"""Implicit-obstacle registration hook used by Box (and future primitives)."""

from __future__ import annotations

_AUTO_OBSTACLE_COUNTER = [0]

def _register_implicit_obstacle(x: float, y: float, w: float, h: float) -> None:
    """Publish a rendered primitive's bbox as an anonymous obstacle.

    Any :class:`Box` (or future primitive that calls this) shows up in
    the active :class:`Flowed` registry so the orthogonal router routes
    around it, even if the author never wrapped it in an explicit
    :class:`Anchor`. Silently no-ops when no ``Flowed`` scope is active.
    """
    from ..composition import _anchor_stack
    stack = _anchor_stack.get()
    if not stack:
        return
    _AUTO_OBSTACLE_COUNTER[0] += 1
    name = f"_auto_obstacle_{_AUTO_OBSTACLE_COUNTER[0]}"
    for reg in stack:
        reg[name] = (x, y, w, h)
