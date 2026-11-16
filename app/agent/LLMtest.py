import asyncio

from app.agent.ToolRouter import ToolRouter
from app.agent.pending_manager import PendingRequests
from app.agent.tools.currenTime import GetTimeTool
from app.agent.tools.calculator import CalculatorTool
from app.agent.registery import ToolRegistry
from app.agent.Agent import Agent
from app.agent.tools.system import SystemInfoTool

def create_tool_registry():
    registry = ToolRegistry()

    registry.register(CalculatorTool())
    registry.register(GetTimeTool())
    registry.register(SystemInfoTool())
    

    return registry




async def main():
    registery = create_tool_registry()
    router = ToolRouter(registery, PendingRequests())
    agent = Agent(registery, router)
    await agent.run("what time is it now ?")

if __name__ == "__main__":
    asyncio.run(main())
