from app.agent.pending_manager import PendingRequests

from .base import Tool
import asyncio
import json
class RemoteTool(Tool):

    def __init__(
        self,
        name,
        description,
        parameters,
        websocket,
        client_name,
        requests_manager=PendingRequests(),
    ):
        self.name = name
        self.description = description
        self.parameters = parameters

        self.websocket = websocket
        self.client_name = client_name
        self.pending_requests = requests_manager

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    async def execute(
        self,
        tool_name: str,
        **kwargs
    ) -> str:

        """Execute a remote tool and await its result."""
        if 'tool_call_id' in kwargs:
                        tool_call_id = kwargs.pop('tool_call_id')

        print(
            f"Executing remote tool '{tool_name}' "
            f"with tool call ID: {tool_call_id} "
            f"on client '{self.client_name}' "
            f"with arguments: {kwargs}"
        )

        # 1. Create and register pending request
        request_id, future = self.pending_requests.create(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=kwargs,
            source="remote",
            client_name=self.client_name,
        )

        # 2. Build execution payload
        payload = {
            "type": "execute_tool",
            "request_id": request_id,
            "tool_name": tool_name,
            "arguments": kwargs,
        }

        # 3. Send request to PC Agent
        await self.websocket.send(json.dumps(payload))

        # 4. Wait for PC response
        try:
            result = await asyncio.wait_for(
                future,
                timeout=30.0
            )

            return result

        except asyncio.TimeoutError:
            return (
                f"Error: Remote execution of "
                f"'{tool_name}' timed out on "
                f"client '{self.client_name}'."
            )