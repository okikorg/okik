from typing_extensions import Callable
from okik.utils.configs.serviceconfigs import ServiceConfigs
from enum import Enum
from pydantic import BaseModel
import os
import json

image_path = os.path.join(".okik/cache/configs.json")
with open(image_path, "r") as f:
    image = json.load(f)["image_name"]

def generate_k8s_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": cls.__name__.lower()
        },
        "spec": {
            "replicas": replicas,
            "selector": {
                "matchLabels": {
                    "app": cls.__name__.lower()
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": cls.__name__.lower()
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": f"{cls.__name__.lower()}-container",
                            "image": f"{image}",
                            "resources": {
                                "limits": {
                                    "nvidia.com/gpu": resources.accelerator.count,
                                    "memory": f"{resources.accelerator.memory}Gi"
                                },
                                "requests": {
                                    "nvidia.com/gpu": resources.accelerator.count,
                                    "memory": f"{resources.accelerator.memory}Gi"
                                }
                            },
                            "env": [
                                {
                                    "name": "NVIDIA_VISIBLE_DEVICES",
                                    "value": ",".join(str(i) for i in range(resources.accelerator.count))
                                }
                            ]
                        }
                    ]
                }
            }
        }
    }

def generate_okik_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    return {
            "name": cls.__name__.lower(),
            "kind": "service",
            "replicas": replicas,
            "resources": resources.dict() if resources else None,
            "port": 3000,
            # take the image name from .okik/cache/config.json
            "image": f"{image}"
    }


def generate_sky_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    return {
        # Placeholder for the 'sky' YAML format
    }
