from okik.utils.configs.machines import AcceleratorDevice, AcceleratorType
from pydantic import BaseModel

class AcceleratorConfigs(BaseModel):
    type: AcceleratorType
    device: AcceleratorDevice
    count: int

class ServiceConfigs(BaseModel):
    accelerator: AcceleratorConfigs

__all__ = ["AcceleratorConfigs", "ServiceConfigs"]
