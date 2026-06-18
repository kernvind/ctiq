import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { GqlArgumentsHost } from '@nestjs/graphql';
import { Request, Response } from 'express';
import { GraphQLError } from 'graphql';

import {
  PrismaClientKnownRequestError,
  PrismaClientValidationError,
  PrismaClientInitializationError,
  PrismaClientRustPanicError,
} from '@repo/db';

@Catch()
export class GlobalExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(GlobalExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost) {
    const context = this.getContext(host);

    const normalized = this.normalize(exception);

    // 🔴 Always log safely (never assume request exists)
    this.logger.error(
      `${context.type} ${context.path} → ${normalized.status} (${normalized.errorType}): ${normalized.message}`,
      exception instanceof Error ? exception.stack : String(exception),
    );

    // 🟣 GRAPHQL PATH
    if (context.type === 'graphql') {
      throw new GraphQLError(normalized.message, {
        extensions: {
          code: normalized.errorType,
          statusCode: normalized.status,
          path: context.path,
        },
      });
    }

    // 🟢 REST PATH
    const res = context.response;
    // `.send()` (not `.json()`): the app runs on Fastify, whose reply has no `.json()`.
    // `.send(obj)` serializes to JSON on both Fastify and Express.
    res.status(normalized.status).send({
      statusCode: normalized.status,
      message: this.clientMessage(normalized.status, normalized.message),
      error: normalized.errorType,
      timestamp: new Date().toISOString(),
      path: context.path,
    });
  }

  // -----------------------------
  // CONTEXT NORMALIZATION (SAFE)
  // -----------------------------
  private getContext(host: ArgumentsHost) {
    // REST
    if (host.getType() === 'http') {
      const ctx = host.switchToHttp();
      const req = ctx.getRequest<Request>();
      const res = ctx.getResponse<Response>();

      return {
        type: 'rest' as const,
        request: req,
        response: res,
        path: req?.url ?? '',
      };
    }

    // GRAPHQL
    const gqlHost = GqlArgumentsHost.create(host);
    const gqlContext = gqlHost.getContext<{ req?: Request }>();

    return {
      type: 'graphql' as const,
      request: gqlContext?.req,
      response: undefined,
      // Explicitly assert the object shape before accessing the property
      // Cast to unknown record, then safely stringify the final result

      // eslint-disable-next-line @typescript-eslint/no-unsafe-member-access
      path: String(gqlHost.getInfo()?.fieldName ?? 'graphql'),
    };
  }

  // -----------------------------
  // NORMALIZER (PURE LOGIC)
  // -----------------------------
  private normalize(exception: unknown): {
    status: number;
    message: string;
    errorType: string;
  } {
    if (exception instanceof HttpException) {
      const response = exception.getResponse();
      const message =
        typeof response === 'string'
          ? response
          : ((response as { message?: string }).message ?? exception.message);
      return {
        status: exception.getStatus(),
        message,
        errorType: exception.name,
      };
    }

    if (exception instanceof PrismaClientKnownRequestError) {
      return this.mapPrisma(exception);
    }

    if (exception instanceof PrismaClientValidationError) {
      return {
        status: HttpStatus.BAD_REQUEST,
        message: 'Invalid request data',
        errorType: 'VALIDATION_ERROR',
      };
    }

    if (
      exception instanceof PrismaClientInitializationError ||
      exception instanceof PrismaClientRustPanicError
    ) {
      return {
        status: HttpStatus.SERVICE_UNAVAILABLE,
        message: 'Something went wrong. Please try again.',
        errorType: 'DATABASE_UNAVAILABLE',
      };
    }

    return {
      status: HttpStatus.INTERNAL_SERVER_ERROR,
      message: 'Something went wrong. Please try again.',
      errorType: 'INTERNAL_SERVER_ERROR',
    };
  }

  private mapPrisma(error: PrismaClientKnownRequestError) {
    switch (error.code) {
      case 'P2002':
        return {
          status: HttpStatus.CONFLICT,
          message: 'A record already exists',
          errorType: 'DUPLICATE',
        };

      case 'P2025':
        return {
          status: HttpStatus.NOT_FOUND,
          message: 'Record not found',
          errorType: 'NOT_FOUND',
        };

      case 'P2003':
        return {
          status: HttpStatus.BAD_REQUEST,
          message: 'Invalid reference',
          errorType: 'FOREIGN_KEY_VIOLATION',
        };

      default:
        return {
          status: HttpStatus.INTERNAL_SERVER_ERROR,
          message: 'Something went wrong. Please try again.',
          errorType: 'DATABASE_ERROR',
        };
    }
  }

  private clientMessage(status: number, message: string) {
    if (status >= 500) {
      return 'An unexpected error occurred. Please try again.';
    }
    return message;
  }
}
