"""Opt-in pixel-parity test for gallery PNG outputs.

Set the env var ``SCIVIZ_GALLERY_PARITY=1`` to enable. This regenerates
every gallery file and compares SHA-256 of the resulting PNGs against the
baseline in ``tests/fixtures/gallery_hashes.json``.

The test is opt-in because regenerating all galleries takes ~8 seconds
and produces sidecar ``.pdf`` and ``.svg`` files we don't want to rewrite
on every test run.
"""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
GALLERY_DIR = REPO_ROOT / "gallery"
OUT_DIR = REPO_ROOT / "_out"
HASHES_FILE = Path(__file__).parent / "fixtures" / "gallery_hashes.json"
ALLOWED_DIFFS_FILE = Path(__file__).parent / "fixtures" / "gallery_allowed_diffs.json"


def _load_hashes() -> dict[str, str]:
    return json.loads(HASHES_FILE.read_text())


def _allowed_diffs() -> dict[str, str]:
    if not ALLOWED_DIFFS_FILE.exists():
        return {}
    return json.loads(ALLOWED_DIFFS_FILE.read_text())


@pytest.mark.skipif(
    os.environ.get("SCIVIZ_GALLERY_PARITY") != "1",
    reason="set SCIVIZ_GALLERY_PARITY=1 to run",
)
def test_gallery_pixel_parity():
    baseline = _load_hashes()
    allowed = _allowed_diffs()

    for gallery_path in sorted(GALLERY_DIR.glob("*.py")):
        subprocess.run(
            [sys.executable, str(gallery_path)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

    drift: list[str] = []
    for name, expected in baseline.items():
        png = OUT_DIR / name
        assert png.exists(), f"missing expected gallery output: {png}"
        actual = hashlib.sha256(png.read_bytes()).hexdigest()
        if actual != expected and name not in allowed:
            drift.append(f"{name}: expected {expected[:12]} got {actual[:12]}")

    if drift:
        raise AssertionError(
            "Gallery pixel drift:\n  "
            + "\n  ".join(drift)
            + "\n"
            "If intentional, update tests/fixtures/gallery_hashes.json, "
            "or whitelist with a justification in "
            "tests/fixtures/gallery_allowed_diffs.json."
        )
