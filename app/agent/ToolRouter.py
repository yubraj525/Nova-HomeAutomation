from typing import Any
from .registery import ToolRegistry


class ToolRouter:

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ):

        tool = self.registry.get(tool_name)

        result = await tool.execute(arguments)

        return result