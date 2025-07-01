import { Command } from 'commander';
import fs from 'fs-extra';
import path from 'path';
import { color } from '../utils/ui';
import { confirm as askConfirm, select } from '../utils/prompt';
import { spawnSync } from 'child_process';
import yaml from 'yaml';
import Table from 'cli-table3';
import { createSpinner } from '../utils/ui';

interface DeployOptions {
  entryPoint: string; // kept for parity, but unused in deploy
}

export const deployCommand = new Command('deploy')
  .description('Deploy the application YAML configs to Kubernetes')
  .option('-e, --entry-point <file>', 'Entry point file (unused in deploy)', 'main.py')
  .action(async (_opts: DeployOptions) => {
    const servicesDir = path.join('.okik', 'services', 'k8');
    if (!(await fs.pathExists(servicesDir))) {
      console.error(color.error('No services directory found. Run okik init first.'));
      return;
    }

    const files = (await fs.readdir(servicesDir)).filter((f: string) => f.endsWith('.yaml') || f.endsWith('.yml'));
    if (!files.length) {
      console.error(color.error('No YAML configuration files found.'));
      return;
    }

    const selected = await select('Select a YAML file to deploy', files);
    if (!selected) {
      console.log(color.warning('No file selected. Deployment cancelled.'));
      return;
    }

    const yamlPath = path.join(servicesDir, selected);
    const docContent = await fs.readFile(yamlPath, 'utf8');

    // Display YAML summary table for docs inside file
    const docs = yaml.parseAllDocuments(docContent).map((d) => d.toJSON());
    const table = new Table({ head: [color.accent('Kind'), color.accent('Name')] });
    docs.forEach((d: any) => table.push([d.kind, d.metadata?.name]));
    console.log(color.accent('\nResources to be deployed:'));
    console.log(table.toString());

    const proceed = await askConfirm('Continue with deployment?');
    if (!proceed) {
      console.log(color.warning('Deployment cancelled.'));
      return;
    }

    const spinner = createSpinner('Applying configuration');
    // Use kubectl apply -f yamlPath
    const res = spawnSync('kubectl', ['apply', '-f', yamlPath], { encoding: 'utf8' });
    spinner.stop();

    if (res.status === 0) {
      console.log(color.success('Deployment applied successfully.'));
      console.log(res.stdout.trim());
    } else {
      console.error(color.error('Failed to apply Kubernetes manifest.'));
      if (res.stderr) console.error(res.stderr.trim());
    }
  });