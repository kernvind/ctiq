import { ObjectType, Field, Int } from '@nestjs/graphql';
import { Verdict, TrialSignal } from '../../enums/eligibility-match.enum';

/**
 * Eligibility match result. snake_case fields mirror the inference-service `MatchResult`
 * JSON so the api-core service can return the HTTP response directly (same convention as
 * TrialDetail). The verdict list IS the match explanation (ROADMAP step 6).
 */

@ObjectType()
export class CriterionVerdict {
  @Field(() => String, { description: 'inclusion | exclusion' })
  criterion_type!: string;

  @Field(() => String, { nullable: true })
  category?: string | null;

  @Field(() => String, { description: 'Verbatim criterion text' })
  text!: string;

  @Field(() => Verdict)
  verdict!: Verdict;

  @Field(() => String, { description: 'Human-readable why' })
  reason!: string;
}

@ObjectType()
export class MatchResult {
  @Field(() => String)
  nct_id!: string;

  @Field(() => TrialSignal)
  signal!: TrialSignal;

  @Field(() => Int)
  n_pass!: number;

  @Field(() => Int)
  n_fail!: number;

  @Field(() => Int)
  n_uncertain!: number;

  @Field(() => Int)
  n_not_evaluated!: number;

  @Field(() => [CriterionVerdict], { defaultValue: [] })
  verdicts: CriterionVerdict[] = [];
}

/**
 * A candidate trial + its match summary for the patient-first ranked list (no per-criterion
 * verdicts — drill into `matchTrial(nctId, profile)` for those). snake_case mirrors the
 * inference-service `MatchedTrial`.
 */
@ObjectType()
export class MatchedTrial {
  @Field(() => String)
  nct_id!: string;

  @Field(() => String, { nullable: true, description: 'Brief Title' })
  brief_title?: string | null;

  @Field(() => String, { nullable: true, description: 'Overall Status' })
  overall_status?: string | null;

  @Field(() => [String], { defaultValue: [] })
  phases: string[] = [];

  @Field(() => [String], { defaultValue: [] })
  conditions: string[] = [];

  @Field(() => String, { nullable: true, description: 'Lead Sponsor Name' })
  lead_sponsor_name?: string | null;

  @Field(() => TrialSignal)
  signal!: TrialSignal;

  @Field(() => Int)
  n_pass!: number;

  @Field(() => Int)
  n_fail!: number;

  @Field(() => Int)
  n_uncertain!: number;

  @Field(() => Int)
  n_not_evaluated!: number;

  @Field(() => Boolean, {
    description: 'False when the trial has no extracted eligibility yet (signal defaults to possible)',
  })
  has_criteria!: boolean;

  @Field(() => [CriterionVerdict], {
    defaultValue: [],
    description: 'The failing criteria (verdict=FAIL) behind a likely_excluded signal — the inline "why"',
  })
  blockers: CriterionVerdict[] = [];
}
