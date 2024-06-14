from abc import ABC, abstractmethod
from okik.endpoints import endpoint
from transformers import AutoConfig

class MemoryEstimator(ABC):
    def __init__(self, model: str):
        pass


    @abstractmethod
    def estimate(self, prompt: str) -> int:
        """
        Estimate the memory usage of the model based on the given prompt.

        :param prompt: The input text to estimate memory usage from.
        :return: The estimated memory usage.
        """
        pass

class BaseLLM(ABC):
    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate text based on the given prompt.

        :param prompt: The input text to generate text from.
        :return: The generated text.
        """
        pass
