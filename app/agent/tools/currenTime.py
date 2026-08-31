from datetime import datetime
from app.agent.base import Tool
from pydantic import BaseModel

class GetTimeArgs(BaseModel):
    pass  # No arguments needed for this tool

class GetTimeTool(Tool):
    name = "get_time"
    description = "Get the current local time."
    arguments_model = GetTimeArgs

    async def execute(self, arguments):
        return datetime.now().isoformat()