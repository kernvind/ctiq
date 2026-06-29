import { HttpException } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { AxiosError } from 'axios';
import { of, throwError } from 'rxjs';
import { EligibilityMatchService } from './eligibility-match.service';
import type { PatientProfileInput } from '@repo/graphql-types';

function axiosError(status?: number, detail?: string): AxiosError {
  return {
    isAxiosError: true,
    name: 'AxiosError',
    message: 'request failed',
    response: status ? { status, data: detail ? { detail } : {} } : undefined,
  } as AxiosError;
}

function profile(over: Partial<PatientProfileInput> = {}): PatientProfileInput {
  return {
    age_years: 65,
    sex: 'MALE',
    ecog: 1,
    stage: 'IV',
    biomarkers: [
      { marker: 'PD-L1', value: '60' },
      { marker: 'EGFR', value: 'wild-type' },
    ],
    prior_therapies: ['chemotherapy'],
    treatment_naive: null,
    labs: [{ analyte: 'ANC', value: 1800 }],
    ...over,
  } as PatientProfileInput;
}

describe('EligibilityMatchService', () => {
  let http: { post: jest.Mock };
  let service: EligibilityMatchService;

  beforeEach(() => {
    http = { post: jest.fn() };
    const config = {
      getOrThrow: jest.fn((key: string) =>
        key === 'FAST_API_VERSION_V1' ? '/v1' : '/match/trials',
      ),
    } as unknown as ConfigService;
    service = new EligibilityMatchService(http as unknown as HttpService, config);
  });

  describe('toInferenceProfile (pair-lists -> dicts)', () => {
    const map = (p: PatientProfileInput) =>
      (
        service as unknown as {
          toInferenceProfile(p: PatientProfileInput): Record<string, unknown>;
        }
      ).toInferenceProfile(p);

    it('folds biomarker pairs into a dict, parsing numerics but keeping status strings', () => {
      const out = map(profile());
      expect(out.biomarkers).toEqual({ 'PD-L1': 60, EGFR: 'wild-type' });
    });

    it('folds labs into a dict and passes scalar fields through (snake_case)', () => {
      const out = map(profile());
      expect(out.labs).toEqual({ ANC: 1800 });
      expect(out.age_years).toBe(65);
      expect(out.prior_therapies).toEqual(['chemotherapy']);
    });

    it('folds washout pairs into a days-since dict', () => {
      const out = map(
        profile({
          washouts: [
            { event: 'chemotherapy', days_since: 14 },
            { event: 'surgery', days_since: 60 },
          ],
        }),
      );
      expect(out.washouts).toEqual({ chemotherapy: 14, surgery: 60 });
    });

    it('defaults washouts to an empty dict when none are supplied', () => {
      const out = map(profile({ washouts: undefined as never }));
      expect(out.washouts).toEqual({});
    });
  });

  describe('matchTrial', () => {
    it('POSTs the mapped profile to /match/trials/{nctId} and returns the result', async () => {
      const result = { nct_id: 'NCT06561386', signal: 'likely_eligible' };
      http.post.mockReturnValue(of({ data: result }));

      const res = await service.matchTrial('NCT06561386', profile());

      expect(res).toBe(result);
      const [url, body] = http.post.mock.calls[0];
      expect(url).toBe('/v1/match/trials/NCT06561386');
      expect((body as { biomarkers: unknown }).biomarkers).toEqual({
        'PD-L1': 60,
        EGFR: 'wild-type',
      });
    });

    it('returns null when the trial has no extracted criteria (upstream 404)', async () => {
      http.post.mockReturnValue(throwError(() => axiosError(404, 'none')));
      await expect(service.matchTrial('NCT00000000', profile())).resolves.toBeNull();
    });

    it('translates a non-404 upstream failure into an HttpException', async () => {
      http.post.mockReturnValue(throwError(() => axiosError(503, 'down')));
      await expect(service.matchTrial('NCT06561386', profile())).rejects.toBeInstanceOf(
        HttpException,
      );
    });
  });

  describe('matchTrials (patient-first)', () => {
    it('POSTs {profile, condition, top_k, recruiting_only} to /match/trials', async () => {
      const ranked = [{ nct_id: 'NCT1', signal: 'likely_eligible' }];
      http.post.mockReturnValue(of({ data: ranked }));

      const res = await service.matchTrials('melanoma', profile(), 25, false);

      expect(res).toBe(ranked);
      const [url, body] = http.post.mock.calls[0];
      expect(url).toBe('/v1/match/trials');
      expect(body).toMatchObject({
        condition: 'melanoma',
        top_k: 25,
        recruiting_only: false,
      });
      expect((body as { profile: { labs: unknown } }).profile.labs).toEqual({ ANC: 1800 });
    });

    it('translates an upstream failure into an HttpException', async () => {
      http.post.mockReturnValue(throwError(() => axiosError(503, 'down')));
      await expect(service.matchTrials('melanoma', profile())).rejects.toBeInstanceOf(
        HttpException,
      );
    });
  });
});
