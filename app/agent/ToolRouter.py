
from hashlib import new

from app.agent.pending_manager import PendingRequests
from app.agent.registery import ToolRegistry

class ToolRouter:

    def __init__(self, registry: ToolRegistry, pending_requests: PendingRequests):
        self.registry = registry
        self.pending_requests = pending_requests

    async def execute(
     self,
     tool_name: str,
     arguments: dict[str, any],
     tool_call_id: str | None = None
     
):  
     tool = self.registry.get(tool_name)

     
     try:
         result = await tool.execute(
             tool_name,
             **arguments
         )

       

        

     except Exception as e:
       
         new_e = Exception(f"Error executing tool {tool_name}: {str(e)}")
         new_e.__cause__ = e

         raise new_e