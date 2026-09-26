import json
import os

from groq import Groq
from dotenv import load_dotenv
load_dotenv()

class Agent:

    def __init__(self, registry,router):
    # def __init__(self, client, registry, router):
        self.router = router
        self.client = Groq(api_key=os.getenv("GROQ"))
        self.registry = registry
        # self.router = router

       
        _build_system_prompt= """
        You are a helpful assistant that can use tools to answer questions. only reason a relevent if in action queries go through with provided tools listed to control browser wven have control to observer a result form browsers"""
        self.messages = [
                {"role": "system", "content": _build_system_prompt}
            ]

    async def run(self, user_text):

        # Add user message
        self.messages.append({
            "role": "user",
            "content": user_text
        })

        for _ in range(10):

            completion = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=self.messages,
                tools=self.registry.get_tool_schemas(),
                temperature=0.5,
                max_completion_tokens=100,
            )

            response = completion.choices[0].message

            self.messages.append(response)

            print(f"\nModel Response:\n{response}")

            # No tool → final answer
            if not response.tool_calls:
                print(f"\nFinal Answer in test:\n{response.content}")
                return response.content

            # Execute tools
            for tool_call in response.tool_calls:

                 print("\n========== TOOL CALL ==========")
                 print(f"ID        : {tool_call.id}")
                 print(f"Name      : {tool_call.function.name}")
                 print(f"Arguments : {tool_call.function.arguments}")
                 print("================================\n")

                 try:
                     tool_name = tool_call.function.name

                     print(f"Fetching tool '{tool_name}'...")


                     arguments = json.loads(
                         tool_call.function.arguments
                     )

                     print(
                         f"Executing tool '{tool_name}' "
                         f"with arguments: {arguments}"
                     )

                     result = await self.router.execute(
                         tool_name,
                         arguments,
                         tool_call_id=tool_call.id
                     )

                     print(
                         f"\nTool '{tool_name}' "
                         f"executed successfully"
                     )

                     self.messages.append({
                         "role": "tool",
                         "tool_call_id": tool_call.id,
                         "content": str(result)
                     })

                 except Exception as e:

                     print(
                         f"\nError executing tool "
                         f"'{tool_call.function.name}': {e}"
                     )

                     self.messages.append({
                         "role": "tool",
                         "tool_call_id": tool_call.id,
                         "content": f"Error: {str(e)}"
                     })

            return f"Tool '{tool_name}' executed successfully."

        return "Maximum agent iterations reached."