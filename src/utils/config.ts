import { promises as fs } from 'fs';
import { join, dirname } from 'path';
import { v4 as uuidv4 } from 'uuid';
import { ProjectDir, CliConfig, CliConfigSchema } from '../types/index.js';
import { logInfo, logWarning, logError } from './logger.js';

export class ConfigManager {
  private configDir: string;
  private configPath: string;

  constructor(baseDir: string = process.cwd()) {
    this.configDir = join(baseDir, ProjectDir.CONFIG_DIR);
    this.configPath = join(this.configDir, 'config.json');
  }

  /**
   * Initialize project directories and configuration
   */
  async initProject(): Promise<void> {
    const directories = Object.values(ProjectDir);
    
    for (const dir of directories) {
      try {
        await fs.mkdir(dir, { recursive: true });
        logInfo(`Created directory: ${dir}`);
      } catch (error) {
        logError(`Failed to create directory ${dir}: ${error}`);
        throw error;
      }
    }

    // Create initial configuration
    await this.createInitialConfig();
    
    // Create credentials if not exists
    await this.createCredentials();
    
    // Create Dockerfile template
    await this.createDockerfile();
  }

  /**
   * Create initial configuration file
   */
  private async createInitialConfig(): Promise<void> {
    const defaultConfig: CliConfig = {
      imageName: '',
      appName: '',
      registry: 'okik.cloud',
      tag: 'latest'
    };

    try {
      await fs.writeFile(
        this.configPath,
        JSON.stringify(defaultConfig, null, 2)
      );
      logInfo('Created initial configuration file');
    } catch (error) {
      logError(`Failed to create configuration file: ${error}`);
      throw error;
    }
  }

  /**
   * Load configuration from file
   */
  async loadConfig(): Promise<CliConfig> {
    try {
      const configData = await fs.readFile(this.configPath, 'utf-8');
      const config = JSON.parse(configData);
      return CliConfigSchema.parse(config);
    } catch (error) {
      logWarning('Configuration file not found or invalid, using defaults');
      return CliConfigSchema.parse({});
    }
  }

  /**
   * Save configuration to file
   */
  async saveConfig(config: CliConfig): Promise<void> {
    try {
      await fs.mkdir(dirname(this.configPath), { recursive: true });
      await fs.writeFile(
        this.configPath,
        JSON.stringify(config, null, 2)
      );
      logInfo('Configuration saved');
    } catch (error) {
      logError(`Failed to save configuration: ${error}`);
      throw error;
    }
  }

  /**
   * Update configuration with new values
   */
  async updateConfig(updates: Partial<CliConfig>): Promise<CliConfig> {
    const currentConfig = await this.loadConfig();
    const newConfig = { ...currentConfig, ...updates };
    await this.saveConfig(newConfig);
    return newConfig;
  }

  /**
   * Create credentials file in home directory
   */
  private async createCredentials(): Promise<void> {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    const okikDir = join(homeDir, 'okik');
    const credentialsPath = join(okikDir, 'credentials.json');

    try {
      // Check if credentials already exist
      await fs.access(credentialsPath);
      logInfo('Credentials file already exists');
      return;
    } catch {
      // Credentials don't exist, create them
    }

    const credentials = {
      token: uuidv4(),
      created: new Date().toISOString()
    };

    try {
      await fs.mkdir(okikDir, { recursive: true });
      await fs.writeFile(
        credentialsPath,
        JSON.stringify(credentials, null, 2)
      );
      logInfo('Created credentials file');
    } catch (error) {
      logError(`Failed to create credentials: ${error}`);
      throw error;
    }
  }

  /**
   * Create Dockerfile template
   */
  private async createDockerfile(): Promise<void> {
    const dockerDir = ProjectDir.DOCKER_DIR;
    const dockerfilePath = join(dockerDir, 'Dockerfile');

    const dockerfileContent = `# Multi-stage Node.js Dockerfile for Okik
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src/ ./src/

# Build TypeScript
RUN npm run build

# Production stage
FROM node:18-alpine AS production

# Install okik CLI globally
RUN npm install -g okik

# Set working directory
WORKDIR /app

# Copy built application
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./

# Copy entry point
COPY . .

# Initialize okik
RUN okik init

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:3000/health || exit 1

# Start server
CMD ["okik", "server", "--dev", "--reload"]
`;

    try {
      await fs.writeFile(dockerfilePath, dockerfileContent);
      logInfo('Created Dockerfile template');
    } catch (error) {
      logError(`Failed to create Dockerfile: ${error}`);
      throw error;
    }
  }

  /**
   * Check if project is initialized
   */
  async isProjectInitialized(): Promise<boolean> {
    try {
      await fs.access(this.configPath);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get project directories
   */
  getProjectDirectories(): string[] {
    return Object.values(ProjectDir);
  }

  /**
   * Clean project (remove generated files)
   */
  async cleanProject(): Promise<void> {
    const directories = [
      ProjectDir.TEMP_DIR,
      ProjectDir.CACHE_DIR
    ];

    for (const dir of directories) {
      try {
        await fs.rm(dir, { recursive: true, force: true });
        logInfo(`Cleaned directory: ${dir}`);
      } catch (error) {
        logWarning(`Failed to clean directory ${dir}: ${error}`);
      }
    }
  }
}

/**
 * Global config manager instance
 */
export const configManager = new ConfigManager();

/**
 * Helper function to get configuration
 */
export async function getConfig(): Promise<CliConfig> {
  return configManager.loadConfig();
}

/**
 * Helper function to update configuration
 */
export async function updateConfig(updates: Partial<CliConfig>): Promise<CliConfig> {
  return configManager.updateConfig(updates);
}