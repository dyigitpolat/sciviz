"""Lock the public `sciviz.__all__` surface against silent drift.

The expected surface is snapshotted in `tests/fixtures/public_surface.json`.
When we intentionally change the exported names (e.g. prune dead code or
introduce new primitives), we update the snapshot in the same commit and
the diff is reviewable.
"""
from __future__ import annotations

import json
from pathlib import Path

import sciviz


FIXTURE = Path(__file__).parent / "fixtures" / "public_surface.json"


def _expected() -> list[str]:
    return json.loads(FIXTURE.read_text())


def test_public_surface_matches_snapshot():
    actual = sorted(sciviz.__all__)
    expected = _expected()
    assert actual == expected, (
        "Public surface drift detected.\n"
        f"  added:   {sorted(set(actual) - set(expected))}\n"
        f"  removed: {sorted(set(expected) - set(actual))}\n"
        "If intentional, update tests/fixtures/public_surface.json."
    )


def test_every_name_resolves():
    """Every name in __all__ must be an attribute of the package."""
    missing = [n for n in sciviz.__all__ if not hasattr(sciviz, n)]
    assert not missing, f"__all__ names not resolvable on sciviz: {missing}"


def test_all_is_unique():
    names = list(sciviz.__all__)
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate names in __all__: {sorted(dupes)}"
