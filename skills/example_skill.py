"""Example skill — a simple calculator and weather placeholder.

This demonstrates how to write skills for AILIEN. Create your own skills
by copying this pattern and placing them in the ``skills/`` directory.
"""

from skills import Skill, tool


class ExampleSkill(Skill):
    name = "example"
    description = "Example skill with utility tools"

    @tool(description="Add two numbers together")
    def add(self, a: float, b: float) -> str:
        """Add two numbers."""
        return f"{a} + {b} = {a + b}"

    @tool(description="Multiply two numbers")
    def multiply(self, a: float, b: float) -> str:
        """Multiply two numbers."""
        return f"{a} × {b} = {a * b}"

    @tool(description="Get a motivational quote")
    def motivational_quote(self) -> str:
        """Return a random motivational quote."""
        import random
        quotes = [
            "The only way to do great work is to love what you do. — Steve Jobs",
            "Believe you can and you're halfway there. — Theodore Roosevelt",
            "It does not matter how slowly you go as long as you do not stop. — Confucius",
            "The future belongs to those who believe in the beauty of their dreams. — Eleanor Roosevelt",
            "In the middle of difficulty lies opportunity. — Albert Einstein",
        ]
        return random.choice(quotes)
