import os
from fastapi import FastAPI, APIRouter, HTTPException, Request
from typing import Type, Callable, Any, Dict, Union, List, Optional
import inspect
import torch
import torch.nn as nn
import asyncio
import yaml
import numpy as np
from rich.console import Console
from pydantic import BaseModel, ValidationError
from okik.utils.configs.serviceconfigs import BackendType, ProvisioningBackend, ServiceConfigs, AcceleratorConfigs, AcceleratorType, AcceleratorDevice
from okik.utils.configs.yaml_configs import generate_k8s_yaml_config, generate_okik_yaml_config
from okik.logger import log_info, log_error, log_warning, log_debug, log_success, log_start, log_running

console = Console()
app = FastAPI()
router = APIRouter()

def create_route_handlers(cls):
    model_instance = cls()
    class_name = cls.__name__.lower()
    for method_name, method in inspect.getmembers(model_instance, predicate=inspect.ismethod):
        if hasattr(method, "is_endpoint"):
            def create_endpoint_route(method):
                endpoint_schema = inspect.signature(method)
                async def endpoint_route(request: Request):
                    try:
                        if endpoint_schema.parameters:
                            request_data = await request.json()
                            bound_args = endpoint_schema.bind(**request_data)
                            bound_args.apply_defaults()
                            result = await call_method(model_instance, method, dict(bound_args.arguments))
                        else:
                            result = await call_method(model_instance, method, {})
                        return serialize_result(result)
                    except TypeError as e:
                        raise HTTPException(status_code=400, detail=str(e))
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=str(e))
                return endpoint_route
            unique_endpoint_route = create_endpoint_route(method)
            router.post(f"/{class_name}/{method_name}", response_model=Union[Dict, List, int, float, str, bool])(unique_endpoint_route)
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
    elif isinstance(result, (list, tuple, int, float, str, bool, set)):
        return result
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported return type {type(result)} for serialization")


def create_yaml_resources(cls, replicas: int, resources: ServiceConfigs, backend: ProvisioningBackend):
    k8s_yaml = {}
    okik_yaml = {}

    log_start(f"Creating YAML for {cls.__name__}...")
    log_info(f"cls: {cls} | replicas: {replicas} | resources: {resources} | backend: {backend}")
    if backend not in BackendType.__members__.values():
            raise ValueError(f"Invalid backend. Must be one of {list(BackendType.__members__.keys())}")

    def enum_representer(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data.value)

    yaml.add_representer(AcceleratorType, enum_representer)
    yaml.add_representer(AcceleratorDevice, enum_representer)

    if backend == "k8":
            k8s_yaml = generate_k8s_yaml_config(cls, resources, replicas)
            file_path = f".okik/services/k8/{cls.__name__.lower()}-config.yaml"
    elif backend == "okik":
            okik_yaml = generate_okik_yaml_config(cls, resources, replicas)
            file_path = f".okik/services/okik/serviceconfig.yaml"
    elif backend == "ray":
        raise NotImplementedError("Ray backend is not yet implemented")
        ray_yaml = {}
        file_path = f".okik/services/ray/{cls.__name__.lower()}-config.yaml"
    elif backend == "sky":
        raise NotImplementedError("Sky backend is not yet implemented")
        sky_yaml = {}
        file_path = f".okik/services/sky/{cls.__name__.lower()}-config.yaml"
    else:
        raise ValueError(f"Invalid backend. Must be one of {list(BackendType.__members__.keys())}")

    # Load existing data if the file exists
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                existing_data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                print(f"Error reading YAML file: {e}")
                existing_data = {}
    else:
        existing_data = {}

    # Prepare new service configuration based on style
    if backend == "k8":
        new_service_config = k8s_yaml
    elif backend == "okik":
        new_service_config = okik_yaml
    elif backend == "ray":
        # new_service_config = ray_yaml
        raise NotImplementedError("Ray style is not yet implemented")
    else:  # Placeholder for 'sky' style
        # new_service_config = sky_yaml
        raise NotImplementedError("Sky style is not yet implemented")

    # Update existing data with the new service configuration
    existing_data.update(new_service_config)

    # Write back the updated data to the YAML file
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        yaml.dump(existing_data, f)

def service(replicas: Optional[int] = 1, resources: Optional[Union[dict, ServiceConfigs]] = {}, backend: Optional[str] = "okik") -> Callable:
    """
    Decorator for creating services with specified configurations.

    Args:
        replicas (Optional[int]): Number of service replicas. Defaults to 1.
        resources (Union[dict, ServiceConfigs, None]): Resource configurations for the service.
            Can be a dictionary or a ServiceConfigs instance. Defaults to None.
        backend (Optional[str]): The backend provisioning system. Defaults to None.

    Returns:
        Callable: The decorated class.

    Raises:
        ValueError: If replicas is not a positive integer or resources is not a dictionary when provided.
        HTTPException: If there is a validation error with the provided resource configurations.

    Example:
        @service(replicas=2, resources={"type": "cuda"})\n
        class MyModel:
            pass
    """
    # console print the service creation
    log_start("Creating services...")
    log_info(f"replicas: {replicas} | resources: {resources} | backend: {backend}")
    def decorator(cls):
        log_start(f"Creating service {cls.__name__}...")
        if not isinstance(replicas, int) or replicas < 1:
            raise ValueError("Replicas must be an integer greater than 0")
        if resources is not None and not isinstance(resources, dict) and not isinstance(resources, ServiceConfigs):
            raise ValueError("Resources, if provided, must be a dictionary or a ServiceConfigs instance")
        create_route_handlers(cls)
        try:
            service_configs = ServiceConfigs(**resources) if resources else None
            create_yaml_resources(cls, replicas, service_configs, backend)
        except ValidationError as e:
            console.print("[bold red]Validation error while creating ServiceConfigs:[/bold red]")
            for error in e.errors():
                console.print(f"[red]{error['loc']}: {error['msg']}[/red]")
            raise HTTPException(status_code=400, detail="Invalid resource configuration. See logs for details.")
        return cls
    return decorator

def endpoint(func: Callable):
    """
    Decorator to mark a function as an API endpoint.

    Args:
        func (Callable): The function to be marked as an endpoint.

    Returns:
        Callable: The original function marked as an endpoint.

    Example:
        @api\n
        def my_endpoint():
    """
    func.is_endpoint = True # type: ignore
    return func

app.include_router(router)

__all__ = ["service", "endpoint", "app"]
