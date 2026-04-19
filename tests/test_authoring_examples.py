"""Execute every code example in docs/AUTHORING.md.

Keeps the authoring guide truthful: any rename, signature change, or
deprecation that breaks a snippet breaks this test.

Each fenced ```python ...``` block is exec'd in a fresh namespace
prepopulated with every public name from :mod:`sciviz`. If the block
constructs a :class:`Diagram`, we also do a smoke render to SVG in a
temp dir to catch downstream measurement / routing bugs.
"""
from __future__ import annotations

import pathlib
import re

import pytest


AUTHORING_MD = pathlib.Path(__file__).resolve().parents[1] / "docs" / "AUTHORING.md"


def _python_blocks():
    """Yield each ```python ... ``` fenced block from AUTHORING.md."""
    text = AUTHORING_MD.read_text()
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def _blocks_with_ids():
    for i, block in enumerate(_python_blocks()):
        first = block.strip().split("\n", 1)[0][:50]
        yield pytest.param(block, id=f"block{i:02d}-{first!r}")


@pytest.mark.parametrize("block", list(_blocks_with_ids()))
def test_authoring_block_executes(block: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    import sciviz

    monkeypatch.chdir(tmp_path)

    ns: dict = {name: getattr(sciviz, name) for name in sciviz.__all__}
    ns["__name__"] = "authoring_example"
    exec(compile(block, str(AUTHORING_MD), "exec"), ns)

    for value in ns.values():
        if isinstance(value, sciviz.Diagram):
            value.save(str(tmp_path / "out.svg"))
