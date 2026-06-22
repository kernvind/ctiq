import { InputType, Field } from '@nestjs/graphql';
import { SignupRole } from '../../enums/signup-role.enum';

@InputType()
export class SignupInput {
  @Field(() => String)
  email!: string;

  @Field(() => String)
  password!: string;

  @Field(() => String, { nullable: true })
  name?: string;

  // Self-selected at signup; defaults to PATIENT. ADMIN is not a member of SignupRole,
  // so it cannot be sent. CLINICIAN/ANALYST are treated as unverified for now.
  @Field(() => SignupRole, { defaultValue: SignupRole.PATIENT })
  role!: SignupRole;
}
