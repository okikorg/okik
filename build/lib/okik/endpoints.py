from fastapi import FastAPI, APIRouter, HTTPException, Request
from typing import Type, Callable, Any, Dict, Union, List
import inspect
import torch
import torch.nn as nn
import asyncio
import numpy as np
import yaml
from .machines import Accelerators

app = FastAPI()
router = APIRouter()


def generate_service_yaml(
    replicas: int, accelerator: Accelerators, accelerator_count: int = 1
):

    service_yaml = {
        "resources": {
            "cloud": "runpod",
            "accelerators": (f"{accelerator}:{accelerator_count}"),
        },
        "workdir": ".",
        "setup": "pip install -r requirements.txt",
        "run": "python okik/main.py serve-dev -e main.py",
    }

    with open("service.yaml", "w") as file:
        yaml.dump(service_yaml, file)


def service(
    model_class: Type,
    replicas: int = 1,
    accelerator=Accelerators.A40,
    accelerator_count: int = 1,
):
    model_instance = model_class()
    class_name = model_class.__name__

    # Generate service.yaml
    generate_service_yaml(replicas, accelerator)

    for method_name, method in inspect.getmembers(
        model_instance, predicate=inspect.ismethod
    ):
        if hasattr(method, "is_endpoint"):

            # Function factory to create a route handler for each method
            def create_endpoint_route(method):
                # Move the determination of endpoint_schema inside this function
                endpoint_schema = inspect.signature(method)

                async def endpoint_route(request: Request):
                    try:
                        request_data = await request.json()
                        bound_args = endpoint_schema.bind(**request_data)
                        bound_args.apply_defaults()  # Ensure default values are applied
                        result = await call_method(
                            model_instance, method, dict(bound_args.arguments)
                        )
                        return serialize_result(result)
                    except TypeError as e:
                        raise HTTPException(status_code=400, detail=str(e))
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=str(e))

                return endpoint_route

            # Use the factory function to create a unique endpoint_route for each method
            unique_endpoint_route = create_endpoint_route(method)

            # Define the route using the unique endpoint route
            router.post(
                f"/{class_name}/{method_name}",
                response_model=Union[Dict, List, int, float, str, bool],
            )(unique_endpoint_route)

    app.include_router(router)


async def call_method(model_instance, method, kwargs: Dict[str, Any]):
    if asyncio.iscoroutinefunction(method):
        result = await method(**kwargs)
    elif isinstance(model_instance, nn.Module):
        result = model_instance(**kwargs)
    else:
        result = method(**kwargs)
    return result


def serialize_result(result: Any):
    if isinstance(result, torch.Tensor):
        return result.tolist()
    elif isinstance(result, np.ndarray):
        return result.tolist()
    elif isinstance(result, dict):
        return {str(key): value for key, value in result.items()}
    elif isinstance(result, (list, tuple, int, float, str, bool)):
        return result
    else:
        raise ValueError(f"Unsupported result type: {type(result)}")


def api(func: Callable):
    func.is_endpoint = True
    return func


app.include_router(router)


# Export the necessary objects and functions
__all__ = ["service", "api", "app"]
