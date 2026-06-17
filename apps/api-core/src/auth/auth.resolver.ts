import { Resolver, Mutation, Args } from '@nestjs/graphql';
import { Logger, UseGuards } from '@nestjs/common';
import { AuthService } from './auth.service';
import { AuthPayload } from '@repo/graphql-types';
import { LoginInput } from '@repo/graphql-types';
import { SignupInput } from '@repo/graphql-types';
import { GqlAuthGuard } from './guards/gql-auth.guard';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { ZodLoginSchema, ZodSignupSchema } from '@repo/zod-validations';

@Resolver()
export class AuthResolver {
  private readonly logger = new Logger(AuthResolver.name);

  constructor(private readonly authService: AuthService) {}

  @Mutation(() => AuthPayload)
  login(
    @Args('input', zodPipe(ZodLoginSchema)) input: LoginInput,
  ): Promise<AuthPayload> {
    // Reaching here means the request passed transport + Zod validation.
    this.logger.log(`login request: username=${input.username}`);
    return this.authService.login(input);
  }

  @Mutation(() => AuthPayload)
  signup(
    @Args('input', zodPipe(ZodSignupSchema)) input: SignupInput,
  ): Promise<AuthPayload> {
    // Reaching here means the request passed transport + Zod validation.
    this.logger.log(
      `signup request: username=${input.username}, email=${input.email}, role=${input.role}`,
    );
    return this.authService.signup(input);
  }

  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  logout(): boolean {
    return true;
  }
}
