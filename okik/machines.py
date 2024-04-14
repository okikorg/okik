from enum import Enum


class Accelerators(Enum):
    MI300X = "MI300X"
    MI250X = "MI250X"
    HGX_A100_80GB_SXM5 = "HGX A100 80GB SXM5"
    TX_1080_80GB_PCIE = "TX 1080 80GB PCIe"
    TX_L40 = "TX L40"
    TX_L40S = "TX L40S"
    RTX_6000_Ada = "RTX 6000 Ada"
    RTX_4090 = "RTX 4090"
    TX_L4 = "TX L4"
    RTX_4000_Ada = "RTX 4000 Ada"
    A100_80GB = "A100 80GB"
    A100_SXM4_80GB = "A100 SXM4 80GB"
    A40 = "A40"
    RTX_A6000 = "RTX A6000"
    RTX_A5500 = "RTX A5500"
    RTX_A4000 = "RTX A4000"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def get_accelerators(cls):
        return [acc.value for acc in cls]
