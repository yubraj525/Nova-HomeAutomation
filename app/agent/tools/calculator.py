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

        if operation == "+":
            return a + b
        elif operation == "-":
            return a - b
        elif operation == "*" :
            return a * b
        elif operation == "/" :
            if b == 0:
                raise ValueError("Cannot divide by zero")
            return a / b

        raise ValueError("Unknown operation")