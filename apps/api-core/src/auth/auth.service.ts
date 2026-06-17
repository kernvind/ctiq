import {
  Injectable,
  ConflictException,
  UnauthorizedException,
  Logger,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { compare, hash } from 'bcrypt';
import { Role } from '@repo/db';
import { UsersService, UserRecord } from '../users/users.service';
import { LoginInput, SignupInput, SignupRole } from '@repo/graphql-types';

// Map the frontend-safe SignupRole (no ADMIN) to the Prisma Role. Typing this as
// Record<SignupRole, Role> makes any drift between the two enums a compile error.
const SIGNUP_ROLE_TO_ROLE: Record<SignupRole, Role> = {
  [SignupRole.PATIENT]: Role.PATIENT,
  [SignupRole.CLINICIAN]: Role.CLINICIAN,
  [SignupRole.ANALYST]: Role.ANALYST,
};

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
  ) {}

  async login(dto: LoginInput): Promise<{ token: string }> {
    const user = await this.usersService.findByUsername(dto.username);

    if (!user || typeof dto.password !== 'string') {
      throw new UnauthorizedException('Invalid credentials');
    }
    const passwordMatches = await compare(dto.password, user.passwordHash);

    if (!passwordMatches) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const token = this.jwtService.sign({
      sub: user.id,
      username: user.username,
      role: user.role,
    });

    return { token };
  }

  logout(): { message: string } {
    return { message: 'Logged out successfully' };
  }

  async signup(dto: SignupInput): Promise<{ token: string }> {
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
    this.logger.log(`signup: creating user username=${dto.username} role=${role}`);

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

    const token = this.jwtService.sign({
      sub: user.id,
      username: user.username,
      role: user.role,
    });

    this.logger.log(`signup: token issued user id=${user.id}`);
    return { token };
  }
}
