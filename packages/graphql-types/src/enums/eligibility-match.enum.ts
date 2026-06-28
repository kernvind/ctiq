import { registerEnumType } from '@nestjs/graphql';

/**
 * Eligibility-match enums. Values mirror the inference-service strings exactly so the
 * api-core service can return the HTTP JSON unchanged (ROADMAP step 6).
 */

export enum Verdict {
  PASS = 'pass',
  FAIL = 'fail',
  UNCERTAIN = 'uncertain',
  NOT_EVALUATED = 'not_evaluated',
}

registerEnumType(Verdict, {
  name: 'Verdict',
  description: 'Per-criterion match outcome.',
});

export enum TrialSignal {
  LIKELY_ELIGIBLE = 'likely_eligible',
  POSSIBLE = 'possible',
  LIKELY_EXCLUDED = 'likely_excluded',
}

registerEnumType(TrialSignal, {
  name: 'TrialSignal',
  description: 'Trial-level eligibility signal rolled up from the criterion verdicts.',
});
