import Enquirer from 'enquirer';
const { Confirm, Select, Input } = Enquirer as any;
import { color } from './ui';

export async function confirm(message: string): Promise<boolean> {
  const prompt = new Confirm({
    name: 'confirm',
    message: color.accent(message),
  });
  return prompt.run();
}

export async function select<T extends string>(message: string, choices: T[]): Promise<T> {
  const prompt = new Select({
    name: 'select',
    message: color.accent(message),
    choices,
  });
  return prompt.run() as Promise<T>;
}

export async function input(message: string, initial = ''): Promise<string> {
  const prompt = new Input({ name: 'input', message: color.accent(message), initial });
  return prompt.run();
}