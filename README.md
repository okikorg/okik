# About

*Okik* is a command-line interface (CLI) that allows users to run various inference services such as LLM, RAG(WIP), or anything in between using various frameworks on any *cloud. With *Okik*, you can easily run these services directly on any cloud without the hassle of managing your own infra.

## Installation
Using pip

```bash
pip install okik
```

Or
To install Okik, follow these steps:

1. Clone the repository: `git clone https://github.com/okikorg/okik.git`
2. Navigate to the project directory: `cd okik`
3. Install Okik using pip: `pip install .`

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

## Initialise the project
```bash
okik init
```

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

## Serving the app
```bash
# run the okik run to start the server in production mode
okik server
# or run in dev mode
okik server --dev --reload
#or
okik server -d -r
```

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


## Build the app
```bash
okik build -a "your_awesome_app" -t latest
```

## Deploy the app
```bash
okik deploy
```

## Monitor the app
```bash
# similar to kubectl commands, infact you can use kubectl commands as well
okik get deployments # for deployments
okik get services # for services
```

## Delete the app
```bash
okik delete deployment "your_awesome_app"
```

## Status
Okik is currently in development so expect sharp edges and bugs. Feel free to contribute to the project by submitting a pull request.

## Roadmap

- [] Add support for various inference engines such as vLLM, TGI, etc.
- [] Add support for various cloud providers such as AWS, GCP, Azure, etc.
