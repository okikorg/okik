#!/usr/bin/env node

import { Command } from 'commander';
import figlet from 'figlet';
import { printBanner, logInfo, logError, formatError } from './utils/logger.js';
import { configManager } from './utils/config.js';
import { OkikServer } from './server/index.js';
import { getRoutes, getAllServices } from './decorators/index.js';
import { version } from '../package.json';

const program = new Command();

// Configure main program
program
  .name('okik')
  .description('A modern CLI tool to simplify deployment and scaling of services on cloud platforms')
  .version(version)
  .configureHelp({
    sortSubcommands: true,
    showGlobalOptions: true
  });

// Show banner when no command is provided
program.hook('preAction', (thisCommand) => {
  if (thisCommand.args.length === 0 && process.argv.length === 2) {
    printBanner();
  }
});

// Init command
program
  .command('init')
  .description('Initialize a new Okik project with required files and directories')
  .option('--force', 'Force initialization even if project already exists')
  .action(async (options) => {
    try {
      logInfo('Initializing Okik project...');
      
      if (!options.force && await configManager.isProjectInitialized()) {
        logInfo('Project is already initialized. Use --force to reinitialize.');
        return;
      }
      
      await configManager.initProject();
      logInfo('✅ Project initialized successfully!');
      
      console.log('\nNext steps:');
      console.log('1. Create your service classes with @service and @endpoint decorators');
      console.log('2. Run "okik server --dev" to start development server');
      console.log('3. Run "okik build" to build your application for deployment');
      
    } catch (error) {
      formatError(error as Error, 'Failed to initialize project');
      process.exit(1);
    }
  });

// Server command
program
  .command('server')
  .alias('serve')
  .description('Start the development or production server')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.js')
  .option('-h, --host <host>', 'Host address', '0.0.0.0')
  .option('-p, --port <port>', 'Port number', '3000')
  .option('-d, --dev', 'Run in development mode', false)
  .option('-r, --reload', 'Enable auto-reload', false)
  .option('-l, --log-level <level>', 'Log level', 'info')
  .option('-w, --workers <count>', 'Number of worker processes', '1')
  .action(async (options) => {
    try {
      const server = new OkikServer();
      
      // In a real implementation, you'd dynamically import and register services here
      // For now, we'll demonstrate with the server starting
      
      const serverOptions = {
        host: options.host,
        port: parseInt(options.port),
        dev: options.dev,
        reload: options.reload,
        logLevel: options.logLevel,
        workers: parseInt(options.workers)
      };
      
      await server.start(serverOptions);
      
      // Handle graceful shutdown
      process.on('SIGINT', async () => {
        logInfo('Received SIGINT, shutting down gracefully...');
        await server.stop();
        process.exit(0);
      });
      
    } catch (error) {
      formatError(error as Error, 'Failed to start server');
      process.exit(1);
    }
  });

// Routes command
program
  .command('routes')
  .description('Display all registered routes and endpoints')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.js')
  .option('--json', 'Output as JSON', false)
  .action(async (options) => {
    try {
      // In a real implementation, you'd import the entry point file here
      // to ensure all decorators are registered
      
      const routes = getRoutes();
      const services = getAllServices();
      
      if (options.json) {
        console.log(JSON.stringify({ routes: routes, services: Array.from(services.entries()) }, null, 2));
        return;
      }
      
      if (routes.length === 0) {
        logInfo('No routes found. Make sure your services are decorated with @service and methods with @endpoint.');
        return;
      }
      
      console.log('\n📋 Application Routes\n');
      
      // Group routes by service
      const routesByService = routes.reduce((acc, route) => {
        if (!acc[route.service]) {
          acc[route.service] = [];
        }
        acc[route.service].push(route);
        return acc;
      }, {} as Record<string, typeof routes>);
      
      Object.entries(routesByService).forEach(([service, serviceRoutes]) => {
        console.log(`🔧 ${service.toUpperCase()} Service`);
        serviceRoutes.forEach(route => {
          console.log(`   ${route.method.padEnd(6)} ${route.path} → ${route.handler}`);
        });
        console.log();
      });
      
    } catch (error) {
      formatError(error as Error, 'Failed to display routes');
      process.exit(1);
    }
  });

// Build command
program
  .command('build')
  .description('Build Docker image for your application')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.js')
  .option('-d, --docker-file <file>', 'Dockerfile path', '.okik/docker/Dockerfile')
  .option('-a, --app-name <name>', 'Application name')
  .option('-t, --tag <tag>', 'Image tag', 'latest')
  .option('-r, --registry <registry>', 'Container registry')
  .option('-v, --verbose', 'Verbose output', false)
  .option('-f, --force', 'Force rebuild', false)
  .action(async (options) => {
    try {
      logInfo('Building Docker image...');
      
      // Implementation would go here
      // For now, just show what would be built
      
      const config = await configManager.loadConfig();
      const appName = options.appName || config.appName || `okik-app-${Date.now()}`;
      const tag = options.tag;
      const registry = options.registry || config.registry;
      
      logInfo(`App Name: ${appName}`);
      logInfo(`Tag: ${tag}`);
      logInfo(`Registry: ${registry}`);
      logInfo(`Docker File: ${options.dockerFile}`);
      
      // Update config with build information
      await configManager.updateConfig({
        appName,
        imageName: `${registry}/${appName}:${tag}`,
        tag
      });
      
      logInfo('✅ Build configuration updated');
      
    } catch (error) {
      formatError(error as Error, 'Failed to build image');
      process.exit(1);
    }
  });

// Deploy command
program
  .command('deploy')
  .description('Deploy application to Kubernetes cluster')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.js')
  .option('-n, --namespace <namespace>', 'Kubernetes namespace', 'default')
  .option('-f, --file <file>', 'YAML configuration file')
  .option('--dry-run', 'Show what would be deployed without actually deploying', false)
  .action(async (options) => {
    try {
      logInfo('Deploying application...');
      
      // Implementation would use Kubernetes client
      logInfo(`Namespace: ${options.namespace}`);
      if (options.file) {
        logInfo(`Configuration file: ${options.file}`);
      }
      if (options.dryRun) {
        logInfo('Dry run mode - no actual deployment');
      }
      
      logInfo('✅ Deployment would be initiated here');
      
    } catch (error) {
      formatError(error as Error, 'Failed to deploy');
      process.exit(1);
    }
  });

// Get command (for Kubernetes resources)
program
  .command('get <resource>')
  .description('Get Kubernetes resources (deployments, services, pods)')
  .option('-n, --namespace <namespace>', 'Kubernetes namespace', 'default')
  .option('--json', 'Output as JSON', false)
  .action(async (resource, options) => {
    try {
      logInfo(`Getting ${resource} from namespace: ${options.namespace}`);
      
      // Implementation would use Kubernetes client
      logInfo('✅ Resource information would be displayed here');
      
    } catch (error) {
      formatError(error as Error, `Failed to get ${resource}`);
      process.exit(1);
    }
  });

// Delete command
program
  .command('delete <resource> <name>')
  .description('Delete Kubernetes resources')
  .option('-n, --namespace <namespace>', 'Kubernetes namespace', 'default')
  .option('-f, --force', 'Force deletion', false)
  .action(async (resource, name, options) => {
    try {
      logInfo(`Deleting ${resource}/${name} from namespace: ${options.namespace}`);
      
      // Implementation would use Kubernetes client
      logInfo('✅ Resource would be deleted here');
      
    } catch (error) {
      formatError(error as Error, `Failed to delete ${resource}/${name}`);
      process.exit(1);
    }
  });

// Cluster command
program
  .command('cluster [context]')
  .description('List or switch Kubernetes cluster contexts')
  .action(async (context) => {
    try {
      if (context) {
        logInfo(`Switching to cluster context: ${context}`);
      } else {
        logInfo('Listing available cluster contexts');
      }
      
      // Implementation would use Kubernetes client
      logInfo('✅ Cluster operation would be performed here');
      
    } catch (error) {
      formatError(error as Error, 'Failed to manage cluster');
      process.exit(1);
    }
  });

// Clean command
program
  .command('clean')
  .description('Clean temporary files and caches')
  .option('--all', 'Clean all generated files including configs', false)
  .action(async (options) => {
    try {
      await configManager.cleanProject();
      
      if (options.all) {
        logInfo('Performing deep clean...');
        // Additional cleanup logic
      }
      
      logInfo('✅ Project cleaned successfully');
      
    } catch (error) {
      formatError(error as Error, 'Failed to clean project');
      process.exit(1);
    }
  });

// Error handling
program.exitOverride();

try {
  program.parse();
} catch (error) {
  if (error instanceof Error) {
    formatError(error);
  }
  process.exit(1);
}

export { program };