import { HttpException } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { AxiosError } from 'axios';
import { of, throwError } from 'rxjs';
import { TrialSearchService } from './trial-search.service';

function axiosError(status?: number, detail?: string): AxiosError {
  return {
    isAxiosError: true,
    name: 'AxiosError',
    message: 'request failed',
    response: status ? { status, data: detail ? { detail } : {} } : undefined,
  } as AxiosError;
}

describe('TrialSearchService', () => {
  let http: { get: jest.Mock };
  let service: TrialSearchService;

  beforeEach(() => {
    http = { get: jest.fn() };
    const config = {
      getOrThrow: jest.fn((key: string) =>
        key === 'FAST_API_VERSION_V1' ? '/v1' : '/search/trials',
      ),
    } as unknown as ConfigService;
    service = new TrialSearchService(http as unknown as HttpService, config);
  });

  describe('searchTrials', () => {
    it('calls the inference service with the query + top_k and returns the cards', async () => {
      const cards = [{ nct_id: 'NCT1' }];
      http.get.mockReturnValue(of({ data: cards }));

      const result = await service.searchTrials('melanoma', 5);

      expect(result).toBe(cards);
      expect(http.get).toHaveBeenCalledWith('/v1/search/trials', {
        params: { q: 'melanoma', top_k: 5 },
      });
    });

    it('translates an inference-service failure into an HttpException (not a raw error)', async () => {
      http.get.mockReturnValue(
        throwError(() => axiosError(503, 'upstream down')),
      );

      await expect(service.searchTrials('x')).rejects.toBeInstanceOf(
        HttpException,
      );
    });
  });

  describe('mapError (upstream error translation)', () => {
    const mapError = (e: AxiosError) =>
      (
        service as unknown as { mapError(e: AxiosError): HttpException }
      ).mapError(e);

    it('masks any upstream 5xx as a generic 502', () => {
      const ex = mapError(axiosError(500, 'internal stacktrace leak'));
      expect(ex.getStatus()).toBe(502);
      expect(ex.message).toBe('Search service error');
      expect(ex.message).not.toContain('internal stacktrace leak');
    });

    it('passes a 4xx through with the upstream detail message', () => {
      const ex = mapError(axiosError(422, 'invalid query'));
      expect(ex.getStatus()).toBe(422);
      expect(ex.message).toBe('invalid query');
    });

    it('uses a generic message for a 4xx with no detail', () => {
      const ex = mapError(axiosError(400));
      expect(ex.getStatus()).toBe(400);
      expect(ex.message).toBe('Clinical search service unavailable');
    });

    it('treats a network error (no response) as a masked 502', () => {
      // status defaults to 502 (>= 500), so it is masked like any other 5xx.
      const ex = mapError(axiosError(undefined));
      expect(ex.getStatus()).toBe(502);
      expect(ex.message).toBe('Search service error');
    });
  });
});
