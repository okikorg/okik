from okik.utils.configs.machines import AcceleratorDevice, AcceleratorType
from pydantic import BaseModel
from enum import Enum

class AcceleratorConfigs(BaseModel):
    type: AcceleratorType
    device: AcceleratorDevice
    count: int = 1
    memory: int

class ServiceConfigs(BaseModel):
    accelerator: AcceleratorConfigs

class BackendType(str, Enum):
    k8 = "k8"
    okik = "okik"
    sky = "sky"
    ray = "ray"

class ProvisioningBackend(BaseModel):
    backend: BackendType

__all__ = ["AcceleratorConfigs", "ServiceConfigs"]
