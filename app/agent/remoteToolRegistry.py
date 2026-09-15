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
    ):
        self.name = name
        self.description = description
        self.parameters = parameters

        self.websocket = websocket
        self.client_name = client_name

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    async def execute(self,tool_name, **kwargs) -> str:
        """Sends execution payload over WebSocket and awaits tool_result."""
        print(f"Executing remote tool '{self.name}' on client '{tool_name}' with arguments: {kwargs}")
        # call_id = str(uuid.uuid4())/
        loop = asyncio.get_running_loop()

        # 1. Create a Future to block until WebSocket receives the response
        future = loop.create_future()
        # self.pending_calls[call_id] = future

        # 2. Build execution payload for PC agent
        payload = {
            "type": "execute_tool",
            # "call_id": call_id,
            "tool_name": tool_name,
            "arguments": kwargs,
        }

        # 3. Transmit command over WebSocket
        await self.websocket.send(json.dumps(payload))

        # 4. Await response or timeout safely
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            return f"Error: Remote execution of '{self.name}' timed out on client '{self.client_name}'."
        # finally:
            # Clean up pending call dictionary
            # self.pending_calls.pop(call_id, None)