import { ObjectType, Field, ID, GraphQLISODateTime } from '@nestjs/graphql';

/**
 * A trial in the current user's open-trial portfolio — the studies their site is running and
 * wants to enroll patients into (site-payer wedge). `nctId` references the clinical-trial
 * domain by id; the client hydrates details via the public `trial(nctId)` query. userId is
 * intentionally not exposed (it's always the caller).
 */
@ObjectType()
export class PortfolioTrial {
  @Field(() => ID)
  id!: string;

  @Field(() => String)
  nctId!: string;

  @Field(() => GraphQLISODateTime)
  createdAt!: Date;
}
