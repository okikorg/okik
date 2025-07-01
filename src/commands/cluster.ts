import { Command } from 'commander';
import { color } from '../utils/ui';
import { spawnSync } from 'child_process';
import Table from 'cli-table3';

export const clusterCommand = new Command('cluster')
  .description('List all Kubernetes clusters or switch context')
  .argument('[context]', 'Context name to switch to')
  .action((context?: string) => {
    if (context) {
      const res = spawnSync('kubectl', ['config', 'use-context', context], { encoding: 'utf8' });
      if (res.status === 0) {
        console.log(color.success(`Switched to context ${context}`));
      } else {
        console.error(color.error(`Failed to switch context.`));
        if (res.stderr) console.error(res.stderr.trim());
      }
      return;
    }

    const res = spawnSync('kubectl', ['config', 'get-contexts', '-o', 'name'], { encoding: 'utf8' });
    if (res.status !== 0) {
      console.error(color.error('Failed to list contexts.'));
      if (res.stderr) console.error(res.stderr.trim());
      return;
    }

    const currentRes = spawnSync('kubectl', ['config', 'current-context'], { encoding: 'utf8' });
    const currentCtx = currentRes.stdout.trim();

    const contexts = res.stdout.split('\n').filter((l: string) => l);
    const table = new Table({ head: [color.accent('Context'), color.accent('Current')] });
    contexts.forEach((ctx: string) => table.push([ctx, ctx === currentCtx ? 'Yes' : '']));
    console.log(table.toString());
  });