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

    def print_tools(self):
     for tool in self._tools.values():
         print(f"\nTool: {tool.name}")
         print(f"Description: {tool.description}")
 
         # Case 1: Pydantic model structure
         if getattr(tool, "arguments_model", None):  
             print("Arguments:")
             fields = tool.arguments_model.model_fields
             if not fields:
                 print("  None")
             else:
                 for name, field in fields.items():
                     # Extract type name cleanly from annotation
                     type_hint = getattr(field.annotation, "__name__", str(field.annotation))
                     print(f"  - {name}: {type_hint}")
 
         # Case 2: Raw dictionary parameters
         elif getattr(tool, "parameters", None):
             print("Parameters:")
             params = tool.parameters
             if not params:
                 print("  None")
             else:
                 for name, value in params.items():
                     print(f"  - {name}: {value}")
         
         else:
             print("Parameters: None")
 
         print("-" * 40)

    def get_tool_schemas(self):
        return [
            tool.schema()
            for tool in self._tools.values()
        ]