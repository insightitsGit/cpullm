"""Evaluate the arithmetic a prompt actually writes.

The result is a calculation. It is not a stored proposition, and it is not
spoken as one. An expression the parser does not recognize is reported as
missing. It is not guessed.
"""

from __future__ import annotations

import ast
import re
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext

_MAX_EXPONENT = 64
_LIST = re.compile(
    r"\b(sum|product|average|mean)\s+of\s+"
    r"((?:\d+(?:\.\d+)?)(?:\s*(?:,\s*(?:and\s+)?|and\s+)\d+(?:\.\d+)?)+)",
    re.IGNORECASE,
)
_PERCENT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SQRT = re.compile(
    r"(?:square\s+root\s+of|sqrt)\s*\(?\s*(\d+(?:\.\d+)?)\s*\)?",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def solve_math(message: str) -> dict[str, str | bool]:
    """The first arithmetic reading of ``message``.

    ``ok`` is false when the prompt names an operation that cannot be
    completed, including division by zero. The value is a decimal string.
    """
    text = _normalize(message or "")
    special = _special(text)
    if special is not None:
        return special
    expression = _expression(text)
    if expression is None:
        return {
            "ok": False,
            "expression": "",
            "value": "",
            "text": "No arithmetic expression was found.",
        }
    try:
        value = _evaluate(expression)
    except (ValueError, DivisionByZero, InvalidOperation, OverflowError):
        return {
            "ok": False,
            "expression": expression,
            "value": "",
            "text": f"Cannot evaluate {expression}.",
        }
    shown = _format(value)
    return {
        "ok": True,
        "expression": expression,
        "value": shown,
        "text": f"{expression} = {shown}.",
    }


def _normalize(message: str) -> str:
    text = message.replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"\bmultiplied by\b", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdivided by\b", "/", text, flags=re.IGNORECASE)
    text = re.sub(r"\bplus\b", "+", text, flags=re.IGNORECASE)
    text = re.sub(r"\bminus\b", "-", text, flags=re.IGNORECASE)
    text = re.sub(r"\btimes\b", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)\s+over\s+(?=\d)", " / ", text, flags=re.IGNORECASE)
    return text


def _special(text: str) -> dict[str, str | bool] | None:
    percent = _PERCENT.search(text)
    if percent:
        rate = Decimal(percent.group(1)) / Decimal(100)
        whole = Decimal(percent.group(2))
        value = rate * whole
        expression = f"{percent.group(1)}% of {percent.group(2)}"
        shown = _format(value)
        return {"ok": True, "expression": expression, "value": shown, "text": f"{expression} = {shown}."}
    root = _SQRT.search(text)
    if root:
        number = Decimal(root.group(1))
        if number < 0:
            return {
                "ok": False,
                "expression": f"sqrt({root.group(1)})",
                "value": "",
                "text": "Cannot take the square root of a negative number.",
            }
        shown = _format(number.sqrt())
        expression = f"sqrt({root.group(1)})"
        return {"ok": True, "expression": expression, "value": shown, "text": f"{expression} = {shown}."}
    listed = _LIST.search(text)
    if listed:
        kind = listed.group(1).casefold()
        numbers = [Decimal(item) for item in _NUMBER.findall(listed.group(2))]
        if kind == "product":
            value = Decimal(1)
            for item in numbers:
                value *= item
        elif kind in {"average", "mean"}:
            value = sum(numbers, Decimal(0)) / Decimal(len(numbers))
        else:
            value = sum(numbers, Decimal(0))
        expression = f"{kind} of {', '.join(_format(item) for item in numbers)}"
        shown = _format(value)
        return {"ok": True, "expression": expression, "value": shown, "text": f"{expression} = {shown}."}
    return None


def _expression(text: str) -> str | None:
    pieces = list(re.finditer(r"\d+(?:\.\d+)?|\*\*|[()+*/%-]", text))
    groups: list[list[re.Match[str]]] = []
    current: list[re.Match[str]] = []
    for piece in pieces:
        if current and text[current[-1].end() : piece.start()].strip():
            groups.append(current)
            current = []
        current.append(piece)
    if current:
        groups.append(current)
    best: str | None = None
    for group in groups:
        tokens = [item.group(0) for item in group]
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                candidate = "".join(tokens[start:end])
                if not re.search(r"\d", candidate) or not re.search(r"[+\-*/%]", candidate):
                    continue
                try:
                    ast.parse(candidate, mode="eval")
                except SyntaxError:
                    continue
                if best is None or len(candidate) > len(best):
                    best = candidate
    return best


def _evaluate(expression: str) -> Decimal:
    tree = ast.parse(expression, mode="eval")
    with localcontext() as ctx:
        ctx.prec = 50
        return _walk(tree.body)


def _walk(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _walk(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
        left = _walk(node.left)
        right = _walk(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise DivisionByZero
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise DivisionByZero
            return left // right
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise DivisionByZero
            return left % right
        return _power(left, right)
    raise ValueError("unsupported expression")


def _power(left: Decimal, right: Decimal) -> Decimal:
    if right != right.to_integral_value():
        raise ValueError("fractional powers are limited to square root")
    exponent = int(right)
    if abs(exponent) > _MAX_EXPONENT:
        raise ValueError("exponent is too large")
    return left ** exponent


def _format(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
