from app.agent.base import Tool
class CalculatorTool(Tool):
    name = "calculator"
    description = "Perform basic arithmetic."

    async def execute(self, arguments):
        a = arguments["a"]
        b = arguments["b"]

        operation = arguments["operation"]

        if operation == "add":
            return a + b
        elif operation == "subtract":
            return a - b
        elif operation == "multiply":
            return a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Cannot divide by zero")
            return a / b

        raise ValueError("Unknown operation")