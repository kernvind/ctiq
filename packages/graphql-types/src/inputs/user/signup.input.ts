import { InputType, Field } from '@nestjs/graphql';

@InputType()
export class SignupInput {
  @Field(() => String)
  username!: string;

  @Field(() => String)
  email!: string;

  @Field(() => String)
  password!: string;

  @Field(() => String, { nullable: true })
  name?: string;
}
