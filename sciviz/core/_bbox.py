"""BBox: width/height pair measured by every sciviz element."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BBox:
    """Simple (width, height) pair. All sciviz elements measure to this."""
    w: float
    h: float

    def expand(self, *, dx: float = 0, dy: float = 0) -> "BBox":
        return BBox(self.w + dx, self.h + dy)
