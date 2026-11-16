from __future__ import annotations

from copy import deepcopy

from .base import (
    ExecutionType,
    Tool,
    ToolRegistrationError,
    UnknownToolError,
    validate_json_schema_definition,
    validate_tool_name,
)


class ToolRegistry:
    """Validated registry shared by local and remote tool implementations."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, executor: str = ExecutionType.LOCAL) -> None:
        if not isinstance(tool, Tool):
            raise ToolRegistrationError("Registered tools must implement Tool.")
        validate_tool_name(getattr(tool, "name", None))
        if executor not in (ExecutionType.LOCAL, ExecutionType.REMOTE):
            raise ToolRegistrationError(f"Unsupported execution type: {executor!r}.")
        if not isinstance(getattr(tool, "description", None), str) or not tool.description.strip():
            raise ToolRegistrationError(f"Tool {tool.name!r} must have a description.")

        schema = tool.parameter_schema()
        if executor == ExecutionType.REMOTE and not isinstance(tool.parameters, dict):
            raise ToolRegistrationError(f"Remote tool {tool.name!r} must provide a parameters schema.")
        validate_json_schema_definition(schema)
        if schema.get("type") != "object":
            raise ToolRegistrationError(f"Tool {tool.name!r} parameters must describe an object.")
        existing = self._tools.get(tool.name)
        if existing is not None:
            same_remote_owner = (
                executor == ExecutionType.REMOTE
                and existing.executor == ExecutionType.REMOTE
                and getattr(existing, "client_name", None) == getattr(tool, "client_name", None)
                and getattr(existing, "websocket", None) is getattr(tool, "websocket", None)
            )
            if not same_remote_owner:
                raise ToolRegistrationError(f"Tool {tool.name!r} is already registered.")

        tool.executor = executor
        self._tools[tool.name] = tool
        print(f"[TOOL REGISTRY] Registered {executor} tool: {tool.name}")

    def unregister_remote_client(self, client_name: str, websocket=None) -> list[str]:
        """Remove tools owned by a disconnected remote client."""
        removed = []
        for name, tool in list(self._tools.items()):
            if (
                tool.executor == ExecutionType.REMOTE
                and getattr(tool, "client_name", None) == client_name
                and (websocket is None or getattr(tool, "websocket", None) is websocket)
            ):
                del self._tools[name]
                removed.append(name)
        return removed

    def get(self, name: str) -> Tool:
        if not isinstance(name, str):
            raise UnknownToolError("Tool name must be a string.")
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(f"Tool {name!r} is not registered.")
        return tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def print_tools(self):
        for tool in self._tools.values():
            print(f"\nTool: {tool.name}")
            print(f"Description: {tool.description}")
            print(f"Execution Type: {tool.executor}")
            print(f"Parameters: {tool.parameter_schema()}")
            print("-" * 40)

    def get_tool_schemas(self):
        return [deepcopy(tool.schema()) for tool in self._tools.values()]
