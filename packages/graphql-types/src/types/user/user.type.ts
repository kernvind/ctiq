import { ObjectType, Field, ID } from '@nestjs/graphql';
import { UserRole } from '../../enums/role.enum';

/**
 * The authenticated user, returned by the `me` query. Deliberately exposes only
 * non-sensitive account fields — never passwordHash or session data.
 */
@ObjectType()
export class User {
  @Field(() => ID)
  id!: string;

  @Field(() => String)
  email!: string;

  @Field(() => String, { nullable: true })
  name?: string | null;

  @Field(() => UserRole)
  role!: UserRole;
}
