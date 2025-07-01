#!/usr/bin/env node
import { Command } from 'commander';
import { renderBanner } from './utils/ui';
import { initCommand } from './commands/init';
import { buildCommand } from './commands/build';
import { serverCommand } from './commands/server';
import { routesCommand } from './commands/routes';
import { deployCommand } from './commands/deploy';
import { getCommand } from './commands/get';
import { deleteCommand } from './commands/delete';
import { clusterCommand } from './commands/cluster';
import { handleError } from './utils/error';
// Import other commands as they are implemented

const program = new Command();

// Banner
renderBanner();

program
  .name('okik')
  .description('Okik CLI – Simplify. Deploy. Scale.')
  .version('0.1.0');

// Register commands
program.addCommand(initCommand);
program.addCommand(buildCommand);
program.addCommand(serverCommand);
program.addCommand(routesCommand);
program.addCommand(deployCommand);
program.addCommand(getCommand);
program.addCommand(deleteCommand);
program.addCommand(clusterCommand);

program.parseAsync(process.argv).catch(handleError);