import {
  Body,
  Controller,
  HttpCode,
  HttpStatus,
  Post,
  UseGuards,
} from '@nestjs/common';
import { AuthService } from './auth.service';
import { LoginSchema } from './dto/login.dto';
import type { LoginDto } from './dto/login.dto';
import { SignupSchema } from './dto/signup.dto';
import type { SignupDto } from './dto/signup.dto';
import { JwtAuthGuard } from './guards/jwt-auth.guard';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  login(@Body(new ZodValidationPipe(LoginSchema)) dto: LoginDto) {
    return this.authService.login(dto);
  }

  @Post('signup')
  @HttpCode(HttpStatus.CREATED)
  signup(@Body(new ZodValidationPipe(SignupSchema)) dto: SignupDto) {
    return this.authService.signup(dto);
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  @UseGuards(JwtAuthGuard)
  logout() {
    return this.authService.logout();
  }
}
