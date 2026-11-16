from datetime import datetime
from app.agent.base import Tool, ToolExecutionContext
from pydantic import BaseModel

class GetTimeArgs(BaseModel):
    pass  # No arguments needed for this tool

class GetTimeTool(Tool):
    name = "get_time"
    description = "Get the current local time."
    arguments_model = GetTimeArgs
    executor = None

    async def execute(self, arguments, context: ToolExecutionContext | None = None):
        return datetime.now().isoformat()
