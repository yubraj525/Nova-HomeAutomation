from .base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)

        if tool is None:
            raise ValueError(f"Tool '{name}' is not registered.")

        return tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())