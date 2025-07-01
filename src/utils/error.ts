/// <reference types="node" />
import { color } from './ui';

export class CliError extends Error {
  public readonly exitCode: number;
  constructor(message: string, exitCode = 1) {
    super(message);
    this.exitCode = exitCode;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export function handleError(err: unknown): void {
  if (err instanceof CliError) {
    console.error(color.error(`Error: ${err.message}`));
    process.exit(err.exitCode);
  } else if (err instanceof Error) {
    console.error(color.error(`Unexpected error: ${err.message}`));
    if (process.env.DEBUG) console.error(err.stack);
    process.exit(1);
  } else {
    console.error(color.error('An unknown error occurred.'));
    process.exit(1);
  }
}