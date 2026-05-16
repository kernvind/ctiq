import { InputType, Field } from '@nestjs/graphql';

@InputType()
export class SignupInput {
  @Field()
  username: string;

  @Field()
  email: string;

  @Field()
  password: string;

  @Field({ nullable: true })
  name?: string;
}
