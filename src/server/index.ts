import fastify, { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { getAllServices } from '../decorators/index.js';
import { ServerOptions } from '../types/index.js';
import { logInfo, logError, logSuccess, printBox } from '../utils/logger.js';

interface RequestBody {
  [key: string]: any;
}

export class OkikServer {
  private app: FastifyInstance;
  private services: Map<string, any> = new Map();

  constructor() {
    this.app = fastify({
      logger: false // We handle logging ourselves
    });
    
    this.setupHealthCheck();
  }

  private setupHealthCheck(): void {
    this.app.get('/health', async (request, reply) => {
      return { status: 'ok', timestamp: new Date().toISOString() };
    });
  }

  public async registerServices(): Promise<void> {
    const serviceMetadata = getAllServices();
    
    for (const [serviceName, metadata] of serviceMetadata) {
      try {
        // Create service instance - in a real implementation, you'd need to 
        // import and instantiate the actual service class
        logInfo(`Registering service: ${serviceName}`);
        
        for (const endpoint of metadata.methods) {
          const routePath = `/${serviceName.toLowerCase()}${endpoint.options.path}`;
          const method = endpoint.options.method?.toLowerCase() as 'get' | 'post' | 'put' | 'delete' | 'patch';
          
          if (endpoint.options.stream) {
            // Handle streaming endpoints
            this.app[method || 'post'](routePath, async (request: FastifyRequest, reply: FastifyReply) => {
              try {
                const serviceInstance = this.getServiceInstance(serviceName);
                const methodFn = serviceInstance[endpoint.methodName];
                
                // Parse request body for parameters
                const params = this.parseRequestParams(request);
                
                // Call the method and get the async generator
                const generator = await methodFn.call(serviceInstance, ...params);
                
                // Set headers for streaming
                reply.type('text/plain; charset=utf-8');
                reply.header('Cache-Control', 'no-cache');
                reply.header('Connection', 'keep-alive');
                
                // Stream the response
                for await (const chunk of generator) {
                  reply.raw.write(chunk);
                }
                
                reply.raw.end();
              } catch (error) {
                logError(`Error in streaming endpoint ${routePath}: ${error}`);
                reply.code(500).send({ error: 'Internal server error' });
              }
            });
          } else {
            // Handle regular endpoints
            this.app[method || 'post'](routePath, async (request: FastifyRequest, reply: FastifyReply) => {
              try {
                const serviceInstance = this.getServiceInstance(serviceName);
                const methodFn = serviceInstance[endpoint.methodName];
                
                // Parse request body for parameters
                const params = this.parseRequestParams(request);
                
                // Call the method
                const result = await methodFn.call(serviceInstance, ...params);
                
                // Serialize and return result
                return this.serializeResult(result);
              } catch (error) {
                logError(`Error in endpoint ${routePath}: ${error}`);
                reply.code(500).send({ error: 'Internal server error' });
              }
            });
          }
          
          logInfo(`Registered endpoint: ${method?.toUpperCase() || 'POST'} ${routePath}`);
        }
      } catch (error) {
        logError(`Failed to register service ${serviceName}: ${error}`);
      }
    }
  }

  private getServiceInstance(serviceName: string): any {
    // In a real implementation, this would maintain instances of the service classes
    // For now, we'll return a mock object
    if (!this.services.has(serviceName)) {
      logError(`Service instance not found: ${serviceName}`);
      throw new Error(`Service instance not found: ${serviceName}`);
    }
    return this.services.get(serviceName);
  }

  private parseRequestParams(request: FastifyRequest): any[] {
    const body = request.body as RequestBody;
    
    if (!body || typeof body !== 'object') {
      return [];
    }
    
    // Convert object properties to method parameters
    // This is a simplified implementation - in practice, you'd want to use
    // parameter reflection or explicit parameter mapping
    return Object.values(body);
  }

  private serializeResult(result: any): any {
    if (result === null || result === undefined) {
      return result;
    }
    
    // Handle arrays and tensors
    if (Array.isArray(result)) {
      return result;
    }
    
    // Handle objects with toJSON method
    if (result && typeof result.toJSON === 'function') {
      return result.toJSON();
    }
    
    // Handle objects with toArray method (for tensor-like objects)
    if (result && typeof result.toArray === 'function') {
      return result.toArray();
    }
    
    // Handle primitive types
    if (typeof result === 'string' || typeof result === 'number' || typeof result === 'boolean') {
      return result;
    }
    
    // Handle plain objects
    if (typeof result === 'object') {
      return result;
    }
    
    // Fallback to string conversion
    return String(result);
  }

  public async start(options: ServerOptions): Promise<void> {
    const { host, port, dev, logLevel } = options;
    
    try {
      await this.registerServices();
      
      const address = await this.app.listen({ 
        host, 
        port
      });
      
      // Enhanced server startup display
      const serverInfo = [
        `Host: ${host}`,
        `Port: ${port}`,
        `Environment: ${dev ? 'Development' : 'Production'}`,
        `Log Level: ${logLevel}`,
        `Address: ${address}`,
        '',
        'API Documentation: /docs (if available)',
        'Health Check: /health'
      ];
      
      printBox('🚀 Server Started', serverInfo, { 
        color: dev ? 'warning' : 'success',
        width: 50
      });
      
      logSuccess(`Server listening at ${address}`);
      
    } catch (error) {
      logError(`Failed to start server: ${error}`);
      throw error;
    }
  }

  public async stop(): Promise<void> {
    try {
      await this.app.close();
      logInfo('Server stopped gracefully');
    } catch (error) {
      logError(`Error stopping server: ${error}`);
      throw error;
    }
  }

  public getApp(): FastifyInstance {
    return this.app;
  }
  
  public addService(name: string, instance: any): void {
    this.services.set(name, instance);
  }
}