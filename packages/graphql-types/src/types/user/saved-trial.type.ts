import { ObjectType, Field, ID, GraphQLISODateTime } from '@nestjs/graphql';

/**
 * A trial the current user has saved (their watchlist). `nctId` references the
 * clinical-trial domain by id — the client hydrates trial details via the public
 * `trial(nctId)` query. userId is intentionally not exposed (it's always the caller).
 */
@ObjectType()
export class SavedTrial {
  @Field(() => ID)
  id!: string;

  @Field(() => String)
  nctId!: string;

  @Field(() => GraphQLISODateTime)
  createdAt!: Date;
}
