from app.agent.base import Tool, ToolExecutionContext
from pydantic import BaseModel
from typing import Literal

class CalculatorArgs(BaseModel):
    a: float
    b: float
    operation: Literal["add", "subtract", "multiply", "divide"]

class CalculatorTool(Tool):
    name = "calculator"
    description = "Perform basic arithmetic."
    arguments_model = CalculatorArgs
    executor = None

    async def execute(self, arguments, context: ToolExecutionContext | None = None):
        a = arguments["a"]
        b = arguments["b"]

        operation = arguments["operation"]

        if operation == "add":
            return a + b
        elif operation == "subtract":
            return a - b
        elif operation == "multiply" :
            return a * b
        elif operation == "divide" :
            if b == 0:
                raise ValueError("Cannot divide by zero")
            return a / b

        raise ValueError("Unknown operation")
