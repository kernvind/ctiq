import { InputType, Field, Float, Int } from '@nestjs/graphql';
import { IsOptional, IsString, IsNumber, IsInt, IsBoolean, IsArray } from 'class-validator';

/**
 * Patient profile for the stateless eligibility matcher (ROADMAP step 6). GraphQL has no
 * map type, so biomarkers/labs are typed key-value lists; the api-core service folds them
 * into the dicts the inference-service expects. NEVER persisted — evaluated in-request only.
 */

@InputType()
export class BiomarkerInput {
  @IsString()
  @Field(() => String, { description: 'Marker, e.g. EGFR, PD-L1' })
  marker!: string;

  @IsString()
  @Field(() => String, { description: 'Value as text: "60" (numeric) or "wild-type" (status)' })
  value!: string;
}

@InputType()
export class LabInput {
  @IsString()
  @Field(() => String, { description: 'Analyte, e.g. ANC, creatinine' })
  analyte!: string;

  @IsNumber()
  @Field(() => Float)
  value!: number;
}

@InputType()
export class PatientProfileInput {
  @IsOptional()
  @IsNumber()
  @Field(() => Float, { nullable: true })
  age_years?: number | null;

  @IsOptional()
  @IsString()
  @Field(() => String, { nullable: true, description: 'MALE | FEMALE' })
  sex?: string | null;

  @IsOptional()
  @IsInt()
  @Field(() => Int, { nullable: true, description: 'ECOG performance status' })
  ecog?: number | null;

  @IsOptional()
  @IsString()
  @Field(() => String, { nullable: true, description: 'Disease stage, e.g. "IV"' })
  stage?: string | null;

  @IsArray()
  @Field(() => [BiomarkerInput], { defaultValue: [] })
  biomarkers: BiomarkerInput[] = [];

  @IsArray()
  @Field(() => [String], { defaultValue: [], description: 'Prior therapy classes received' })
  prior_therapies: string[] = [];

  @IsOptional()
  @IsBoolean()
  @Field(() => Boolean, { nullable: true })
  treatment_naive?: boolean | null;

  @IsArray()
  @Field(() => [LabInput], { defaultValue: [] })
  labs: LabInput[] = [];
}
