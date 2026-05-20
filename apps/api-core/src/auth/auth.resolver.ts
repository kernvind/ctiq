import { Resolver, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { AuthService } from './auth.service';
import { AuthPayload } from '@repo/graphql-types';
import { LoginInput } from '@repo/graphql-types';
import { SignupInput } from '@repo/graphql-types';
import { GqlAuthGuard } from './guards/gql-auth.guard';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { ZodLoginSchema, ZodSignupSchema } from '@repo/zod-validations';

@Resolver()
export class AuthResolver {
  constructor(private readonly authService: AuthService) {}

  @Mutation(() => AuthPayload)
  login(
    @Args('input', zodPipe(ZodLoginSchema)) input: LoginInput,
  ): Promise<AuthPayload> {
    return this.authService.login(input);
  }

  @Mutation(() => AuthPayload)
  signup(
    @Args('input', zodPipe(ZodSignupSchema)) input: SignupInput,
  ): Promise<AuthPayload> {
    return this.authService.signup(input);
  }

  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  logout(): boolean {
    return true;
  }
}
