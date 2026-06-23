import { InputType, Field } from '@nestjs/graphql';

@InputType()
export class CreateLandscapeInput {
  @Field(() => String)
  name!: string;

  // The semantic query to save and monitor (validated against the search bounds).
  @Field(() => String)
  q!: string;

  @Field(() => String, { nullable: true })
  phase?: string;
}
