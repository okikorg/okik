/// <reference types="node" />
import { color } from './ui';

/**
 * Base error for all CLI related failures
 */
export class CliError extends Error {
  constructor(message: string, public readonly exitCode: number = 1) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class FileNotFoundError extends CliError {
  constructor(file: string) {
    super(`File not found: ${file}`);
  }
}

/**
 * Docker errors
 */
export class DockerBuildError extends CliError {
  constructor(message: string) {
    super(`Docker build error: ${message}`);
  }
}

export class DockerRunError extends CliError {
  constructor(message: string) {
    super(`Docker run error: ${message}`);
  }
}

/**
 * Kubernetes errors
 */
export class KubernetesDeployError extends CliError {
  constructor(message: string) {
    super(`Kubernetes deploy error: ${message}`);
  }
}

export class KubernetesConfigError extends CliError {
  constructor(message: string) {
    super(`Kubernetes config error: ${message}`);
  }
}

/**
 * Validation / Configuration
 */
export class ValidationError extends CliError {
  constructor(message: string) {
    super(`Validation error: ${message}`);
  }
}

export class ConfigurationError extends CliError {
  constructor(message: string) {
    super(`Configuration error: ${message}`);
  }
}

/**
 * Runtime/network errors
 */
export class NetworkError extends CliError {
  constructor(message: string) {
    super(`Network error: ${message}`);
  }
}

export class TimeoutError extends CliError {
  constructor(message: string) {
    super(`Timeout error: ${message}`);
  }
}

/**
 * Centralised error handler – use at program entry
 */
export function handleError(err: unknown): void {
  if (err instanceof CliError) {
    console.error(color.error(err.message));
    process.exit(err.exitCode);
  }

  if (err instanceof Error) {
    console.error(color.error(`Unexpected error: ${err.message}`));
    if (process.env.DEBUG) console.error(err.stack);
  } else {
    console.error(color.error('An unknown error occurred.'));
  }

  process.exit(1);
}