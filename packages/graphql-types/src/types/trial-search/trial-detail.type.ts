import { ObjectType, Field, Float, Int } from "@nestjs/graphql";

/**
 * Full single-trial record for the detail page. Mirrors the inference-service
 * `TrialDetail` schema (snake_case fields line up with the JSON over the wire), so the
 * api-core service can return the HTTP response directly. Search-agnostic — no match
 * context — so it can also back the public (no-account) surface.
 */

@ObjectType()
export class ContactInfo {
  @Field(() => String, { nullable: true })
  name?: string | null;

  @Field(() => String, { nullable: true })
  role?: string | null;

  @Field(() => String, { nullable: true })
  phone?: string | null;

  @Field(() => String, { nullable: true })
  email?: string | null;
}

@ObjectType()
export class Collaborator {
  @Field(() => String, { nullable: true })
  name?: string | null;

  @Field(() => String, { nullable: true, description: "Sponsor Class" })
  sponsor_class?: string | null;
}

@ObjectType()
export class Reference {
  @Field(() => String, { nullable: true })
  citation?: string | null;

  @Field(() => String, { nullable: true })
  type?: string | null;

  @Field(() => String, { nullable: true })
  pmid?: string | null;
}

@ObjectType()
export class TrialLocationDetail {
  @Field(() => String, { nullable: true })
  facility?: string | null;

  @Field(() => String, { nullable: true })
  city?: string | null;

  @Field(() => String, { nullable: true })
  state?: string | null;

  @Field(() => String, { nullable: true })
  country?: string | null;

  @Field(() => String, { nullable: true })
  zip?: string | null;

  @Field(() => String, { nullable: true })
  status?: string | null;
}

@ObjectType()
export class TrialIntervention {
  @Field(() => String, { nullable: true })
  type?: string | null;

  @Field(() => String, { nullable: true })
  name?: string | null;

  @Field(() => String, { nullable: true })
  description?: string | null;
}

@ObjectType()
export class TrialOutcome {
  @Field(() => String, { nullable: true, description: "Outcome Type" })
  outcome_type?: string | null;

  @Field(() => String, { nullable: true })
  measure?: string | null;

  @Field(() => String, { nullable: true })
  description?: string | null;

  @Field(() => String, { nullable: true, description: "Time Frame" })
  time_frame?: string | null;
}

@ObjectType()
export class TrialArmGroup {
  @Field(() => String, { nullable: true })
  label?: string | null;

  @Field(() => String, { nullable: true })
  type?: string | null;

  @Field(() => String, { nullable: true })
  description?: string | null;
}

@ObjectType()
export class TrialOfficial {
  @Field(() => String, { nullable: true })
  name?: string | null;

  @Field(() => String, { nullable: true })
  affiliation?: string | null;

  @Field(() => String, { nullable: true })
  role?: string | null;
}

@ObjectType()
export class TrialDetail {
  @Field(() => String)
  nct_id!: string;

  // Identification
  @Field(() => String, { nullable: true, description: "Brief Title" })
  brief_title?: string | null;

  @Field(() => String, { nullable: true, description: "Official Title" })
  official_title?: string | null;

  @Field(() => String, { nullable: true })
  acronym?: string | null;

  @Field(() => String, { nullable: true })
  organization?: string | null;

  // Status / dates (ISO date strings)
  @Field(() => String, { nullable: true, description: "Overall Status" })
  overall_status?: string | null;

  @Field(() => String, { nullable: true, description: "Start Date" })
  start_date?: string | null;

  @Field(() => String, { nullable: true, description: "Completion Date" })
  completion_date?: string | null;

  @Field(() => String, { nullable: true, description: "Primary Completion Date" })
  primary_completion_date?: string | null;

  @Field(() => String, { nullable: true, description: "Last Update Post Date" })
  last_update_post_date?: string | null;

  // Sponsor
  @Field(() => String, { nullable: true, description: "Lead Sponsor Name" })
  lead_sponsor_name?: string | null;

  @Field(() => String, { nullable: true, description: "Lead Sponsor Class" })
  lead_sponsor_class?: string | null;

  @Field(() => [Collaborator], { defaultValue: [] })
  collaborators: Collaborator[] = [];

  // Design
  @Field(() => String, { nullable: true, description: "Study Type" })
  study_type?: string | null;

  @Field(() => [String], { description: "Phases", defaultValue: [] })
  phases: string[] = [];

  @Field(() => String, { nullable: true })
  allocation?: string | null;

  @Field(() => String, { nullable: true, description: "Intervention Model" })
  intervention_model?: string | null;

  @Field(() => String, { nullable: true, description: "Primary Purpose" })
  primary_purpose?: string | null;

  @Field(() => String, { nullable: true })
  masking?: string | null;

  @Field(() => Int, { nullable: true, description: "Enrollment Count" })
  enrollment_count?: number | null;

  @Field(() => String, { nullable: true, description: "Enrollment Type" })
  enrollment_type?: string | null;

  // Topic
  @Field(() => [String], { description: "Conditions", defaultValue: [] })
  conditions: string[] = [];

  @Field(() => [String], { description: "Keywords", defaultValue: [] })
  keywords: string[] = [];

  // Eligibility
  @Field(() => String, { nullable: true, description: "Eligibility Criteria" })
  eligibility_criteria?: string | null;

  @Field(() => String, { nullable: true, description: "Min Age Raw" })
  min_age_raw?: string | null;

  @Field(() => String, { nullable: true, description: "Max Age Raw" })
  max_age_raw?: string | null;

  @Field(() => Float, { nullable: true, description: "Min Age Years" })
  min_age_years?: number | null;

  @Field(() => Float, { nullable: true, description: "Max Age Years" })
  max_age_years?: number | null;

  @Field(() => String, { nullable: true })
  sex?: string | null;

  @Field(() => [String], { description: "Std Ages", defaultValue: [] })
  std_ages: string[] = [];

  @Field(() => Boolean, { nullable: true, description: "Healthy Volunteers" })
  healthy_volunteers?: boolean | null;

  // Descriptions
  @Field(() => String, { nullable: true, description: "Brief Summary" })
  brief_summary?: string | null;

  @Field(() => String, { nullable: true, description: "Detailed Description" })
  detailed_description?: string | null;

  // Contacts / references
  @Field(() => [ContactInfo], { defaultValue: [] })
  central_contacts: ContactInfo[] = [];

  @Field(() => [Reference], { defaultValue: [] })
  references: Reference[] = [];

  // Child collections
  @Field(() => [TrialLocationDetail], { defaultValue: [] })
  locations: TrialLocationDetail[] = [];

  @Field(() => [TrialIntervention], { defaultValue: [] })
  interventions: TrialIntervention[] = [];

  @Field(() => [TrialOutcome], { defaultValue: [] })
  outcomes: TrialOutcome[] = [];

  @Field(() => [TrialArmGroup], { defaultValue: [] })
  arm_groups: TrialArmGroup[] = [];

  @Field(() => [TrialOfficial], { defaultValue: [] })
  officials: TrialOfficial[] = [];
}
