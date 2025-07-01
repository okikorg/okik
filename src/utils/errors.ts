import { color } from './ui';

declare const process: NodeJS.Process;

/**
 * Base class for all CLI errors. These errors should be caught at the top level and
 * reported nicely to the user, then cause a non-zero exit code.
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

export class DockerError extends CliError {
  constructor(message: string) {
    super(`Docker error: ${message}`);
  }
}

export class KubernetesError extends CliError {
  constructor(message: string) {
    super(`Kubernetes error: ${message}`);
  }
}

export class ValidationError extends CliError {
  constructor(message: string) {
    super(`Validation error: ${message}`);
  }
}

/**
 * Utility that prints the error nicely and exits. This is re-exported so callers
 * can simply `catch(handleError)`.
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