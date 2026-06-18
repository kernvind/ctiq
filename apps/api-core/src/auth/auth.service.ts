import {
  Injectable,
  ConflictException,
  UnauthorizedException,
  Logger,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { compare, hash } from 'bcryptjs';
import { Role } from '@repo/db';
import { UsersService, UserRecord } from '../users/users.service';
import { LoginInput, SignupInput, SignupRole } from '@repo/graphql-types';
import { SessionService, SessionMeta } from './session.service';

// Map the frontend-safe SignupRole (no ADMIN) to the Prisma Role. Typing this as
// Record<SignupRole, Role> makes any drift between the two enums a compile error.
const SIGNUP_ROLE_TO_ROLE: Record<SignupRole, Role> = {
  [SignupRole.PATIENT]: Role.PATIENT,
  [SignupRole.CLINICIAN]: Role.CLINICIAN,
  [SignupRole.ANALYST]: Role.ANALYST,
};

// Returned to the resolver -> AuthPayload. Access token authorizes requests;
// refresh token obtains a new access token (rotated on each use).
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
    private readonly sessionService: SessionService,
  ) {}

  private signAccessToken(
    user: Pick<UserRecord, 'id' | 'username' | 'role'>,
  ): string {
    return this.jwtService.sign({
      sub: user.id,
      username: user.username,
      role: user.role,
    });
  }

  async login(dto: LoginInput, meta: SessionMeta = {}): Promise<AuthTokens> {
    const user = await this.usersService.findByUsername(dto.username);

    if (!user || typeof dto.password !== 'string') {
      this.logger.warn(`login: invalid credentials username=${dto.username}`);
      throw new UnauthorizedException('Invalid credentials');
    }
    const passwordMatches = await compare(dto.password, user.passwordHash);

    if (!passwordMatches) {
      this.logger.warn(`login: bad password username=${dto.username}`);
      throw new UnauthorizedException('Invalid credentials');
    }

    const accessToken = this.signAccessToken(user);
    const refreshToken = await this.sessionService.issue(user.id, meta);
    this.logger.log(`login: success userId=${user.id} role=${user.role}`);
    return { accessToken, refreshToken };
  }

  /** Rotate a refresh token and mint a fresh access token for its owner. */
  async refresh(
    refreshToken: string,
    meta: SessionMeta = {},
  ): Promise<AuthTokens> {
    const { userId, refreshToken: newRefreshToken } =
      await this.sessionService.rotate(refreshToken, meta);

    const user = await this.usersService.findById(userId);
    if (!user) {
      // Session existed but the user is gone — treat as unauthenticated.
      this.logger.warn(`refresh: user not found userId=${userId}`);
      throw new UnauthorizedException('Invalid refresh token');
    }

    const accessToken = this.signAccessToken(user);
    this.logger.log(`refresh: success userId=${userId}`);
    return { accessToken, refreshToken: newRefreshToken };
  }

  /** Revoke the session tied to a refresh token (current-session logout). */
  async logout(refreshToken: string): Promise<boolean> {
    await this.sessionService.revoke(refreshToken);
    this.logger.log('logout: session revoked');
    return true;
  }

  async signup(dto: SignupInput, meta: SessionMeta = {}): Promise<AuthTokens> {
    this.logger.log(
      `signup: start username=${dto.username} email=${dto.email} role=${dto.role}`,
    );

    const existingUser = await this.usersService.findByUsername(dto.username);
    if (existingUser) {
      this.logger.warn(`signup: username taken username=${dto.username}`);
      throw new ConflictException('Username already exists');
    }
    const existingEmail = await this.usersService.findByEmail(dto.email);
    if (existingEmail) {
      this.logger.warn(`signup: email taken email=${dto.email}`);
      throw new ConflictException('Email already exists');
    }

    const role = SIGNUP_ROLE_TO_ROLE[dto.role];
    this.logger.log(
      `signup: creating user username=${dto.username} role=${role}`,
    );

    let user: UserRecord;
    try {
      const passwordHash = await hash(dto.password, 10);
      user = await this.usersService.create(
        dto.username,
        dto.email,
        passwordHash,
        dto.name ?? undefined,
        role,
      );
    } catch (err) {
      // Surfaces DB/Prisma errors (e.g. schema mismatch, constraint) in the logs
      // instead of only as a generic GraphQL error on the client.
      this.logger.error(
        `signup: create failed username=${dto.username}: ${(err as Error).message}`,
        (err as Error).stack,
      );
      throw err;
    }

    this.logger.log(`signup: created user id=${user.id} role=${user.role}`);

    const accessToken = this.signAccessToken(user);
    const refreshToken = await this.sessionService.issue(user.id, meta);

    this.logger.log(`signup: tokens issued user id=${user.id}`);
    return { accessToken, refreshToken };
  }
}
