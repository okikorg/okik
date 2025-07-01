import chalk from 'chalk';
import figlet from 'figlet';
import ora from 'ora';
import type { Ora } from 'ora';

export const color = {
  primary: chalk.hex('#00b894'),
  accent: chalk.cyan,
  warning: chalk.keyword('orange'),
  error: chalk.red,
  success: chalk.green,
  dim: chalk.dim,
};

export function renderBanner(): void {
  const banner = figlet.textSync('Okik', { font: 'ANSI Shadow' });
  console.log(color.primary.bold(banner));
  console.log(color.primary.bold('Simplify. Deploy. Scale.'));
  console.log(color.dim("Type 'okik --help' for more commands.\n"));
}

export function createSpinner(text: string): Ora {
  return ora({ text, spinner: 'dots' }).start();
}