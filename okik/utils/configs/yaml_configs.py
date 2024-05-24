from typing_extensions import Callable
from okik.utils.configs.serviceconfigs import ServiceConfigs
from enum import Enum
from pydantic import BaseModel
import os
import json
from okik.consts import ProjectDir

def generate_k8s_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    # read image name from .okik/configs/configs.json
    with open(os.path.join(ProjectDir.CONFIG_DIR.value, "configs.json"), "r") as f:
        configs = json.load(f)
        image_name = configs["image_name"]
        app_name = configs["app_name"]

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": cls.__name__.lower(),
            "labels": {
                "app_name": f"{app_name}"
            }
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
                            "image": f"{image_name}",
                            "resources": {
                                "limits": {
                                    "memory": f"{resources.accelerator.memory}Gi",
                                    **({"nvidia.com/gpu": resources.accelerator.count} if resources.accelerator.type == "cuda" else {})
                                },
                                "requests": {
                                    "memory": f"{resources.accelerator.memory}Gi",
                                    **({"nvidia.com/gpu": resources.accelerator.count} if resources.accelerator.type == "cuda" else {})
                                }
                            },
                            "env": [
                                {
                                    "name": "ACCELERATOR_COUNT",
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
    # read image name from .okik/configs/configs.json
    with open(os.path.join(ProjectDir.CONFIG_DIR.value, "configs.json"), "r") as f:
        configs = json.load(f)
        image_name = configs["image_name"]
        app_name = configs["app_name"]

    return {
        "kind": "service",
        "replicas": replicas,
        "resources": resources.dict() if resources else None,
        "port": 3000,
        "image": f"{image_name}",
        "metadata": {
            "name": cls.__name__.lower(),
            "app": f'{app_name}',
            "token": "1234567890",

        },
        "ssh": {
            "enabled": True,
            "port": 22,
            "key": ""
        }
    }


def generate_sky_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    return {
        # Placeholder for the 'sky' YAML format
    }
