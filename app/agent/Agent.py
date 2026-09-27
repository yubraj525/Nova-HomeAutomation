import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class Agent:

    def __init__(self, registry, router):
        self.registry = registry
        self.router = router
        self.client = Groq(api_key=os.getenv("GROQ"))

        self.system_prompt = """
You are NOVA, an AI assistant that can use tools to complete user requests.

Rules:

1. Use tools whenever the user's request requires an available tool.
2. Do not merely describe an action. Execute it using the appropriate tool.
3. A request may require multiple tools. Continue using tools until the
   request is completed.
4. Use the result of previous tools when deciding the next tool call.
5. If a suitable browser tab already exists from a previous tool result,
   reuse its tab ID instead of opening a new tab.
6. Use browser_observe when you need information about the current page
   before performing another browser action.
7. Only return a normal text response when no tool is required or the
   requested action has been completed.
   8. after completetion of a one intent task then only go to another 
   9, for browser observer max 5 limit else use 1-3 as per requirement 
   10. on last where all task executred then reutn a son format as success and failure with content as " successfuly play enjoyded and further
 11. lastly for a one intent task dont repetedly try if the context is same and you are retryng insure after 3rd try it is failure instead no retry and return a failure message with content as " failed to play the video please check your internet connection or the video is not available in your region"
Tool execution follows this pattern:

user request
→ tool call
→ tool result
→ next tool call if required
→ final response
"""

        self.messages = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]

    async def run(self, user_text):

        self.messages.append({
            "role": "user",
            "content": user_text
        })

        for iteration in range(10):

            print(f"\n========== AGENT ITERATION {iteration + 1} ==========")

            response = self._get_completion()

            self._append_assistant_message(response)

            print(f"[MODEL] Content: {response.content}")
            print(f"[MODEL] Reason: {response.reasoning}")
            print(f"[MODEL] Tool calls: {response.tool_calls}")

            if not response.tool_calls:

                if response.content:
                    return response.content

                print("[AGENT] Model returned no content and no tool call.")
                return "I could not determine an action to perform."

            await self._execute_tool_calls(response.tool_calls)

        return "Maximum agent iterations reached."

    def _get_completion(self):

        completion = self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=self.messages,
            tools=self.registry.get_tool_schemas(),
            tool_choice="auto",
            temperature=0.5,
            max_completion_tokens=400,
        )

        return completion.choices[0].message

    def _append_assistant_message(self, response):

        message = {
            "role": "assistant",
            "content": response.content or ""
        }

        if response.tool_calls:

            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
                for tool_call in response.tool_calls
            ]

        self.messages.append(message)

    async def _execute_tool_calls(self, tool_calls):

        for tool_call in tool_calls:

            tool_name = tool_call.function.name

            try:

                arguments = json.loads(
                    tool_call.function.arguments
                )

                print("\n========== TOOL CALL ==========")
                print(f"ID        : {tool_call.id}")
                print(f"Name      : {tool_name}")
                print(f"Arguments : {arguments}")
                print("================================")

                result = await self.router.execute(
                    tool_name,
                    arguments,
                    tool_call_id=tool_call.id
                )

                print(f"[TOOL RESULT] {result}")

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        result,
                        default=str
                    )
                })

            except Exception as error:

                print(
                    f"[TOOL ERROR] "
                    f"{tool_name}: {error}"
                )

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "error": str(error)
                    })
                })