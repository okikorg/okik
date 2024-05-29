from enum import Enum

class AcceleratorType(Enum):
    MI300X = "MI300X"
    MI250X = "MI250X"
    A100_80GB = "A100-80GB"
    A40 = "A40"
    V100 = "V100"
    V100_32GB = "V100-32GB"
    T4 = "T4"
    H100 = "H100"
    L4 = "L4"
    A10 = "A10"
    A10G = "A10G"
    K80 = "K80"
    P100 = "P100"


class AcceleratorDevice(Enum):
    cuda: str = "cuda"
    cpu: str = "cpu"


__all__ = ["AcceleratorType", "AcceleratorDevice"]
