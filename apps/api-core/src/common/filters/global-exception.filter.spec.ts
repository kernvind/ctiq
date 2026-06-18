import { ArgumentsHost, BadRequestException, HttpStatus } from '@nestjs/common';
import { GqlArgumentsHost } from '@nestjs/graphql';
import { GraphQLError } from 'graphql';
import {
  PrismaClientKnownRequestError,
  PrismaClientValidationError,
  PrismaClientInitializationError,
} from '@repo/db';
import { GlobalExceptionFilter } from './global-exception.filter';

describe('GlobalExceptionFilter', () => {
  let filter: GlobalExceptionFilter;

  beforeEach(() => {
    filter = new GlobalExceptionFilter();
  });
  afterEach(() => jest.restoreAllMocks());

  // Invoke the GraphQL path and capture the thrown GraphQLError.
  function catchGraphql(exception: unknown): GraphQLError {
    const host = { getType: () => 'graphql' } as unknown as ArgumentsHost;
    jest.spyOn(GqlArgumentsHost, 'create').mockReturnValue({
      getContext: () => ({ req: { url: '/graphql' } }),
      getInfo: () => ({ fieldName: 'someField' }),
    } as unknown as GqlArgumentsHost);

    try {
      filter.catch(exception, host);
    } catch (e) {
      if (e instanceof GraphQLError) return e;
      throw e;
    }
    throw new Error('expected filter.catch to throw a GraphQLError');
  }

  describe('normalize / mapPrisma (GraphQL path)', () => {
    it('maps an HttpException to its own status + message', () => {
      const e = catchGraphql(new BadRequestException('bad input'));
      expect(e.message).toBe('bad input');
      expect(e.extensions.statusCode).toBe(HttpStatus.BAD_REQUEST);
      expect(e.extensions.code).toBe('BadRequestException');
    });

    it('maps Prisma P2002 (unique) to 409 DUPLICATE', () => {
      const e = catchGraphql(
        new PrismaClientKnownRequestError('dup', {
          code: 'P2002',
          clientVersion: '7.8.0',
        }),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.CONFLICT);
      expect(e.extensions.code).toBe('DUPLICATE');
      expect(e.message).toBe('A record already exists');
    });

    it('maps Prisma P2025 to 404 NOT_FOUND', () => {
      const e = catchGraphql(
        new PrismaClientKnownRequestError('x', {
          code: 'P2025',
          clientVersion: '7.8.0',
        }),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.NOT_FOUND);
      expect(e.extensions.code).toBe('NOT_FOUND');
    });

    it('maps Prisma P2003 to 400 FOREIGN_KEY_VIOLATION', () => {
      const e = catchGraphql(
        new PrismaClientKnownRequestError('x', {
          code: 'P2003',
          clientVersion: '7.8.0',
        }),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.BAD_REQUEST);
      expect(e.extensions.code).toBe('FOREIGN_KEY_VIOLATION');
    });

    it('maps an unknown Prisma code to 500 DATABASE_ERROR', () => {
      const e = catchGraphql(
        new PrismaClientKnownRequestError('x', {
          code: 'P9999',
          clientVersion: '7.8.0',
        }),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(e.extensions.code).toBe('DATABASE_ERROR');
    });

    it('maps PrismaClientValidationError to 400 VALIDATION_ERROR', () => {
      const e = catchGraphql(
        new PrismaClientValidationError('invalid', { clientVersion: '7.8.0' }),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.BAD_REQUEST);
      expect(e.extensions.code).toBe('VALIDATION_ERROR');
    });

    it('maps PrismaClientInitializationError to 503 DATABASE_UNAVAILABLE', () => {
      const e = catchGraphql(
        new PrismaClientInitializationError('db down', '7.8.0'),
      );
      expect(e.extensions.statusCode).toBe(HttpStatus.SERVICE_UNAVAILABLE);
      expect(e.extensions.code).toBe('DATABASE_UNAVAILABLE');
    });

    it('maps an unknown error to a generic 500', () => {
      const e = catchGraphql(new Error('boom'));
      expect(e.extensions.statusCode).toBe(HttpStatus.INTERNAL_SERVER_ERROR);
      expect(e.extensions.code).toBe('INTERNAL_SERVER_ERROR');
      expect(e.message).toBe('Something went wrong. Please try again.');
    });
  });

  describe('REST path', () => {
    function restHost(res: unknown): ArgumentsHost {
      return {
        getType: () => 'http',
        switchToHttp: () => ({
          getRequest: () => ({ url: '/health' }),
          getResponse: () => res,
        }),
      } as unknown as ArgumentsHost;
    }

    it('responds via .send() (Fastify-compatible) and masks 5xx detail', () => {
      const res = { status: jest.fn().mockReturnThis(), send: jest.fn() };
      filter.catch(new Error('secret internal detail'), restHost(res));

      expect(res.status).toHaveBeenCalledWith(500);
      const body = res.send.mock.calls[0][0];
      expect(body).toMatchObject({
        statusCode: 500,
        error: 'INTERNAL_SERVER_ERROR',
        message: 'An unexpected error occurred. Please try again.',
        path: '/health',
      });
      // The raw internal message must never reach the client.
      expect(body.message).not.toContain('secret internal detail');
    });

    it('passes 4xx messages through to the client', () => {
      const res = { status: jest.fn().mockReturnThis(), send: jest.fn() };
      filter.catch(
        new BadRequestException('username too short'),
        restHost(res),
      );

      expect(res.status).toHaveBeenCalledWith(400);
      expect(res.send.mock.calls[0][0]).toMatchObject({
        message: 'username too short',
        error: 'BadRequestException',
      });
    });
  });
});
