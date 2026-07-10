"""Core-only routing registry context shared by drawable layers."""

from __future__ import annotations

import contextvars


routing_registry_stack: contextvars.ContextVar = contextvars.ContextVar(
    "sciviz_routing_registry_stack",
    default=None,
)


def register_routing_region(owner, x: float, y: float,
                            width: float, height: float) -> None:
    """Publish a logical container boundary to active route resolvers."""
    stack = routing_registry_stack.get()
    if stack is None:
        return
    key = f"__region_{id(owner):x}"
    for registry in stack:
        registry[key] = (x, y, width, height)
