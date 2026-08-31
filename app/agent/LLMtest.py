import asyncio
from email import message
import json
import os

from dotenv import load_dotenv
from groq import Groq
from sympy import true

from app.agent.ToolRouter import ToolRouter
from app.agent.tools.currenTime import GetTimeTool
from app.agent.tools.calculator import CalculatorTool
from app.agent.registery import ToolRegistry

load_dotenv()
client = Groq(api_key=os.getenv("GROQ"))
def create_tool_registry():
    registry = ToolRegistry()

    registry.register(CalculatorTool())
    registry.register(GetTimeTool())
    

    return registry



async def llmtest(user_text):

    registery = create_tool_registry()
    registery.list_tools()
    router = ToolRouter(registery)
    tools_schema= registery.get_tool_schemas()
    print("Tools Schema:", tools_schema)
        

    messages = [
        {
            "role": "user",
            "content": user_text
        }
    ]
    while true:
        completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages,
        tools=registery.get_tool_schemas(),
        temperature=0.5,
        max_completion_tokens=100,
    )
        response = completion.choices[0].message
        messages.append(response)
    
        if not response.tool_calls:
         print(response.content)
         break
        
        for tool_call in response.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
        
                    result =  await router.execute(tool_name, arguments)
                    print(f"\nTool '{tool_name}' executed with result: {result}")
                    
        # 5. Add tool result
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        })
    
        





if __name__ == "__main__":
    response =asyncio.run(llmtest("what is 2*2?"))
   
