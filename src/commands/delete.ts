import { Command } from 'commander';
import { color } from '../utils/ui';
import { spawnSync } from 'child_process';
import { confirm as askConfirm } from '../utils/prompt';
import { ValidationError, KubernetesDeployError } from '../utils/errors';

export const deleteCommand = new Command('delete')
  .description('Delete a deployment or service in the default namespace')
  .argument('<resource>', 'Resource type: deployment|service')
  .argument('<name>', 'Name of the resource')
  .action(async (resource: string, name: string) => {
    if (!['deployment', 'service'].includes(resource)) {
      throw new ValidationError('Unsupported resource type.');
    }

    const proceed = await askConfirm(`Delete ${resource} ${name}?`);
    if (!proceed) {
      console.log(color.warning('Deletion aborted.'));
      return;
    }

    const res = spawnSync('kubectl', ['delete', resource, name, '-n', 'default'], { encoding: 'utf8' });
    if (res.status === 0) {
      console.log(color.success(res.stdout.trim()));
    } else {
      throw new KubernetesDeployError(res.stderr || 'Failed to delete resource.');
    }
  });