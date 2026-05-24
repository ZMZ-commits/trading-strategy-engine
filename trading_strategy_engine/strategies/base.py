from abc import ABC, abstractmethod
from ..models import RunResult, RunConfig


class BaseStrategy(ABC):
    @abstractmethod
    def run(self, config: RunConfig) -> RunResult:
        ...
