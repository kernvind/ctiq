import { Resolver, Mutation, Args, Context } from '@nestjs/graphql';
import { Logger } from '@nestjs/common';
import { AuthService } from './auth.service';
import { AuthPayload } from '@repo/graphql-types';
import { LoginInput } from '@repo/graphql-types';
import { SignupInput } from '@repo/graphql-types';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { ZodLoginSchema, ZodSignupSchema } from '@repo/zod-validations';
import { SessionMeta } from './session.service';

interface GqlReq {
  headers?: Record<string, string | string[] | undefined>;
  ip?: string;
}

// Capture user-agent + ip for the session record (audit / device list later).
function metaFromContext(ctx: { req?: GqlReq }): SessionMeta {
  const req = ctx.req;
  const ua = req?.headers?.['user-agent'];
  return {
    userAgent: Array.isArray(ua) ? ua[0] : (ua ?? null),
    ip: req?.ip ?? null,
  };
}

@Resolver()
export class AuthResolver {
  private readonly logger = new Logger(AuthResolver.name);

  constructor(private readonly authService: AuthService) {}

  @Mutation(() => AuthPayload)
  login(
    @Args('input', zodPipe(ZodLoginSchema)) input: LoginInput,
    @Context() ctx: { req?: GqlReq },
  ): Promise<AuthPayload> {
    // Reaching here means the request passed transport + Zod validation.
    this.logger.log(`login request: username=${input.username}`);
    return this.authService.login(input, metaFromContext(ctx));
  }

  @Mutation(() => AuthPayload)
  signup(
    @Args('input', zodPipe(ZodSignupSchema)) input: SignupInput,
    @Context() ctx: { req?: GqlReq },
  ): Promise<AuthPayload> {
    // Reaching here means the request passed transport + Zod validation.
    this.logger.log(
      `signup request: username=${input.username}, email=${input.email}, role=${input.role}`,
    );
    return this.authService.signup(input, metaFromContext(ctx));
  }

  @Mutation(() => AuthPayload)
  refresh(
    @Args('refreshToken') refreshToken: string,
    @Context() ctx: { req?: GqlReq },
  ): Promise<AuthPayload> {
    this.logger.log('refresh request');
    return this.authService.refresh(refreshToken, metaFromContext(ctx));
  }

  // No auth guard: the refresh token itself is the credential to revoke a session,
  // and it must work even after the access token has expired.
  @Mutation(() => Boolean)
  logout(@Args('refreshToken') refreshToken: string): Promise<boolean> {
    this.logger.log('logout request');
    return this.authService.logout(refreshToken);
  }
}
