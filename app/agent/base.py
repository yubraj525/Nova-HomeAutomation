from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str
    arguments_model: Any  # This should be a Pydantic model class
    
    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> Any:
        pass