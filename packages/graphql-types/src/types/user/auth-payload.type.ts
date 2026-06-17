import { ObjectType, Field } from '@nestjs/graphql';

@ObjectType()
export class AuthPayload {
  // Short-lived JWT used to authorize requests.
  @Field(() => String)
  accessToken!: string;

  // Long-lived opaque token used to obtain a new access token. Rotated on each use;
  // only its hash is stored server-side.
  @Field(() => String)
  refreshToken!: string;
}
