import { Command } from 'commander';
import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import ora from 'ora';
import { v4 as uuidv4 } from 'uuid';

const spinner = ora();

export const initCommand = new Command('init')
  .description('Initialize the project with the required files and directories.')
  .action(async () => {
    const tasks: Array<{ description: string; fn: () => Promise<void> }> = [];

    const projectDirs = {
      SERVICES_DIR: '.okik/services',
      CACHE_DIR: '.okik/cache',
      CONFIG_DIR: '.okik/configs',
      TEMP_DIR: '.okik/temp',
      DOCKER_DIR: '.okik/docker',
    } as const;

    // 1. Create directories
    Object.values(projectDirs).forEach((dir) => {
      tasks.push({
        description: `Creating directory ${dir}`,
        fn: async () => {
          await fs.ensureDir(dir);
        },
      });
    });

    // 2. Generate Dockerfile stub if not exists
    tasks.push({
      description: 'Creating Dockerfile',
      fn: async () => {
        const dockerfilePath = path.join(projectDirs.DOCKER_DIR, 'Dockerfile');
        if (!(await fs.pathExists(dockerfilePath))) {
          const dockerfileContent = `# ---- Okik generated Dockerfile\nFROM python:3.11-slim\nCOPY requirements.txt /app/requirements.txt\nRUN pip install -r /app/requirements.txt\nCOPY . /app\nCMD [\"python\", \"main.py\"]\n`;
          await fs.writeFile(dockerfilePath, dockerfileContent, 'utf8');
        }
      },
    });

    // 3. Create credentials.json in home directory
    tasks.push({
      description: 'Creating credentials file with token',
      fn: async () => {
        const okikHomeDir = path.join(process.env.HOME || process.env.USERPROFILE || '.', 'okik');
        await fs.ensureDir(okikHomeDir);
        const credentialsPath = path.join(okikHomeDir, 'credentials.json');
        if (!(await fs.pathExists(credentialsPath))) {
          const token = uuidv4();
          await fs.writeJSON(credentialsPath, { token }, { spaces: 2 });
        }
      },
    });

    // 4. Create configs.json
    tasks.push({
      description: 'Creating configs.json file in config directory',
      fn: async () => {
        const configsPath = path.join(projectDirs.CONFIG_DIR, 'configs.json');
        if (!(await fs.pathExists(configsPath))) {
          await fs.writeJSON(configsPath, { image_name: '', app_name: '' }, { spaces: 2 });
        }
      },
    });

    for (const task of tasks) {
      spinner.start(task.description);
      try {
        await task.fn();
        spinner.succeed(task.description);
      } catch (err) {
        spinner.fail(`${task.description} - ${(err as Error).message}`);
        process.exitCode = 1;
        return;
      }
    }

    console.log(chalk.green.bold('\nProject initialized successfully.'));
  });