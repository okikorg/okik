from fastapi import FastAPI, APIRouter, HTTPException, Request
from typing import Type, Callable, Any, Dict, Union, List
import inspect
import torch
import torch.nn as nn
import asyncio
import numpy as np
from .machines import Accelerators
from rich.console import Console


console = Console()
app = FastAPI()
router = APIRouter()


def generate_service_yaml(service_name: str, service_params: dict):
    # Implement the logic to generate the YAML content based on the service parameters
    # Return the generated YAML content as a string
    yaml_content = f"""
  name: {service_name}
  workdir: .
  resources:
    accelerators:
      {service_params["accelerator"]}: {service_params["accelerator_count"]}
  setup: |
    echo "Setting up the service..."
  run: |
    echo "Running the service..."
"""
    return yaml_content


def generate_service_yaml_file(cls):
    service_name = cls.__name__.lower()
    service_params = cls._service_params

    yaml_content = generate_service_yaml(service_name, service_params)

    file_path = f".okik/services/{service_name}.yaml"
    with open(file_path, "w") as file:
        file.write(yaml_content)


def create_route_handlers(cls):
    model_instance = cls()
    class_name = cls.__name__

    for method_name, method in inspect.getmembers(
        model_instance, predicate=inspect.ismethod
    ):
        if hasattr(method, "is_endpoint"):
            # Function factory to create a route handler for each method
            def create_endpoint_route(method):
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


def service(
    model_class: Type = None,  # type: ignore
    replicas: int = 1,
    accelerator=Accelerators.A40,
    accelerator_count: int = 1,
):
    def decorator(cls):
        cls._service_params = {
            "replicas": replicas,
            "accelerator": accelerator,
            "accelerator_count": accelerator_count,
        }
        generate_service_yaml_file(cls)
        create_route_handlers(cls)
        return cls

    if model_class is None:
        return decorator
    else:
        return decorator(model_class)


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
