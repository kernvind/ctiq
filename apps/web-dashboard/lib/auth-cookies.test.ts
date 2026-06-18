import { describe, it, expect, vi, beforeEach } from 'vitest';

const { store } = vi.hoisted(() => ({
  store: { set: vi.fn(), delete: vi.fn(), get: vi.fn() },
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => store),
}));

import {
  setAuthCookies,
  clearAuthCookies,
  getRefreshToken,
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
} from './auth-cookies';

describe('auth-cookies', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    delete process.env.COOKIE_SECURE;
  });

  it('setAuthCookies sets httpOnly access + refresh cookies (lax, path /)', async () => {
    await setAuthCookies('access-tok', 'refresh-tok');

    expect(store.set).toHaveBeenCalledWith(
      ACCESS_TOKEN_COOKIE,
      'access-tok',
      expect.objectContaining({ httpOnly: true, sameSite: 'lax', path: '/' }),
    );
    expect(store.set).toHaveBeenCalledWith(
      REFRESH_TOKEN_COOKIE,
      'refresh-tok',
      expect.objectContaining({ httpOnly: true, maxAge: expect.any(Number) }),
    );
  });

  it('cookie secure flag is off unless COOKIE_SECURE=true', async () => {
    await setAuthCookies('a', 'r');
    const accessCall = store.set.mock.calls.find(
      (c) => c[0] === ACCESS_TOKEN_COOKIE,
    );
    expect(accessCall?.[2].secure).toBe(false);
  });

  it('cookie secure flag is on when COOKIE_SECURE=true', async () => {
    process.env.COOKIE_SECURE = 'true';
    await setAuthCookies('a', 'r');
    const accessCall = store.set.mock.calls.find(
      (c) => c[0] === ACCESS_TOKEN_COOKIE,
    );
    expect(accessCall?.[2].secure).toBe(true);
  });

  it('clearAuthCookies deletes both cookies', async () => {
    await clearAuthCookies();
    expect(store.delete).toHaveBeenCalledWith(ACCESS_TOKEN_COOKIE);
    expect(store.delete).toHaveBeenCalledWith(REFRESH_TOKEN_COOKIE);
  });

  it('getRefreshToken reads the refresh cookie value', async () => {
    store.get.mockReturnValue({ value: 'rt-123' });
    await expect(getRefreshToken()).resolves.toBe('rt-123');
    expect(store.get).toHaveBeenCalledWith(REFRESH_TOKEN_COOKIE);
  });
});
