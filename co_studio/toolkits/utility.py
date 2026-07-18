"""Utility toolkit: small deterministic demo tools (no external calls)."""

from __future__ import annotations

import ast
import datetime
import operator
import random
from typing import Any, Callable

_OPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval(node: ast.expr) -> Any:
    """Recursively evaluate a whitelisted arithmetic AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. "3 * (4 + 5) ** 2"."""
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except Exception as exc:  # noqa: BLE001 — surface the reason to the LLM
        return f"Could not evaluate: {exc}"


def get_weather(city: str) -> str:
    """Get today's weather for a city (demo data, deterministic per city)."""
    condition = ["Sunny", "Cloudy", "Rainy", "Windy", "Clear", "Foggy"][abs(hash(city.lower())) % 6]
    return f"{city.title()}: {condition}, {12 + abs(hash(city.lower())) % 18}°C"


def current_time() -> str:
    """Return the current local date and time."""
    return datetime.datetime.now().strftime("%A %Y-%m-%d %H:%M:%S")


def roll_dice(sides: int = 6, count: int = 1) -> str:
    """Roll `count` dice of `sides` sides; returns the rolls and their total."""
    rolls = [random.randint(1, max(2, sides)) for _ in range(max(1, count))]
    return f"Rolled {rolls} — total {sum(rolls)}"


def reverse_text(text: str) -> str:
    """Reverse a string."""
    return text[::-1]


def is_prime(n: int) -> bool:
    """Return whether n is a prime number."""
    if n < 2:
        return False
    return all(n % i for i in range(2, int(n**0.5) + 1))


def fibonacci(n: int) -> int:
    """Return the nth Fibonacci number (0-indexed)."""
    a, b = 0, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def tools() -> list[Any]:
    """Tool functions for this group."""
    return [add, calculate, get_weather, current_time, roll_dice, reverse_text, is_prime, fibonacci]


def plugins() -> list[Any]:
    """No plugins needed for plain utility tools."""
    return []
