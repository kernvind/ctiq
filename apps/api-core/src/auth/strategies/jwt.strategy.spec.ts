import { ConfigService } from '@nestjs/config';
import { Role } from '@repo/db';
import { JwtStrategy, JwtPayload } from './jwt.strategy';

const configWith = (secret = 'a-secret') =>
  ({ getOrThrow: jest.fn().mockReturnValue(secret) }) as unknown as ConfigService;

describe('JwtStrategy', () => {
  it('reads the signing secret via getOrThrow at construction', () => {
    const config = configWith();

    new JwtStrategy(config);

    expect(config.getOrThrow).toHaveBeenCalledWith('JWT_SECRET');
  });

  it('maps the verified payload to the request user (sub -> id, plus email + role)', () => {
    const strategy = new JwtStrategy(configWith());

    const payload: JwtPayload = {
      sub: 'u1',
      email: 'alice@example.com',
      role: Role.ANALYST,
    };

    expect(strategy.validate(payload)).toEqual({
      id: 'u1',
      email: 'alice@example.com',
      role: Role.ANALYST,
    });
  });
});
