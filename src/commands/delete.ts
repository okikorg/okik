import { Command } from 'commander';
import { color } from '../utils/ui';
import { spawnSync } from 'child_process';
import { Confirm } from 'enquirer';

export const deleteCommand = new Command('delete')
  .description('Delete a deployment or service in the default namespace')
  .argument('<resource>', 'Resource type: deployment|service')
  .argument('<name>', 'Name of the resource')
  .action(async (resource: string, name: string) => {
    if (!['deployment', 'service'].includes(resource)) {
      console.error(color.error('Unsupported resource type.'));
      return;
    }

    const confirmPrompt = new Confirm({ name: 'confirm', message: `Delete ${resource} ${name}?` });
    const proceed = await confirmPrompt.run();
    if (!proceed) {
      console.log(color.warning('Deletion aborted.'));
      return;
    }

    const res = spawnSync('kubectl', ['delete', resource, name, '-n', 'default'], { encoding: 'utf8' });
    if (res.status === 0) {
      console.log(color.success(res.stdout.trim()));
    } else {
      console.error(color.error('Failed to delete resource.'));
      if (res.stderr) console.error(res.stderr.trim());
    }
  });