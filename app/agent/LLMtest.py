from app.agent import ToolRouter
from app.agent.tools.currenTime import GetTimeTool
from app.agent.tools.calculator import CalculatorTool
from .base import Tool
from .registery import ToolRegistry
from  dotenv import load_dotenv
from groq import Groq
import asyncio
import os


load_dotenv()
client = Groq(api_key=os.getenv("GROQ"))


def create_tool_registry():
    registry = ToolRegistry()

    registry.register(CalculatorTool())
    registry.register(GetTimeTool())
    

    return registry

def llmtest(messages):
    registery = create_tool_registry()
    registery.list_tools()
    tools_schema= registery.print_tools()
        
    


    completion = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=messages,
    tools=registery.print_tools(),
    temperature=0.5,
    max_completion_tokens=400,
    )

    print("LLM Response:", completion.choices[0].message)




if __name__ == "__main__":
    asyncio.run(llmtest("what is 2*2?"))
