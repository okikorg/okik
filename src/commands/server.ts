import { Command } from 'commander';
import { color } from '../utils/ui';
import { spawn } from 'child_process';
import path from 'path';
import os from 'os';

interface ServerOptions {
  entryPoint: string;
  reload: boolean;
  host: string;
  port: number;
  dev: boolean;
  logLevel: string;
}

export const serverCommand = new Command('server')
  .description('Serve the FastAPI app specified by the entry point file using Uvicorn.')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.py')
  .option('-r, --reload', 'Enable auto-reload (only in dev)', false)
  .option('-h, --host <host>', 'Host address', '0.0.0.0')
  .option('-p, --port <port>', 'Port number', (v: string) => parseInt(v, 10), 3000)
  .option('-d, --dev', 'Run in development mode', false)
  .option('-l, --log-level <level>', 'Log level', 'info')
  .action((opts: ServerOptions) => {
    const entryPoint = opts.entryPoint;
    const moduleName = path.basename(entryPoint, path.extname(entryPoint));

    // Workers calculation
    const workers = opts.dev ? 1 : Math.min(os.cpus().length, 8);

    const args = [
      '-m',
      'uvicorn',
      `${moduleName}:app`,
      '--host',
      opts.host,
      '--port',
      String(opts.port),
      '--log-level',
      opts.logLevel,
    ];

    if (opts.reload && opts.dev) {
      args.push('--reload');
    }

    if (!opts.dev) {
      args.push('--workers', String(workers));
    }

    console.log(color.warning('Starting Uvicorn server...'));
    console.log(color.success(`Host: ${opts.host}\nPort: ${opts.port}\nReload: ${opts.reload && opts.dev}\nEnvironment: ${opts.dev ? 'Development' : 'Production'}\nWorkers: ${workers}`));

    // Spawn the python process
    const proc = spawn('python', args, {
      stdio: 'inherit',
    });

    proc.on('close', (code: number | null) => {
      if (code === 0) {
        console.log(color.success('Server stopped.'));
      } else {
        console.error(color.error(`Server exited with code ${code}`));
      }
    });
  });