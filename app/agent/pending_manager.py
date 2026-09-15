import asyncio
from datetime import datetime
import uuid


class PendingRequests:

    def __init__(self):
        self._requests = {}

    def create(
            self,
            tool_name: str,
            tool_call_id: str | None,
            arguments: dict,
            source: str = "local",
            client_name: str | None = None,
        ):
            request_id = str(uuid.uuid4())
    
            future = asyncio.get_running_loop().create_future()
    
            self._requests[request_id] = {
                "request_id": request_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "source": source,
                "client_name": client_name,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "future": future,
            }
    
            return request_id, future
    def resolve(self, request_id: str, result):
        request = self._requests.pop(request_id, None)

        if request is None:
            print(f"[PendingRequests] Unknown request: {request_id}")
            return

        future = request["future"]

        if not future.done():
            future.set_result(result)

    def reject(self, request_id: str, error):
        request = self._requests.pop(request_id, None)
    
        if request is None:
            print(f"[PendingRequests] Unknown request: {request_id}")
            return
    
        future = request["future"]
    
        if not future.done():
            future.set_exception(RuntimeError(error))
            
    def list(self):
        return [
            {
                key: value
                for key, value in request.items()
                if key != "future"
            }
            for request in self._requests.values()
        ]