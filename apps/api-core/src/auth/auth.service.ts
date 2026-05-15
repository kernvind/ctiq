import {
  Injectable,
  ConflictException,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { compare, hash } from 'bcrypt';
import { UsersService } from '../users/users.service';
import { LoginDto } from './dto/login.dto';
import { SignupDto } from './dto/signup.dto';

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
  ) {}

  async login(dto: LoginDto): Promise<{ token: string }> {
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
    });

    return { token };
  }

  async signup(dto: SignupDto): Promise<{ token: string }> {
    const existingUser = await this.usersService.findByUsername(dto.username);
    if (existingUser) {
      throw new ConflictException('Username already exists');
    }

    const passwordHash = await hash(dto.password, 10);
    const user = await this.usersService.create(
      dto.username,
      dto.email,
      passwordHash,
      dto.name,
    );

    const token = this.jwtService.sign({
      sub: user.id,
      username: user.username,
    });

    return { token };
  }
}
