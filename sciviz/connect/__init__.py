"""Unified connector API.

A single public element, :class:`Connect`, subsumes the former
`Arrow`, `Connector`, `Flow`, `Flowed`, `Labeled`, and `Bus`.

See ``docs/dev/connect-api.md`` for the full design note.
"""
from __future__ import annotations

from .connector import Connect
from .anchor import Anchor

__all__ = ["Connect", "Anchor"]
