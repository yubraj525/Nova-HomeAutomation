from datetime import datetime
from app.agent.base import Tool
class GetTimeTool(Tool):
    name = "get_time"
    description = "Get the current local time."

    async def execute(self, arguments):
        return datetime.now().isoformat()