import 'reflect-metadata';
import {
  ServiceOptions,
  EndpointOptions,
  ServiceMetadata,
  EndpointMetadata,
  SERVICE_METADATA_KEY,
  ENDPOINT_METADATA_KEY,
  BackendType,
  ServiceConfig,
  ServiceConfigSchema,
  ValidationError
} from '../types/index.js';

// Global registry to store service metadata
const serviceRegistry = new Map<string, ServiceMetadata>();

/**
 * Service decorator - marks a class as a deployable service
 * @param options Service configuration options
 */
export function service(options: ServiceOptions = {}) {
  return function <T extends { new (...args: any[]): {} }>(target: T) {
    const {
      replicas = 1,
      resources = {},
      backend = BackendType.OKIK,
      port = 3000,
      name
    } = options;

    // Validate replicas
    if (!Number.isInteger(replicas) || replicas < 1) {
      throw new ValidationError('Replicas must be a positive integer', 'replicas');
    }

    // Validate and parse resources if provided
    let validatedResources: ServiceConfig | undefined;
    if (resources && Object.keys(resources).length > 0) {
      try {
        validatedResources = ServiceConfigSchema.parse(resources);
      } catch (error) {
        throw new ValidationError(`Invalid resource configuration: ${error}`, 'resources');
      }
    }

    // Get existing endpoint metadata from methods
    const endpoints: EndpointMetadata[] = [];
    const prototype = target.prototype;
    
    // Scan prototype for endpoint metadata
    Object.getOwnPropertyNames(prototype).forEach(methodName => {
      if (methodName !== 'constructor') {
        const endpointOptions = Reflect.getMetadata(ENDPOINT_METADATA_KEY, prototype, methodName);
        if (endpointOptions) {
          endpoints.push({
            methodName,
            options: endpointOptions,
            originalMethod: prototype[methodName]
          });
        }
      }
    });

    const serviceName = name || target.name;
    const metadata: ServiceMetadata = {
      options: {
        replicas,
        resources: validatedResources,
        backend,
        port,
        name: serviceName
      },
      className: target.name,
      methods: endpoints
    };

    // Store metadata
    Reflect.defineMetadata(SERVICE_METADATA_KEY, metadata, target);
    serviceRegistry.set(serviceName, metadata);

    return target;
  };
}

/**
 * Endpoint decorator - marks a method as an API endpoint
 * @param options Endpoint configuration options
 */
export function endpoint(options: EndpointOptions = {}) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const {
      stream = false,
      method = 'POST',
      path
    } = options;

    const endpointOptions: EndpointOptions = {
      stream,
      method,
      path: path || `/${propertyKey}`
    };

    // Store endpoint metadata
    Reflect.defineMetadata(ENDPOINT_METADATA_KEY, endpointOptions, target, propertyKey);
    
    return descriptor;
  };
}

/**
 * Get service metadata for a class
 */
export function getServiceMetadata(target: any): ServiceMetadata | undefined {
  return Reflect.getMetadata(SERVICE_METADATA_KEY, target);
}

/**
 * Get endpoint metadata for a method
 */
export function getEndpointMetadata(target: any, propertyKey: string): EndpointOptions | undefined {
  return Reflect.getMetadata(ENDPOINT_METADATA_KEY, target, propertyKey);
}

/**
 * Get all registered services
 */
export function getAllServices(): Map<string, ServiceMetadata> {
  return new Map(serviceRegistry);
}

/**
 * Get service by name
 */
export function getService(name: string): ServiceMetadata | undefined {
  return serviceRegistry.get(name);
}

/**
 * Clear service registry (useful for testing)
 */
export function clearServiceRegistry(): void {
  serviceRegistry.clear();
}

/**
 * Validate service class has required methods
 */
export function validateServiceClass(target: any): void {
  const metadata = getServiceMetadata(target);
  if (!metadata) {
    throw new ValidationError(`Class ${target.name} is not decorated with @service`);
  }

  if (metadata.methods.length === 0) {
    throw new ValidationError(`Service ${target.name} has no @endpoint methods`);
  }
}

/**
 * Get route information for all services
 */
export function getRoutes(): Array<{
  service: string;
  path: string;
  method: string;
  handler: string;
}> {
  const routes: Array<{
    service: string;
    path: string;
    method: string;
    handler: string;
  }> = [];

  serviceRegistry.forEach((metadata, serviceName) => {
    metadata.methods.forEach(endpoint => {
      routes.push({
        service: serviceName,
        path: `/${serviceName.toLowerCase()}${endpoint.options.path}`,
        method: endpoint.options.method || 'POST',
        handler: endpoint.methodName
      });
    });
  });

  return routes;
}

// Export the registry for access in other modules
export { serviceRegistry };