import { Command } from 'commander';
import chalk from 'chalk';
import { spawnSync } from 'child_process';
import Table from 'cli-table3';

export const getCommand = new Command('get')
  .description('Get deployments or services in the default namespace')
  .argument('<resource>', 'Resource type: deployments|services')
  .action((resource: string) => {
    if (!['deployments', 'services'].includes(resource)) {
      console.error(chalk.red('Unsupported resource type.'));
      return;
    }

    const res = spawnSync('kubectl', ['get', resource, '-o', 'json', '-n', 'default'], { encoding: 'utf8' });
    if (res.status !== 0) {
      console.error(chalk.red('Failed to retrieve resources.'));
      if (res.stderr) console.error(res.stderr.trim());
      return;
    }

    try {
      const data = JSON.parse(res.stdout);
      const table = new Table({ head: ['Name', ...(resource === 'deployments' ? ['Replicas', 'Available'] : ['Type', 'Cluster IP', 'Ports'])] });

      data.items.forEach((item: any) => {
        if (resource === 'deployments') {
          table.push([
            item.metadata.name,
            item.spec.replicas?.toString() ?? '0',
            item.status.availableReplicas?.toString() ?? '0',
          ]);
        } else {
          const ports = item.spec.ports.map((p: any) => `${p.port}/${p.protocol}`).join(', ');
          table.push([
            item.metadata.name,
            item.spec.type,
            item.spec.clusterIP,
            ports,
          ]);
        }
      });
      console.log(table.toString());
    } catch (err) {
      console.error(chalk.red('Failed to parse kubectl output.'));
    }
  });