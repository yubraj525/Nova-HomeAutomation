from .base import Tool
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

    async def execute(self, arguments):
        # We will implement this next.
        pass