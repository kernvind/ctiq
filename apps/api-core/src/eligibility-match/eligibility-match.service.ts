import { Injectable, Logger, HttpException } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import { AxiosError } from 'axios';
import { PatientProfile } from '../libs/clinical-search/src/index';
import {
  MatchResult,
  MatchedTrial,
  PatientProfileInput,
} from '@repo/graphql-types';

@Injectable()
export class EligibilityMatchService {
  private readonly logger = new Logger(EligibilityMatchService.name);

  constructor(
    private readonly http: HttpService,
    private readonly configService: ConfigService,
  ) {}

  /**
   * Stateless eligibility match: maps the GraphQL profile to the inference-service body and
   * POSTs it. Returns null when the trial has no extracted criteria yet (inference 404).
   * The profile is forwarded, never persisted (PHI gate).
   */
  async matchTrial(
    nctId: string,
    profile: PatientProfileInput,
  ): Promise<MatchResult | null> {
    const api_version = this.configService.getOrThrow<string>(
      'FAST_API_VERSION_V1',
    );
    const match_path = this.configService.getOrThrow<string>(
      'FAST_API_MATCH_PATH',
    );
    const body = this.toInferenceProfile(profile);

    try {
      const { data } = await firstValueFrom(
        this.http.post<MatchResult>(
          `${api_version}${match_path}/${encodeURIComponent(nctId)}`,
          body,
        ),
      );
      return data;
    } catch (e) {
      const err = e as AxiosError;
      // 404 = trial has no extracted eligibility yet (Stage A hasn't run); not a failure.
      if (err.response?.status === 404) {
        return null;
      }
      this.logger.error(
        `Match failed: nctId=${nctId} status=${err.response?.status} message=${err.message}`,
      );
      throw this.mapError(err);
    }
  }

  /**
   * Patient-first: rank recruiting trials for a condition by how well the profile matches
   * their eligibility. Generates candidates + batch-matches in the inference service.
   */
  async matchTrials(
    condition: string,
    profile: PatientProfileInput,
    topK = 50,
    recruitingOnly = true,
  ): Promise<MatchedTrial[]> {
    const api_version = this.configService.getOrThrow<string>(
      'FAST_API_VERSION_V1',
    );
    const match_path = this.configService.getOrThrow<string>(
      'FAST_API_MATCH_PATH',
    );
    const body = {
      profile: this.toInferenceProfile(profile),
      condition,
      top_k: topK,
      recruiting_only: recruitingOnly,
    };
    try {
      const { data } = await firstValueFrom(
        this.http.post<MatchedTrial[]>(`${api_version}${match_path}`, body),
      );
      return data;
    } catch (e) {
      const err = e as AxiosError;
      this.logger.error(
        `Patient match failed: condition=${condition} status=${err.response?.status} message=${err.message}`,
      );
      throw this.mapError(err);
    }
  }

  /** GraphQL input (typed pair lists) -> inference PatientProfile (maps + dict folding). */
  private toInferenceProfile(p: PatientProfileInput): PatientProfile {
    const biomarkers: Record<string, string | number> = {};
    for (const b of p.biomarkers ?? []) {
      const num = Number(b.value);
      biomarkers[b.marker] =
        b.value.trim() !== '' && !Number.isNaN(num) ? num : b.value;
    }
    const labs: Record<string, number> = {};
    for (const l of p.labs ?? []) labs[l.analyte] = l.value;

    return {
      age_years: p.age_years ?? null,
      sex: p.sex ?? null,
      ecog: p.ecog ?? null,
      stage: p.stage ?? null,
      biomarkers,
      prior_therapies: p.prior_therapies ?? [],
      treatment_naive: p.treatment_naive ?? null,
      labs,
    };
  }

  private mapError(err: AxiosError): HttpException {
    const status = err.response?.status ?? 502;
    const message =
      (err.response?.data as { detail?: string })?.detail ??
      'Eligibility match service unavailable';
    if (status >= 500) {
      return new HttpException('Match service error', 502);
    }
    return new HttpException(message, status);
  }
}
