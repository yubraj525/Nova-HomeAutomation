from app.agent.base import Tool
from pydantic import BaseModel
class CalculatorArgs(BaseModel):
    a: float
    b: float
    operation: str

class CalculatorTool(Tool):
    name = "calculator"
    description = "Perform basic arithmetic."
    arguments_model = CalculatorArgs

    async def execute(self, arguments):
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