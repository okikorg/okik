import { Command } from 'commander';
import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import ora from 'ora';
import { v4 as uuidv4 } from 'uuid';
import Docker from 'dockerode';
import { exec } from 'child_process';
import { promisify } from 'util';

const docker = new Docker();
const execAsync = promisify(exec);
const spinner = ora();

interface BuildOptions {
  entryPoint: string;
  dockerFile: string;
  appName?: string;
  cloudPrefix?: string;
  registryId?: string;
  tag: string;
  verbose?: boolean;
  forceBuild?: boolean;
}

export const buildCommand = new Command('build')
  .description('Build the Docker image for your app')
  .option('-e, --entry-point <file>', 'Entry point file', 'main.py')
  .option('-d, --docker-file <file>', 'Dockerfile name', '.okik/docker/Dockerfile')
  .option('-a, --app-name <name>', 'Name of the Docker image')
  .option('-c, --cloud-prefix <prefix>', 'Prefix for the cloud service')
  .option('-r, --registry-id <id>', 'Registry ID')
  .option('-t, --tag <tag>', 'Tag for the Docker image', 'latest')
  .option('-v, --verbose', 'Verbose build output', false)
  .option('-f, --force-build', 'Force rebuild of the Docker image', false)
  .action(async (opts: BuildOptions) => {
    const start = Date.now();
    const tempDir = '.okik/temp';
    await fs.ensureDir(tempDir);

    const steps: string[] = [];

    // Validate entry point
    if (!(await fs.pathExists(opts.entryPoint))) {
      console.error(chalk.red(`Entry point file '${opts.entryPoint}' not found.`));
      process.exitCode = 1;
      return;
    }
    steps.push('Checked entry point file.');

    // Copy entry point and Dockerfile into tempDir
    await fs.copy(opts.entryPoint, path.join(tempDir, path.basename(opts.entryPoint)));
    steps.push('Copied entry point file.');

    if (!(await fs.pathExists(opts.dockerFile))) {
      console.error(chalk.red(`Dockerfile '${opts.dockerFile}' not found.`));
      process.exitCode = 1;
      return;
    }
    await fs.copy(opts.dockerFile, path.join(tempDir, path.basename(opts.dockerFile)));
    steps.push('Copied Dockerfile.');

    // Copy requirements.txt if present
    if (await fs.pathExists('requirements.txt')) {
      await fs.copy('requirements.txt', path.join(tempDir, 'requirements.txt'));
      steps.push('Copied requirements.txt.');
    }

    // Determine image name
    let dockerImageName: string;
    const configsPath = '.okik/configs/configs.json';
    await fs.ensureFile(configsPath);

    let existing: { image_name?: string; app_name?: string } = {};
    try {
      existing = await fs.readJSON(configsPath);
    } catch {
      /* ignore */
    }

    if (existing.image_name && !opts.forceBuild) {
      dockerImageName = existing.image_name;
      steps.push(`Using existing image name: ${dockerImageName}`);
    } else {
      const appName = opts.appName ?? `app-${uuidv4()}`;
      if (opts.cloudPrefix) {
        dockerImageName = `${opts.cloudPrefix}/${opts.registryId}/${appName}:${opts.tag}`;
      } else {
        dockerImageName = `okik.cloud/${opts.registryId}/${appName}:${opts.tag}`;
      }

      await fs.writeJSON(configsPath, { image_name: dockerImageName, app_name: appName }, { spaces: 2 });
    }

    // Build using docker CLI (simpler cross-platform than dockerode for complex builds)
    const buildCmd = opts.forceBuild
      ? `docker build --no-cache -t ${dockerImageName} -f ${path.join(tempDir, path.basename(opts.dockerFile))} ${tempDir}`
      : `docker build -t ${dockerImageName} -f ${path.join(tempDir, path.basename(opts.dockerFile))} ${tempDir}`;

    spinner.start('Building Docker image');
    try {
      const { stdout, stderr } = await execAsync(buildCmd);
      if (opts.verbose) {
        console.log(stdout);
        console.error(stderr);
      }
      spinner.succeed('Docker image built');
      steps.push(`Built Docker image '${dockerImageName}'.`);
    } catch (err: any) {
      spinner.fail('Docker build failed');
      console.error(chalk.red(err.stderr || err.message));
      process.exitCode = 1;
      return;
    }

    // Cleanup
    await fs.remove(tempDir);
    steps.push('Cleaned up temporary directory.');

    const elapsed = ((Date.now() - start) / 1000).toFixed(2);
    console.log(chalk.green(`Docker image '${dockerImageName}' built successfully in ${elapsed}s.`));

    if (!opts.verbose) {
      console.log(chalk.dim("Run with --verbose to see full build output."));
    }

    // Print steps
    for (const step of steps) {
      console.log(chalk.blue('- ' + step));
    }
  });