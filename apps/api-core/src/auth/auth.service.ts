import {
  Injectable,
  ConflictException,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { compare, hash } from 'bcrypt';
import { UsersService } from '../users/users.service';
import { LoginInput } from '@repo/graphql-types';
import { SignupInput } from '@repo/graphql-types';
@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
  ) {}

  async login(dto: LoginInput): Promise<{ token: string }> {
    const user = await this.usersService.findByUsername(dto.username);

    if (!user || typeof dto.password !== 'string') {
      throw new UnauthorizedException('Invalid credentials');
    }
    console.log('User found:', user);
    const passwordMatches = await compare(dto.password, user.passwordHash);

    if (!passwordMatches) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const token = this.jwtService.sign({
      sub: user.id,
      username: user.username,
    });

    return { token };
  }

  logout(): { message: string } {
    return { message: 'Logged out successfully' };
  }

  async signup(dto: SignupInput): Promise<{ token: string }> {
    const existingUser = await this.usersService.findByUsername(dto.username);
    if (existingUser) {
      throw new ConflictException('Username already exists');
    }
    const existingEmail = await this.usersService.findByEmail(dto.email);
    if (existingEmail) {
      throw new ConflictException('Email already exists');
    }

    const passwordHash = await hash(dto.password, 10);
    const user = await this.usersService.create(
      dto.username,
      dto.email,
      passwordHash,
      dto.name ?? undefined,
    );

    const token = this.jwtService.sign({
      sub: user.id,
      username: user.username,
    });

    return { token };
  }
}
