import { service, endpoint } from '../src/decorators/index.js';
import { AcceleratorType, AcceleratorDevice, BackendType } from '../src/types/index.js';

// Example service similar to the original Python Embedder service
@service({
  replicas: 1,
  resources: {
    accelerator: {
      type: AcceleratorType.A40,
      device: AcceleratorDevice.CUDA,
      count: 1,
      memory: 4
    }
  },
  backend: BackendType.OKIK
})
export class Embedder {
  private model: any; // In real implementation, this would be your ML model

  constructor() {
    // Initialize your model here
    // this.model = new SentenceTransformer("paraphrase-MiniLM-L6-v2");
    console.log('Embedder service initialized');
  }

  @endpoint()
  async embed(sentence: string): Promise<number[]> {
    // Simulate embedding generation
    console.log(`Embedding sentence: ${sentence}`);
    
    // In real implementation:
    // const logits = await this.model.encode(sentence);
    // return logits;
    
    // Mock response
    return new Array(384).fill(0).map(() => Math.random());
  }

  @endpoint()
  async similarity(sentence1: string, sentence2: string): Promise<number> {
    console.log(`Computing similarity between: "${sentence1}" and "${sentence2}"`);
    
    // In real implementation:
    // const logits1 = await this.model.encode(sentence1);
    // const logits2 = await this.model.encode(sentence2);
    // return cosineSimilarity(logits1, logits2);
    
    // Mock response
    return Math.random();
  }

  @endpoint()
  version(): string {
    // Return version information
    return "1.0.0";
  }

  @endpoint({ stream: true })
  async *streamData(): AsyncGenerator<string, void, unknown> {
    // Streaming endpoint example
    for (let i = 0; i < 10; i++) {
      yield `data: ${i}\n`;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

// Mock LLM Service Example (matching the original Python example)
@service({
  replicas: 1,
  backend: BackendType.OKIK
})
export class MockLLM {
  constructor() {
    console.log('MockLLM service initialized');
  }

  @endpoint({ stream: true })
  async *streamRandomWords(prompt: string = "Hello"): AsyncGenerator<string, void, unknown> {
    console.log(`Streaming response for prompt: ${prompt}`);
    
    const words = [
      "hello", "world", "fastapi", "stream", "test", 
      "random", "words", "typescript", "async", "response"
    ];
    
    for (let i = 0; i < 10; i++) {
      const word = words[Math.floor(Math.random() * words.length)];
      yield `${word}\n`;
      await new Promise(resolve => setTimeout(resolve, 400));
    }
  }

  @endpoint()
  async generateText(prompt: string, maxTokens: number = 100): Promise<string> {
    console.log(`Generating text for prompt: ${prompt} (max tokens: ${maxTokens})`);
    
    // Mock text generation
    const sentences = [
      "This is a sample generated text.",
      "TypeScript provides excellent type safety.",
      "Modern CLI tools enhance developer experience.",
      "Cloud deployment made simple with Okik.",
      "Streaming responses enable real-time interactions."
    ];
    
    return sentences[Math.floor(Math.random() * sentences.length)];
  }
}

// Advanced service with multiple accelerator types
@service({
  replicas: 2,
  resources: {
    accelerator: {
      type: AcceleratorType.T4,
      device: AcceleratorDevice.CUDA,
      count: 2,
      memory: 8
    }
  },
  backend: BackendType.K8S,
  port: 8080
})
export class MultiModalAI {
  constructor() {
    console.log('MultiModalAI service initialized');
  }

  @endpoint({ method: 'POST', path: '/analyze-image' })
  async analyzeImage(imageUrl: string): Promise<{
    description: string;
    confidence: number;
    tags: string[];
  }> {
    console.log(`Analyzing image: ${imageUrl}`);
    
    // Mock image analysis
    return {
      description: "A beautiful landscape with mountains and lakes",
      confidence: 0.95,
      tags: ["landscape", "mountains", "nature", "scenic"]
    };
  }

  @endpoint({ method: 'POST', path: '/generate-image' })
  async generateImage(prompt: string, style: string = "realistic"): Promise<{
    imageUrl: string;
    metadata: Record<string, any>;
  }> {
    console.log(`Generating image with prompt: ${prompt}, style: ${style}`);
    
    // Mock image generation
    return {
      imageUrl: `https://example.com/generated-image-${Date.now()}.jpg`,
      metadata: {
        prompt,
        style,
        resolution: "1024x1024",
        model: "diffusion-v2"
      }
    };
  }

  @endpoint({ stream: true, path: '/chat' })
  async *chatStream(message: string): AsyncGenerator<string, void, unknown> {
    console.log(`Chat message: ${message}`);
    
    const responses = [
      "I understand your question about ",
      message.slice(0, 20),
      "... Let me think about that. ",
      "Based on my knowledge, I can tell you that ",
      "this is a complex topic that involves ",
      "multiple factors and considerations. ",
      "Would you like me to elaborate further?"
    ];
    
    for (const response of responses) {
      yield `data: ${response}`;
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }
}

// Health monitoring service
@service({
  replicas: 1,
  backend: BackendType.DOCKER
})
export class HealthMonitor {
  private metrics: Record<string, number> = {};

  constructor() {
    console.log('HealthMonitor service initialized');
    this.startMetricsCollection();
  }

  private startMetricsCollection(): void {
    // Simulate metrics collection
    setInterval(() => {
      this.metrics = {
        cpu_usage: Math.random() * 100,
        memory_usage: Math.random() * 100,
        disk_usage: Math.random() * 100,
        network_io: Math.random() * 1000,
        requests_per_second: Math.random() * 50,
        error_rate: Math.random() * 5
      };
    }, 5000);
  }

  @endpoint({ method: 'GET', path: '/metrics' })
  getMetrics(): Record<string, number> {
    return this.metrics;
  }

  @endpoint({ method: 'GET', path: '/health' })
  healthCheck(): {
    status: string;
    timestamp: string;
    uptime: number;
    version: string;
  } {
    return {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      version: '1.0.0'
    };
  }

  @endpoint({ stream: true, path: '/metrics-stream' })
  async *metricsStream(): AsyncGenerator<string, void, unknown> {
    while (true) {
      yield `data: ${JSON.stringify(this.metrics)}\n\n`;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

// Export all services for auto-discovery
export const services = {
  Embedder,
  MockLLM,
  MultiModalAI,
  HealthMonitor
};

// Auto-register services when this module is imported
Object.values(services).forEach(ServiceClass => {
  // Services are automatically registered via decorators
  console.log(`Registered service: ${ServiceClass.name}`);
});