import { z } from 'zod';

// ===== ACCELERATOR TYPES =====
export enum AcceleratorType {
  CUDA = 'cuda',
  CPU = 'cpu',
  TPU = 'tpu',
  A40 = 'A40',
  A100 = 'A100',
  V100 = 'V100',
  T4 = 'T4'
}

export enum AcceleratorDevice {
  CUDA = 'cuda',
  CPU = 'cpu',
  MPS = 'mps'
}

export const AcceleratorConfigSchema = z.object({
  type: z.nativeEnum(AcceleratorType),
  device: z.nativeEnum(AcceleratorDevice),
  count: z.number().min(1).default(1),
  memory: z.number().min(1)
});

export type AcceleratorConfig = z.infer<typeof AcceleratorConfigSchema>;

// ===== SERVICE CONFIGURATION =====
export const ServiceConfigSchema = z.object({
  accelerator: AcceleratorConfigSchema
});

export type ServiceConfig = z.infer<typeof ServiceConfigSchema>;

// ===== BACKEND TYPES =====
export enum BackendType {
  K8S = 'k8s',
  OKIK = 'okik',
  RAY = 'ray',
  SKY = 'sky',
  DOCKER = 'docker'
}

export const ProvisioningBackendSchema = z.object({
  backend: z.nativeEnum(BackendType)
});

export type ProvisioningBackend = z.infer<typeof ProvisioningBackendSchema>;

// ===== PROJECT DIRECTORIES =====
export enum ProjectDir {
  SERVICES_DIR = '.okik/services',
  CACHE_DIR = '.okik/cache',
  CONFIG_DIR = '.okik/configs',
  TEMP_DIR = '.okik/temp',
  DOCKER_DIR = '.okik/docker'
}

// ===== SERVICE DECORATORS =====
export interface ServiceOptions {
  replicas?: number;
  resources?: ServiceConfig | Record<string, any>;
  backend?: BackendType;
  port?: number;
  name?: string;
}

export interface EndpointOptions {
  stream?: boolean;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path?: string;
}

// ===== FASTIFY/EXPRESS SERVER TYPES =====
export interface ServerOptions {
  host: string;
  port: number;
  dev: boolean;
  reload: boolean;
  logLevel: string;
  workers: number;
}

export interface RouteInfo {
  path: string;
  method: string;
  handler: string;
  service: string;
}

// ===== CLI CONFIGURATION =====
export interface CliConfig {
  imageName: string;
  appName: string;
  registry: string;
  tag: string;
}

export const CliConfigSchema = z.object({
  imageName: z.string().default(''),
  appName: z.string().default(''),
  registry: z.string().default('okik.cloud'),
  tag: z.string().default('latest')
});

// ===== KUBERNETES TYPES =====
export interface K8sResource {
  apiVersion: string;
  kind: string;
  metadata: {
    name: string;
    labels?: Record<string, string>;
    annotations?: Record<string, string>;
  };
  spec?: any;
}

export interface DeploymentInfo {
  name: string;
  replicas: number;
  availableReplicas: number;
  namespace: string;
  image: string;
}

export interface ServiceInfo {
  name: string;
  type: string;
  clusterIP: string;
  ports: Array<{ port: number; protocol: string }>;
  namespace: string;
}

// ===== BUILD CONFIGURATION =====
export interface BuildOptions {
  entryPoint: string;
  dockerFile: string;
  appName?: string;
  cloudPrefix?: string;
  registryId?: string;
  tag: string;
  verbose: boolean;
  forceBuild: boolean;
}

// ===== DEPLOY CONFIGURATION =====
export interface DeployOptions {
  entryPoint: string;
  namespace: string;
  yamlFile?: string;
  dryRun: boolean;
}

// ===== METADATA FOR DECORATORS =====
export const SERVICE_METADATA_KEY = Symbol('service');
export const ENDPOINT_METADATA_KEY = Symbol('endpoint');

export interface ServiceMetadata {
  options: ServiceOptions;
  className: string;
  methods: EndpointMetadata[];
}

export interface EndpointMetadata {
  methodName: string;
  options: EndpointOptions;
  originalMethod: Function;
}

// ===== ERROR TYPES =====
export class OkikError extends Error {
  constructor(message: string, public code?: string) {
    super(message);
    this.name = 'OkikError';
  }
}

export class ValidationError extends OkikError {
  constructor(message: string, public field?: string) {
    super(message, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
  }
}

export class ConfigError extends OkikError {
  constructor(message: string) {
    super(message, 'CONFIG_ERROR');
    this.name = 'ConfigError';
  }
}

export class DeploymentError extends OkikError {
  constructor(message: string) {
    super(message, 'DEPLOYMENT_ERROR');
    this.name = 'DeploymentError';
  }
}

// ===== LOG LEVELS =====
export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error'
}

// ===== TUI TYPES =====
export interface TUITheme {
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  muted: string;
}

export interface ProgressStep {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  details?: string;
}

export interface InteractiveChoice {
  name: string;
  value: string;
  description?: string;
  disabled?: boolean;
}