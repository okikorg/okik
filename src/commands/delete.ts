import { Command } from 'commander';
import chalk from 'chalk';
import { spawnSync } from 'child_process';
import { Confirm } from 'enquirer';

export const deleteCommand = new Command('delete')
  .description('Delete a deployment or service in the default namespace')
  .argument('<resource>', 'Resource type: deployment|service')
  .argument('<name>', 'Name of the resource')
  .action(async (resource: string, name: string) => {
    if (!['deployment', 'service'].includes(resource)) {
      console.error(chalk.red('Unsupported resource type.'));
      return;
    }

    const confirmPrompt = new Confirm({ name: 'confirm', message: `Delete ${resource} ${name}?` });
    const proceed = await confirmPrompt.run();
    if (!proceed) {
      console.log(chalk.yellow('Deletion aborted.'));
      return;
    }

    const res = spawnSync('kubectl', ['delete', resource, name, '-n', 'default'], { encoding: 'utf8' });
    if (res.status === 0) {
      console.log(chalk.green(res.stdout.trim()));
    } else {
      console.error(chalk.red('Failed to delete resource.'));
      if (res.stderr) console.error(res.stderr.trim());
    }
  });