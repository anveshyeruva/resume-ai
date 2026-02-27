from abc import ABC, abstractmethod
from typing import Iterable

class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, prompt: str, *, temperature: float = 0.2) -> str:
        raise NotImplementedError

    def stream(self, prompt: str, *, temperature: float = 0.2) -> Iterable[str]:
        yield self.generate(prompt, temperature=temperature)
