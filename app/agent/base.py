"""Shared contracts and validation for local and remote tools."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from pydantic import BaseModel, ValidationError


class ExecutionType:
    LOCAL = "local"
    REMOTE = "remote"


class ToolError(Exception):
    """Base class for errors that can be returned to the agent as tool results."""


class ToolRegistrationError(ToolError, ValueError):
    pass


class UnknownToolError(ToolError, LookupError):
    pass


class ToolArgumentError(ToolError, ValueError):
    pass


class ToolExecutionError(ToolError):
    pass


class RemoteToolTimeoutError(ToolExecutionError, TimeoutError):
    pass


class RemoteClientDisconnectedError(ToolExecutionError, ConnectionError):
    pass


@dataclass(frozen=True)
class ToolExecutionContext:
    """Per-call metadata shared by every tool implementation."""

    tool_call_id: str | None = None
    session_id: str | None = None
    task_id: str | None = None
    status_callback: Callable[[str], Awaitable[None]] | None = None
    register_side_effect: Callable[[str, Callable[[], Awaitable[None]]], None] | None = None
    request_user_input: Callable[[str], Awaitable[str]] | None = None


_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")


def validate_tool_name(name: Any) -> str:
    if not isinstance(name, str) or not _TOOL_NAME_PATTERN.fullmatch(name):
        raise ToolRegistrationError(
            "Tool names must start with a letter or underscore and contain "
            "only letters, digits, underscores, or hyphens (maximum 64 characters)."
        )
    return name


def _reject_external_schema_refs(value: Any, path: str = "$") -> None:
    """Keep schema validation offline; only local JSON Pointer refs are allowed."""
    if isinstance(value, dict):
        ref = value.get("$ref")
        if ref is not None and (not isinstance(ref, str) or not ref.startswith("#/")):
            raise ToolRegistrationError(f"External schema reference is not allowed at {path}.")
        for key, child in value.items():
            _reject_external_schema_refs(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_external_schema_refs(child, f"{path}[{index}]")


def validate_json_schema_definition(schema: Any) -> None:
    """Check a tool's JSON Schema using the standard Draft 2020-12 validator."""
    if not isinstance(schema, dict):
        raise ToolRegistrationError("Tool parameters schema must be an object.")
    if schema.get("type") != "object":
        raise ToolRegistrationError("Tool parameters schema must have type 'object'.")
    _reject_external_schema_refs(schema)
    validator = validator_for(schema, default=Draft202012Validator)
    try:
        validator.check_schema(schema)
    except SchemaError as exc:
        raise ToolRegistrationError(f"Invalid tool parameters schema: {exc.message}") from exc


def validate_json_arguments(arguments: Any, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolArgumentError("Tool arguments must be a JSON object.")
    validator = validator_for(schema, default=Draft202012Validator)(schema)
    errors = sorted(
        validator.iter_errors(arguments),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "arguments"
        raise ToolArgumentError(f"{location}: {error.message}") from error
    return arguments


class Tool(ABC):
    """Every tool accepts validated arguments and per-call context."""

    name: str
    description: str
    arguments_model: type[BaseModel] | None = None
    parameters: dict[str, Any] | None = None
    executor: str | None = None

    def parameter_schema(self) -> dict[str, Any]:
        if self.arguments_model is not None:
            return self.arguments_model.model_json_schema()
        if self.parameters is not None:
            return self.parameters
        return {"type": "object", "properties": {}, "additionalProperties": False}

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameter_schema(),
            },
        }

    def validate_arguments(self, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolArgumentError("Tool arguments must be a JSON object.")

        if self.arguments_model is not None:
            allowed_fields = set(self.arguments_model.model_fields)
            unknown = set(arguments) - allowed_fields
            if unknown:
                raise ToolArgumentError(
                    f"Unexpected argument(s): {', '.join(sorted(unknown))}."
                )
            try:
                parsed = self.arguments_model.model_validate(arguments)
            except ValidationError as exc:
                raise ToolArgumentError(str(exc)) from exc
            return parsed.model_dump()

        return validate_json_arguments(arguments, self.parameter_schema())

    @abstractmethod
    async def execute(
        self,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        """Run once with router-validated arguments."""
