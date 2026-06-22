import { describe, it, expect, vi, beforeEach } from 'vitest';

const { setAuthCookiesMock, redirectMock, signupMutationMock } = vi.hoisted(() => ({
  setAuthCookiesMock: vi.fn(),
  redirectMock: vi.fn(),
  signupMutationMock: vi.fn(),
}));

vi.mock('@/lib/auth-cookies', () => ({ setAuthCookies: setAuthCookiesMock }));
vi.mock('next/navigation', () => ({ redirect: redirectMock }));
vi.mock('@repo/generated-schemas-web', () => ({
  sdk: { signup_mutation: signupMutationMock },
}));

import { signup } from './actions';

const VALID = {
  email: 'bob@example.com',
  name: 'Bob',
  password: 'password123',
  confirmPassword: 'password123',
  role: 'CLINICIAN',
};

function form(fields: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return fd;
}

describe('signup action', () => {
  beforeEach(() => vi.clearAllMocks());

  it('returns a validation error for invalid input and never calls the API', async () => {
    const res = await signup(
      null,
      form({ ...VALID, email: 'not-an-email', password: 'short', confirmPassword: 'short' }),
    );
    expect(res).toHaveProperty('error');
    expect(signupMutationMock).not.toHaveBeenCalled();
  });

  it('returns an error when the passwords do not match', async () => {
    const res = await signup(
      null,
      form({ ...VALID, confirmPassword: 'different1' }),
    );
    expect(res).toHaveProperty('error');
    expect(signupMutationMock).not.toHaveBeenCalled();
  });

  it('rejects a privileged role (ADMIN) at validation', async () => {
    const res = await signup(null, form({ ...VALID, role: 'ADMIN' }));
    expect(res).toHaveProperty('error');
    expect(signupMutationMock).not.toHaveBeenCalled();
  });

  it('creates the account, sets cookies, and redirects on success', async () => {
    signupMutationMock.mockResolvedValue({
      signup: { accessToken: 'a-tok', refreshToken: 'r-tok' },
    });

    await signup(null, form(VALID));

    expect(signupMutationMock).toHaveBeenCalledWith({
      input: {
        email: 'bob@example.com',
        password: 'password123',
        name: 'Bob',
        role: 'CLINICIAN',
      },
    });
    expect(setAuthCookiesMock).toHaveBeenCalledWith('a-tok', 'r-tok');
    expect(redirectMock).toHaveBeenCalledWith('/dashboard');
  });

  it('surfaces the server error message on signup failure', async () => {
    signupMutationMock.mockRejectedValue({
      response: { errors: [{ message: 'Email already exists' }] },
    });

    const res = await signup(null, form(VALID));

    expect(res).toEqual({ error: 'Email already exists' });
    expect(setAuthCookiesMock).not.toHaveBeenCalled();
  });
});
