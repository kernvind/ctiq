import { describe, it, expect, vi, beforeEach } from 'vitest';

const {
  getRefreshTokenMock,
  setAuthCookiesMock,
  clearAuthCookiesMock,
  refreshMutationMock,
} = vi.hoisted(() => ({
  getRefreshTokenMock: vi.fn(),
  setAuthCookiesMock: vi.fn(),
  clearAuthCookiesMock: vi.fn(),
  refreshMutationMock: vi.fn(),
}));

vi.mock('@/lib/auth-cookies', () => ({
  getRefreshToken: getRefreshTokenMock,
  setAuthCookies: setAuthCookiesMock,
  clearAuthCookies: clearAuthCookiesMock,
}));
vi.mock('@repo/generated-schemas-web', () => ({
  sdk: { refresh_mutation: refreshMutationMock },
}));

import { refreshSession } from './auth-actions';

describe('refreshSession', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns false (and does not call the API) when there is no refresh token', async () => {
    getRefreshTokenMock.mockResolvedValue(undefined);
    await expect(refreshSession()).resolves.toBe(false);
    expect(refreshMutationMock).not.toHaveBeenCalled();
  });

  it('rotates the token and sets the new cookies on success', async () => {
    getRefreshTokenMock.mockResolvedValue('rt-1');
    refreshMutationMock.mockResolvedValue({
      refresh: { accessToken: 'a2', refreshToken: 'r2' },
    });

    await expect(refreshSession()).resolves.toBe(true);
    expect(refreshMutationMock).toHaveBeenCalledWith({ refreshToken: 'rt-1' });
    expect(setAuthCookiesMock).toHaveBeenCalledWith('a2', 'r2');
  });

  it('clears cookies and returns false when the refresh is rejected', async () => {
    getRefreshTokenMock.mockResolvedValue('rt-1');
    refreshMutationMock.mockRejectedValue(new Error('invalid refresh token'));

    await expect(refreshSession()).resolves.toBe(false);
    expect(clearAuthCookiesMock).toHaveBeenCalled();
    expect(setAuthCookiesMock).not.toHaveBeenCalled();
  });
});
