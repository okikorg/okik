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
from okik.utils.configs.serviceconfigs import ServiceConfigs, AcceleratorConfigs, AcceleratorDevice, AcceleratorDevice

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

def create_yaml_resources(cls, replicas: int, resources: Optional[ServiceConfigs]):
    def enum_representer(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data.value)
    yaml.add_representer(AcceleratorDevice, enum_representer)
    yaml.add_representer(AcceleratorDevice, enum_representer)
    model_instance = cls()
    os.makedirs(".okik/services", exist_ok=True)
    file_path = f".okik/services/serviceconfig.yaml"
    with open(file_path, "w") as f:
        yaml.dump({"replicas": replicas, "resources": resources.dict() if resources else None}, f)

def service(replicas: Optional[int] = 1, resources: Union[dict, ServiceConfigs, None] = None) -> Callable:
    def decorator(cls):
        if not isinstance(replicas, int) or replicas < 1:
            raise ValueError("Replicas must be an integer greater than 0")
        if resources is not None and not isinstance(resources, dict):
            raise ValueError("Resources, if provided, must be a dictionary")
        create_route_handlers(cls)
        create_yaml_resources(cls, replicas, ServiceConfigs(**resources) if resources else None)
        return cls
    return decorator

def api(func: Callable):
    func.is_endpoint = True
    return func

app.include_router(router)

__all__ = ["service", "api", "app"]
