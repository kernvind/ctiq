import { Injectable, Logger, HttpException } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom, catchError } from 'rxjs';
import { AxiosError } from 'axios';
import { TrialCard, TrialDetail } from '../libs/clinical-search/src/index';

@Injectable()
export class TrialSearchService {
  private readonly logger = new Logger(TrialSearchService.name);

  constructor(
    private readonly http: HttpService,
    private readonly configService: ConfigService,
  ) {}

  async searchTrials(query: string, topK = 20): Promise<TrialCard[]> {
    const api_version = this.configService.getOrThrow<string>(
      'FAST_API_VERSION_V1',
    );
    const search_path = this.configService.getOrThrow<string>(
      'FAST_API_SEARCH_TRIAL_PATH',
    );
    const { data } = await firstValueFrom(
      this.http
        .get<TrialCard[]>(`${api_version}${search_path}`, {
          params: { q: query, top_k: topK },
        })
        .pipe(
          catchError((err: AxiosError) => {
            this.logger.error(
              `Search failed: status=${err.response?.status} message=${err.message}`,
            );
            throw this.mapError(err);
          }),
        ),
    );
    return data;
  }

  async getTrial(nctId: string): Promise<TrialDetail | null> {
    const api_version = this.configService.getOrThrow<string>(
      'FAST_API_VERSION_V1',
    );
    const search_path = this.configService.getOrThrow<string>(
      'FAST_API_SEARCH_TRIAL_PATH',
    );
    try {
      const { data } = await firstValueFrom(
        this.http.get<TrialDetail>(
          `${api_version}${search_path}/${encodeURIComponent(nctId)}`,
        ),
      );
      return data;
    } catch (e) {
      const err = e as AxiosError;
      // 404 is a legitimate "no such trial", not a service failure — return null so the
      // resolver can return null (web layer renders a not-found page).
      if (err.response?.status === 404) {
        return null;
      }
      this.logger.error(
        `Trial detail fetch failed: nctId=${nctId} status=${err.response?.status} message=${err.message}`,
      );
      throw this.mapError(err);
    }
  }

  private mapError(err: AxiosError): HttpException {
    const status = err.response?.status ?? 502;
    const message =
      (err.response?.data as { detail?: string })?.detail ??
      'Clinical search service unavailable';

    // Don't pass through 5xx as-is — internal failures should look like 502 to the client
    if (status >= 500) {
      return new HttpException('Search service error', 502);
    }
    return new HttpException(message, status);
  }
}
