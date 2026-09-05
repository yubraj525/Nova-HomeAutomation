import platform

from pydantic import BaseModel
from app.agent.base import Tool

class SystemInfoArgs(BaseModel):
   name: str
   description: str


class SystemInfoTool(Tool):
    name = "system_info"
    description = "Get information about the current system."
    arguments_model = SystemInfoArgs

    async def execute(self, arguments):
        return {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }