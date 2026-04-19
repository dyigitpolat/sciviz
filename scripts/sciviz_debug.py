#!/usr/bin/env python3
"""Wrapper around :mod:`sciviz._cli.debug`.

Keeps the familiar ``scripts/sciviz_debug.py`` invocation for users
working inside the repo, even when the project isn't installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sciviz._cli.debug import main

if __name__ == "__main__":
    raise SystemExit(main())
