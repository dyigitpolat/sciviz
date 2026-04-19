"""Anchor primitive: wrap an element and register its bbox under a name.

This is currently a thin re-export of the implementation living in
``sciviz.composition``. Phase 3e will physically move the class body here.
"""
from __future__ import annotations

from ..composition import Anchor

__all__ = ["Anchor"]
