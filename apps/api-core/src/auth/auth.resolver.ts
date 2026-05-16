import { Resolver, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { AuthService } from './auth.service';
import { AuthPayload } from './types/auth-payload.type';
import { LoginInput } from './types/login.input';
import { SignupInput } from './types/signup.input';
import { GqlAuthGuard } from './guards/gql-auth.guard';

@Resolver()
export class AuthResolver {
  constructor(private readonly authService: AuthService) {}

  @Mutation(() => AuthPayload)
  login(@Args('input') input: LoginInput): Promise<AuthPayload> {
    return this.authService.login(input);
  }

  @Mutation(() => AuthPayload)
  signup(@Args('input') input: SignupInput): Promise<AuthPayload> {
    return this.authService.signup(input);
  }

  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  logout(): boolean {
    return true;
  }
}
