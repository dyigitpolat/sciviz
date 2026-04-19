"""Smoke test every gallery file: imports cleanly and the Diagram measures.

We stub out `Diagram.save_all` so the galleries don't write files during
testing. The assertion is that every gallery module constructs a `Diagram`
whose `measure()` returns a positive bbox.
"""
from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import patch

import pytest

from sciviz import Diagram


GALLERY_DIR = Path(__file__).parent.parent / "gallery"
GALLERY_FILES = sorted(GALLERY_DIR.glob("*.py"))


@pytest.mark.parametrize("gallery_path", GALLERY_FILES, ids=[p.stem for p in GALLERY_FILES])
def test_gallery_runs_and_measures(gallery_path: Path):
    captured: dict = {}

    def _capture(self, base_path, *, formats=("svg", "pdf", "png"), dpi=192.0):
        captured["diagram"] = self
        return Path(base_path)

    with patch.object(Diagram, "save_all", _capture):
        runpy.run_path(str(gallery_path), run_name="__main__")

    assert "diagram" in captured, (
        f"{gallery_path.name} never called Diagram.save_all; "
        "smoke test cannot verify it."
    )
    diagram = captured["diagram"]
    bbox = diagram.measure()
    assert bbox.w > 0 and bbox.h > 0, (
        f"{gallery_path.name} produced an empty diagram: {bbox!r}"
    )
