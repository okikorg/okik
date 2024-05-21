from typing_extensions import Callable
from okik.utils.configs.serviceconfigs import ServiceConfigs

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
                            "image": f"your-{cls.__name__.lower()}-image:latest",
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
        cls.__name__.lower(): {
            "name": cls.__name__.lower(),
            "kind": "service",
            "replicas": replicas,
            "resources": resources.dict() if resources else None
        }
    }


def generate_sky_yaml_config(cls: Callable, resources: ServiceConfigs, replicas: int) -> dict:
    return {
        # Placeholder for the 'sky' YAML format
    }
