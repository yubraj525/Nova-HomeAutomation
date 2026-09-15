from typing import Any
from .registery import ToolRegistry
from .pending_manager import PendingRequests


class ToolRouter:

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.pending_requests = PendingRequests()

    async def execute(
     self,
     tool_name: str,
     arguments: dict[str, Any],
     tool_call_id: str | None = None
     
):  
     tool = self.registry.get(tool_name)

     request_id, future = self.pending_requests.create(
         tool_name=tool_name,
         tool_call_id=tool_call_id,
         arguments=arguments,
         source="local",
     )

     try:
         result = await tool.execute(
             tool_name,
             **arguments
         )

         self.pending_requests.resolve(
             request_id,
             result
         )

         return await future

     except Exception as e:
         self.pending_requests.reject(
             request_id,
             str(e)
         )

         raise