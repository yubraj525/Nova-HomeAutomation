import platform
from app.agent.base import Tool

class SystemInfoTool(Tool):
    name = "system_info"
    description = "Get information about the current system."

    async def execute(self, arguments):
        return {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }