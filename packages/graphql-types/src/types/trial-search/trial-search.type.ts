import { ObjectType, Field, Float, Int } from "@nestjs/graphql";

@ObjectType()
export class EligibilitySummary {
  @Field(() => String, { nullable: true, description: "Min Age Raw" })
  min_age_raw?: string | null;

  @Field(() => String, { nullable: true, description: "Max Age Raw" })
  max_age_raw?: string | null;

  @Field(() => Float, { nullable: true, description: "Min Age Years" })
  min_age_years?: number | null;

  @Field(() => Float, { nullable: true, description: "Max Age Years" })
  max_age_years?: number | null;

  @Field(() => String)
  sex!: string;

  @Field(() => Boolean)
  accepts_healthy_volunteers?: boolean | null;

  @Field(() => String, { nullable: true, description: "Short Summary" })
  short_summary?: string | null;
}

@ObjectType()
export class Facility {
  @Field(() => String, { nullable: true })
  facility?: string | null;

  @Field(() => String, { nullable: true })
  city?: string | null;

  @Field(() => String, { nullable: true })
  state?: string | null;

  @Field(() => String, { nullable: true })
  country?: string | null;

  @Field(() => String, { nullable: true })
  status?: string | null;
}

@ObjectType()
export class LocationSummary {
  @Field(() => Int)
  total_sites!: number;

  @Field(() => Int)
  recruiting_sites: number = 0;

  @Field(() => [Facility], {
    description: "Sample Facilities",
    defaultValue: [],
  })
  sample_facilities: Facility[] = [];

  @Field(() => String, { nullable: true, description: "Nearest Facility" })
  nearest_facility?: string | null;

  @Field(() => Float, {
    nullable: true,
    description: "Nearest Distance in Kilometers",
  })
  nearest_distance_km?: number | null;
}

@ObjectType()
export class MatchingChunk {
  @Field(() => String)
  field_type!: string;

  @Field(() => String)
  chunk_text!: string;

  @Field(() => Float, { description: "MatchingDistance" })
  distance!: number;
}

@ObjectType()
export class TrialCard {
  @Field(() => String)
  nct_id!: string;

  @Field(() => String)
  brief_title!: string;

  @Field(() => String)
  overall_status!: string;

  @Field(() => [String], { description: "Phases" })
  phases: string[] = [];

  @Field(() => MatchingChunk)
  best_matching_chunk!: MatchingChunk;

  @Field(() => String, { nullable: true, description: "Match Explanation" })
  match_explanation?: string | null;

  @Field(() => [MatchingChunk], { description: "Top Chunks", defaultValue: [] })
  top_chunks: MatchingChunk[] = [];

  @Field(() => EligibilitySummary)
  eligibility!: EligibilitySummary;

  @Field(() => LocationSummary)
  locations!: LocationSummary;

  @Field(() => String, { description: "Lead Sponsor Name" })
  lead_sponsor_name?: string;

  @Field(() => String, { description: "Lead Sponsor Class" })
  lead_sponsor_class?: string;
}
