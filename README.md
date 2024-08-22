# About

*Okik* is a powerful command-line interface (CLI) tool designed to simplify the process of running various services using different frameworks on any cloud platform. With *Okik*, users can effortlessly deploy and manage their services directly on any cloud infrastructure without the complexity of handling their own infrastructure. This tool bridges the gap between development and deployment, allowing teams to focus on creating innovative applications rather than getting bogged down in infrastructure management.

Key features of *Okik* include:
1. Managed Kubernetes clusters: Deploy services on Kubernetes clusters without the need to manage the underlying infrastructure. *Okik* handles all aspects of cluster management, including provisioning, scaling, and monitoring, allowing users to focus on building their applications.
2. Multi-cloud support: Deploy services across various cloud providers seamlessly. This feature allows for greater flexibility and prevents vendor lock-in, enabling users to choose the best cloud solution for their specific needs.
3. Framework agnostic: Compatible with a wide range of popular frameworks and technologies. Use Hugging Face, TensorFlow, PyTorch, and more to build your services, all managed by *Okik*.
4. LLM and GenAI integration: Easily incorporate Large Language Models and Generative AI capabilities into your applications. *Okik* provides seamless integration with popular LLM frameworks and GenAI tools, enabling advanced natural language processing and content generation within your services.
5. Automated predictive scaling: Easily scale your services up or down based on demand. *Okik* automatically adjusts resources to meet your application's needs, ensuring optimal performance and cost-efficiency, even for resource-intensive LLM and GenAI workloads.
6. Built-in monitoring: Keep track of your services' performance and health with integrated monitoring tools. This feature provides real-time insights into your application's behavior, helping you identify and address issues promptly, including specialized metrics for LLM and GenAI components.
7. Streamlined deployment: Quickly deploy services with a single command. This simplifies the deployment process, reducing the time and effort required to get your application up and running, including complex LLM and GenAI-powered services.
8. Easy-to-use CLI: Simplify the deployment process with an intuitive command-line interface. The CLI is designed to be user-friendly, even for those who may not have extensive experience with cloud deployments or AI model management.

*Okik* streamlines the development and deployment process, allowing developers to focus on building great applications rather than managing infrastructure. It abstracts away the complexities of cloud deployment, making it accessible to developers of all skill levels. Whether you're working on a small project or a large-scale enterprise application, *Okik* provides the flexibility and ease-of-use to meet your needs.

By leveraging *Okik*, teams can significantly reduce the time and resources spent on infrastructure management, leading to faster development cycles and more frequent releases. It also promotes best practices in deployment and scaling, helping to ensure that your applications are robust and performant.

For more information, including detailed documentation, tutorials, and community support, visit [okik.ai](www.okik.ai).

## Installation
Using pip

```bash
pip install okik
```

This is the simplest method to install Okik. It will automatically handle all dependencies and install the latest stable version of Okik.

Or
To install Okik from source, follow these steps:

1. Clone the repository: `git clone https://github.com/okikorg/okik.git`
2. Navigate to the project directory: `cd okik`
3. Install Okik using pip: `pip install .`

This method is useful if you want to contribute to Okik's development or need the latest features that haven't been released in the stable version yet.

## Quick Start

To run Okik, simply execute the following command in your terminal:
`okik`
```
██████  ██   ██ ██ ██   ██
██    ██ ██  ██  ██ ██  ██
██    ██ █████   ██ █████
██    ██ ██  ██  ██ ██  ██
██████  ██   ██ ██ ██   ██



Simplify. Deploy. Scale.
Type 'okik --help' for more commands.
```

This command launches the Okik CLI, providing you with an overview of available commands and options.

## Initialise the project
```bash
okik init
```

This command sets up a new Okik project in your current directory. It creates necessary configuration files and project structure, preparing your environment for Okik-managed deployments.

## Quick Example
Write this in your `main.py` file:

```python
from okik.endpoints import service, endpoint, app
import asyncio
from typing import Any
from sentence_transformers import SentenceTransformer
import sentence_transformers
from torch.nn.functional import cosine_similarity as cosine
import torch
import random

# your service configuration
@service(
    replicas=1,
    resources={"accelerator": {"type": "A40", "device": "cuda", "count": 1, "memory": 4}},
    backend="okik" # <- provisioning backend is okik
)
class Embedder:
    def __init__(self):
        self.model = SentenceTransformer("paraphrase-MiniLM-L6-v2", cache_folder=".okik/cache")

    @endpoint()
    def embed(self, sentence: str):
        logits = self.model.encode(sentence)
        return logits

    @endpoint()
    def similarity(self, sentence1: str, sentence2: str):
        logits1 = self.model.encode(sentence1, convert_to_tensor=True)
        logits2 = self.model.encode(sentence2, convert_to_tensor=True)
        return cosine(logits1.unsqueeze(0), logits2.unsqueeze(0))

    @endpoint()
    def version(self):
        return sentence_transformers.__version__

    @endpoint(stream=True)
    async def stream_data(self) -> Any:
        async def data_generator():
            for i in range(10):
                yield f"data: {i}\n"
                await asyncio.sleep(1)
        return data_generator()

# Mock LLM Service Example
@service(replicas=1)
class MockLLM:
    def __init__(self):
        pass

    @endpoint(stream=True) # <- streaming response enabled for use cases like chatbot
    async def stream_random_words(self, prompt: str = "Hello"):
        async def word_generator():
            words = ["hello", "world", "fastapi", "stream", "test", "random", "words", "python", "async", "response"]
            for _ in range(10):
                word = random.choice(words)
                yield f"{word}\n"
                await asyncio.sleep(0.4)
        return word_generator()

```

This example demonstrates how to create services and endpoints using Okik. The `@service` decorator defines a service with specific configuration, while `@endpoint` decorators define individual API endpoints within the service. The example includes both synchronous and asynchronous endpoints, as well as streaming capabilities.

## Verify the routes
```bash
# run the okik routes to check all available routes
okik routes
```
```bash
# output should be similar to this
main.py Application Routes
├── <HOST>/health/
│   └── /health | GET
├── <HOST>/embedder/
│   ├── /embedder/embed | POST
│   ├── /embedder/similarity | POST
│   ├── /embedder/stream_data | POST
│   └── /embedder/version | POST
└── <HOST>/mockllm/
    └── /mockllm/stream_random_words | POST
```

This command displays all the routes defined in your application, helping you verify that your endpoints are correctly set up.

## Serving the app
```bash
# run the okik run to start the server in production mode
okik server
# or run in dev mode
okik server --dev --reload
#or
okik server -d -r
```

These commands start your Okik server. The `--dev` and `--reload` flags are useful during development as they enable auto-reloading when code changes are detected.

## Test the app
```bash
curl -X POST http://0.0.0.0:3000/embedder/version
# or if you like to use httpie then
http POST 0.0.0.0:3000/embedder/version

# or test the stream endpoint
curl -X POST http://0.0.0.0:3000/mockllm/stream_random_words -d '{"prompt": "Hello"}'
# or if you like to use httpie then
http POST 0.0.0.0:3000/mockllm/stream_random_words prompt="hello" --stream
```

These commands demonstrate how to test your Okik endpoints using curl or httpie. They show both regular POST requests and how to handle streaming responses.

## Build the app
```bash
okik build -a "your_awesome_app" -t latest
```

This command builds your application, preparing it for deployment. The `-a` flag specifies the application name, and `-t` sets the tag for the build.

## Deploy the app
```bash
okik deploy
```

This command deploys your built application to the configured cloud provider.

## Monitor the app
```bash
# similar to kubectl commands, infact you can use kubectl commands as well
okik get deployments # for deployments
okik get services # for services
```

These commands allow you to monitor your deployed applications and services, providing information about their status and configuration.

## Delete the app
```bash
okik delete deployment "your_awesome_app"
```

This command removes a deployed application from your cloud environment.

## Status
Okik is currently in development so expect sharp edges and bugs. Feel free to contribute to the project by submitting a pull request. Your feedback and contributions are valuable in improving and stabilizing Okik for the wider development community.
