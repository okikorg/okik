import { Command } from 'commander';
import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { Select, Confirm } from 'enquirer';
import ora from 'ora';
import { spawnSync } from 'child_process';
import yaml from 'yaml';
import Table from 'cli-table3';

interface DeployOptions {
  entryPoint: string; // kept for parity, but unused in deploy
}

export const deployCommand = new Command('deploy')
  .description('Deploy the application YAML configs to Kubernetes')
  .option('-e, --entry-point <file>', 'Entry point file (unused in deploy)', 'main.py')
  .action(async (_opts: DeployOptions) => {
    const servicesDir = path.join('.okik', 'services', 'k8');
    if (!(await fs.pathExists(servicesDir))) {
      console.error(chalk.red('No services directory found. Run okik init first.'));
      return;
    }

    const files = (await fs.readdir(servicesDir)).filter((f: string) => f.endsWith('.yaml') || f.endsWith('.yml'));
    if (!files.length) {
      console.error(chalk.red('No YAML configuration files found.'));
      return;
    }

    const selectPrompt = new Select({
      name: 'file',
      message: 'Select a YAML file to deploy',
      choices: files,
    });

    const selected = await selectPrompt.run();
    if (!selected) {
      console.log(chalk.yellow('No file selected. Deployment cancelled.'));
      return;
    }

    const yamlPath = path.join(servicesDir, selected);
    const docContent = await fs.readFile(yamlPath, 'utf8');

    // Display YAML summary table for docs inside file
    const docs = yaml.parseAllDocuments(docContent).map((d) => d.toJSON());
    const table = new Table({ head: ['Kind', 'Name'] });
    docs.forEach((d: any) => table.push([d.kind, d.metadata?.name]));
    console.log(chalk.cyan('\nResources to be deployed:'));
    console.log(table.toString());

    const confirm = new Confirm({ name: 'confirm', message: 'Continue with deployment?' });
    const proceed = await confirm.run();
    if (!proceed) {
      console.log(chalk.yellow('Deployment cancelled.'));
      return;
    }

    const spinner = ora('Applying configuration').start();
    // Use kubectl apply -f yamlPath
    const res = spawnSync('kubectl', ['apply', '-f', yamlPath], { encoding: 'utf8' });
    spinner.stop();

    if (res.status === 0) {
      console.log(chalk.green('Deployment applied successfully.'));
      console.log(res.stdout.trim());
    } else {
      console.error(chalk.red('Failed to apply Kubernetes manifest.'));
      if (res.stderr) console.error(res.stderr.trim());
    }
  });