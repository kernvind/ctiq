import { ObjectType, Field, ID, GraphQLISODateTime } from '@nestjs/graphql';

/**
 * The query a landscape runs. v1 wraps the semantic search (q + optional phase). The
 * future NL-to-query agent will widen this — additively — without changing existing
 * fields.
 */
@ObjectType()
export class LandscapeSpec {
  @Field(() => String)
  q!: string;

  @Field(() => String, { nullable: true })
  phase?: string | null;
}

/**
 * A saved, monitored landscape. `lastSeenNctIds` + `lastCheckedAt` back the on-view
 * "new since last check" delta the client computes against a fresh run.
 */
@ObjectType()
export class Landscape {
  @Field(() => ID)
  id!: string;

  @Field(() => String)
  name!: string;

  @Field(() => LandscapeSpec)
  spec!: LandscapeSpec;

  @Field(() => [String])
  lastSeenNctIds!: string[];

  @Field(() => GraphQLISODateTime, { nullable: true })
  lastCheckedAt?: Date | null;

  @Field(() => GraphQLISODateTime)
  createdAt!: Date;
}
