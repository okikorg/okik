# Okik - Modern Cloud Deployment CLI

> **✨ A powerful TypeScript CLI tool designed to simplify the process of running various services using different frameworks on any cloud platform.**

[![npm version](https://badge.fury.io/js/okik.svg)](https://badge.fury.io/js/okik)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2-blue.svg)](https://www.typescriptlang.org/)

## 🚀 Features

Okik has been completely rewritten in TypeScript with a modern TUI and enhanced developer experience:

### 🎯 Core Features
- **🔧 Service Decorators**: Simple `@service` and `@endpoint` decorators for TypeScript classes
- **☁️ Multi-cloud Support**: Deploy across AWS, GCP, Azure, and more
- **🎛️ Framework Agnostic**: Works with any TypeScript/JavaScript framework
- **🤖 LLM & GenAI Integration**: Built-in support for AI/ML workloads
- **📈 Auto-scaling**: Intelligent resource scaling based on demand
- **📊 Built-in Monitoring**: Real-time performance and health monitoring
- **🚢 One-command Deploy**: Deploy with a single command
- **💻 Modern TUI**: Beautiful terminal interface with spinners, progress bars, and colors

### 🆕 Enhanced TypeScript Features
- **🔍 Type Safety**: Full TypeScript support with strict typing
- **📦 Modern Package Management**: Support for npm, yarn, and pnpm
- **🔄 Hot Reload**: Development server with automatic reloading
- **🐳 Docker Integration**: Optimized multi-stage Dockerfiles
- **⚡ Fastify Server**: High-performance HTTP server with streaming support
- **🎨 Enhanced CLI**: Beautiful terminal UI with gradient colors and animations

## 📦 Installation

### Using npm (Recommended)

```bash
npm install -g okik
```

### Using yarn

```bash
yarn global add okik
```

### From Source

```bash
git clone https://github.com/okikorg/okik.git
cd okik
npm install
npm run build
npm link
```

## 🚀 Quick Start

### 1. Initialize a Project

```bash
okik init
```

This creates:
- `.okik/` configuration directory
- TypeScript configuration files
- Docker templates
- Example service files

### 2. Create Your First Service

Create a `main.ts` file:

```typescript
import { service, endpoint } from 'okik';
import { AcceleratorType, AcceleratorDevice, BackendType } from 'okik/types';

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
export class EmbeddingService {
  private model: any;

  constructor() {
    // Initialize your model
    console.log('🚀 Embedding service starting...');
  }

  @endpoint()
  async embed(text: string): Promise<number[]> {
    // Your embedding logic here
    return new Array(768).fill(0).map(() => Math.random());
  }

  @endpoint()
  async similarity(text1: string, text2: string): Promise<number> {
    // Compute cosine similarity
    return Math.random();
  }

  @endpoint({ stream: true })
  async *batchEmbed(texts: string[]): AsyncGenerator<number[], void, unknown> {
    for (const text of texts) {
      yield await this.embed(text);
    }
  }
}

// Streaming LLM Service
@service({ replicas: 1 })
export class ChatService {
  @endpoint({ stream: true })
  async *chat(prompt: string): AsyncGenerator<string, void, unknown> {
    const words = prompt.split(' ');
    for (const word of words) {
      yield `${word} `;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }
}
```

### 3. Start the Development Server

```bash
okik server --dev --reload
```

### 4. View Your Routes

```bash
okik routes
```

```
📋 Application Routes

🔧 EMBEDDINGSERVICE Service
   POST   /embeddingservice/embed → embed
   POST   /embeddingservice/similarity → similarity
   POST   /embeddingservice/batchEmbed → batchEmbed

🔧 CHATSERVICE Service
   POST   /chatservice/chat → chat
```

### 5. Test Your API

```bash
# Test embedding endpoint
curl -X POST http://localhost:3000/embeddingservice/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'

# Test streaming chat
curl -X POST http://localhost:3000/chatservice/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me about TypeScript"}' \
  --no-buffer
```

## 🛠️ CLI Commands

### Project Management

```bash
# Initialize new project
okik init [--force]

# Clean temporary files
okik clean [--all]
```

### Development

```bash
# Start development server
okik server --dev --reload --port 3000

# Start production server
okik server --host 0.0.0.0 --port 8080 --workers 4

# View all routes
okik routes [--json]
```

### Building & Deployment

```bash
# Build Docker image
okik build --app-name my-app --tag latest [--verbose]

# Deploy to Kubernetes
okik deploy [--namespace default] [--dry-run]

# View deployments
okik get deployments

# View services
okik get services

# Delete resources
okik delete deployment my-app
```

### Cluster Management

```bash
# List cluster contexts
okik cluster

# Switch cluster context
okik cluster my-context
```

## 🎨 Enhanced TUI Features

The TypeScript rewrite includes a beautiful modern terminal interface:

### 🌈 Visual Elements
- **Gradient ASCII Art**: Beautiful startup banner
- **Progress Bars**: Real-time build and deployment progress
- **Spinners**: Animated loading indicators
- **Color Coding**: Different colors for different log levels
- **Boxed Output**: Important information in bordered boxes
- **Tables**: Formatted resource listings

### 🎯 Interactive Features
- **Smart Autocomplete**: Tab completion for commands
- **Interactive Prompts**: Choose from available options
- **Real-time Updates**: Live server status and metrics
- **Error Formatting**: Clear, contextual error messages

## 🏗️ Architecture

### Service Decorators

```typescript
// Simple service
@service()
class BasicService {
  @endpoint()
  hello(): string {
    return "Hello, World!";
  }
}

// Advanced service with GPU resources
@service({
  replicas: 3,
  resources: {
    accelerator: {
      type: AcceleratorType.A100,
      device: AcceleratorDevice.CUDA,
      count: 2,
      memory: 16
    }
  },
  backend: BackendType.K8S,
  port: 8080
})
class MLService {
  @endpoint({ method: 'POST', path: '/predict' })
  async predict(data: any): Promise<any> {
    // ML inference logic
  }

  @endpoint({ stream: true })
  async *streamPredictions(data: any[]): AsyncGenerator<any> {
    for (const item of data) {
      yield await this.predict(item);
    }
  }
}
```

### Backend Support

- **🏠 Local**: Development and testing
- **🐳 Docker**: Containerized deployment
- **☸️ Kubernetes**: Production orchestration
- **☁️ Okik Cloud**: Managed platform (coming soon)
- **🌟 Ray**: Distributed computing
- **☁️ SkyPilot**: Multi-cloud deployment

## 📊 Monitoring & Observability

```typescript
@service()
class MonitoredService {
  @endpoint({ method: 'GET', path: '/health' })
  healthCheck() {
    return {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime()
    };
  }

  @endpoint({ stream: true, path: '/metrics' })
  async *metrics(): AsyncGenerator<string> {
    while (true) {
      const data = {
        cpu: Math.random() * 100,
        memory: Math.random() * 100,
        requests: Math.floor(Math.random() * 1000)
      };
      yield `data: ${JSON.stringify(data)}\n\n`;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}
```

## 🔧 Configuration

### Project Configuration (`.okik/configs/config.json`)

```json
{
  "imageName": "myregistry/myapp:latest",
  "appName": "myapp",
  "registry": "docker.io",
  "tag": "latest"
}
```

### TypeScript Configuration

The project includes optimized TypeScript settings:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true,
    "strict": true
  }
}
```

## 🚀 Deployment Examples

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: embedding-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: embedding-service
  template:
    metadata:
      labels:
        app: embedding-service
    spec:
      containers:
      - name: embedding-service
        image: myregistry/embedding-service:latest
        resources:
          limits:
            memory: "4Gi"
            nvidia.com/gpu: 1
```

### Docker Compose

```yaml
version: '3.8'
services:
  okik-app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    volumes:
      - ./logs:/app/logs
```

## 🎯 Migration from Python

The TypeScript version maintains API compatibility while adding type safety:

### Python (Old)
```python
from okik import service, endpoint

@service(replicas=1, resources={"accelerator": {"type": "A40"}})
class MyService:
    @endpoint()
    def process(self, data: str):
        return {"result": data}
```

### TypeScript (New)
```typescript
import { service, endpoint } from 'okik';

@service({
  replicas: 1,
  resources: {
    accelerator: {
      type: AcceleratorType.A40,
      device: AcceleratorDevice.CUDA,
      count: 1,
      memory: 4
    }
  }
})
export class MyService {
  @endpoint()
  async process(data: string): Promise<{ result: string }> {
    return { result: data };
  }
}
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/okikorg/okik.git
cd okik
npm install
npm run dev
```

### Running Tests

```bash
npm test
npm run test:watch
npm run test:coverage
```

## 📝 License

MIT © [Okik](https://okik.ai)

## 🔗 Links

- **Homepage**: [okik.ai](https://okik.ai)
- **Documentation**: [docs.okik.ai](https://docs.okik.ai)
- **GitHub**: [github.com/okikorg/okik](https://github.com/okikorg/okik)
- **NPM**: [npmjs.com/package/okik](https://npmjs.com/package/okik)

---

**Built with ❤️ using TypeScript, Fastify, and modern CLI tools.**