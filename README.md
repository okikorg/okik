# About

*Okik* is a command-line interface (CLI) that allows users to run various inference services such as LLM, RAG(WIP), or anything in between using various frameworks on any *cloud. With *Okik*, you can easily run these services directly on any cloud without the hassle of managing your own infra.

## Installation

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
from okik.endpoints import service, api, app
from sentence_transformers import SentenceTransformer
import sentence_transformers
from torch.nn.functional import cosine_similarity as cosine
import torch

# your service configuration
@service(
    replicas=2,
    resources={"accelerator": {"type": "cuda", "device": "A40", "count": 2}}
)
class Embedder: # your service class which will be used to serve the requests
    def __init__(self):
        self.model = SentenceTransformer("paraphrase-MiniLM-L6-v2", cache_folder=".okik/cache")

    @api # your api endpoint
    def embed(self, sentence: str):
        logits = self.model.encode(sentence)
        return logits

    @api
    def similarity(self, sentence1: str, sentence2: str):
        logits1 = self.model.encode(sentence1, convert_to_tensor=True)
        logits2 = self.model.encode(sentence2, convert_to_tensor=True)
        return cosine(logits1.unsqueeze(0), logits2.unsqueeze(0))

    @api
    def version(self):
        return sentence_transformers.__version__
```

## Verify the routes
```bash
# run the okik routes to check all available routes
okik gen
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
```


## Build the app
```bash
okik build -a "your_awesome_app" -t latest
```

## Status

Okik is currently in development so expect sharp edges and bugs. Feel free to contribute to the project by submitting a pull request.
