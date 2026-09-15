from abc import ABC, abstractmethod
from typing import Any
class ExecutionType():
    LOCAL = "local"
    REMOTE = "remote"

class Tool(ABC):
    name: str
    description: str
    arguments_model: Any  # This should be a Pydantic model class
    executor: ExecutionType  # This should be a callable that takes a dict and returns a result

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments_model.model_json_schema()
            }
        }
    
    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> Any:
        pass