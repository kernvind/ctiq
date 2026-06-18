import { describe, it, expect, vi, beforeEach } from 'vitest';

const { cookieStore, getAuthedSdkMock, refreshSessionMock } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn() },
  getAuthedSdkMock: vi.fn(),
  refreshSessionMock: vi.fn(),
}));

vi.mock('next/headers', () => ({ cookies: vi.fn(async () => cookieStore) }));
vi.mock('@repo/generated-schemas-web', () => ({ getAuthedSdk: getAuthedSdkMock }));
vi.mock('@/app/auth-actions', () => ({ refreshSession: refreshSessionMock }));

import { withAuthedSdk } from './authed-sdk';

const authError = () => ({
  response: { errors: [{ extensions: { code: 'UNAUTHENTICATED' } }] },
});

describe('withAuthedSdk', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cookieStore.get.mockReturnValue({ value: 'access-1' });
  });

  it('runs the call with the cookie access token and returns the result (no refresh)', async () => {
    const sdk = { tag: 'sdk' };
    getAuthedSdkMock.mockReturnValue(sdk);

    const result = await withAuthedSdk(async (s) => {
      expect(s).toBe(sdk);
      return 'ok';
    });

    expect(getAuthedSdkMock).toHaveBeenCalledWith('access-1');
    expect(result).toBe('ok');
    expect(refreshSessionMock).not.toHaveBeenCalled();
  });

  it('on an auth error: refreshes and retries once with the new token', async () => {
    getAuthedSdkMock
      .mockReturnValueOnce('sdk-old')
      .mockReturnValueOnce('sdk-new');
    cookieStore.get
      .mockReturnValueOnce({ value: 'access-1' })
      .mockReturnValueOnce({ value: 'access-2' });
    refreshSessionMock.mockResolvedValue(true);

    let attempts = 0;
    const result = await withAuthedSdk(async (s) => {
      attempts += 1;
      if (attempts === 1) throw authError();
      return `retried:${s}`;
    });

    expect(refreshSessionMock).toHaveBeenCalledTimes(1);
    expect(getAuthedSdkMock).toHaveBeenNthCalledWith(2, 'access-2');
    expect(result).toBe('retried:sdk-new');
  });

  it('rethrows the original error when the refresh fails', async () => {
    refreshSessionMock.mockResolvedValue(false);
    const err = authError();
    await expect(
      withAuthedSdk(async () => {
        throw err;
      }),
    ).rejects.toBe(err);
  });

  it('rethrows a non-auth error immediately without refreshing', async () => {
    const err = new Error('boom');
    await expect(
      withAuthedSdk(async () => {
        throw err;
      }),
    ).rejects.toBe(err);
    expect(refreshSessionMock).not.toHaveBeenCalled();
  });
});
