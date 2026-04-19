"""Tests for the layout debug recorder and viewer.

Covers three layers:

* Instrumentation: :mod:`sciviz.auto.debug` records a call when (and
  only when) a recorder is installed via :func:`record_into`.
* End-to-end: :meth:`sciviz.diagram.Diagram.save_debug` emits a
  self-contained HTML file whose embedded JSON matches the live
  recording.
* CLI: :mod:`sciviz._cli.debug` loads a Python script, locates the
  :class:`Diagram`, and writes a debug page.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

from sciviz import Anchor, Box, Connect, Diagram, Row
from sciviz.auto.debug import DebugRecorder, active, record_into


# ---------------------------------------------------------------------------
# recorder plumbing
# ---------------------------------------------------------------------------

def test_recorder_is_off_by_default():
    assert active() is None


def test_recorder_scoped_to_context_manager():
    rec = DebugRecorder()
    assert active() is None
    with record_into(rec) as r:
        assert r is rec
        assert active() is rec
    assert active() is None


def test_recorder_nested():
    outer = DebugRecorder()
    inner = DebugRecorder()
    with record_into(outer):
        assert active() is outer
        with record_into(inner):
            assert active() is inner
        assert active() is outer


def test_recorder_captures_routed_connect():
    rec = DebugRecorder()
    d = Diagram(body=Row(
        Anchor("a", Box("alpha")),
        Anchor("b", Box("beta")),
        Connect("a", "b"),
    ))
    with record_into(rec):
        d.render()
    assert len(rec.router_paths) == 1
    path = rec.router_paths[0]
    assert path.src_name == "a"
    assert path.dst_name == "b"
    assert len(path.waypoints) >= 2


def test_recorder_captures_bus_label():
    rec = DebugRecorder()
    d = Diagram(body=Row(
        Anchor("a1", Box("a1")),
        Anchor("a2", Box("a2")),
        Anchor("sink", Box("sink")),
        Connect(["a1", "a2"], "sink", label="concat"),
    ))
    with record_into(rec):
        d.render()
    # Bus produces at least one label placement decision.
    assert len(rec.label_placements) >= 1
    placement = rec.label_placements[0]
    assert placement.chosen.rect
    assert placement.chosen.side in {"above", "below", "left", "right"}
    # candidates are non-trivial
    assert len(placement.candidates) > 4


def test_recorder_summary_counts_match():
    rec = DebugRecorder()
    d = Diagram(body=Row(
        Anchor("a", Box("alpha")),
        Anchor("b", Box("beta")),
        Anchor("c", Box("gamma")),
        Connect("a", "b"),
        Connect("b", "c"),
    ))
    with record_into(rec):
        d.render()
    summary = rec.summary()
    assert summary["router_paths"] == len(rec.router_paths) == 2
    assert summary["router_retried"] >= 0


def test_recorder_to_dict_roundtrips_through_json():
    rec = DebugRecorder()
    d = Diagram(body=Row(
        Anchor("a", Box("alpha")),
        Anchor("b", Box("beta")),
        Connect("a", "b", label="x"),
    ))
    with record_into(rec):
        d.render()
    blob = json.dumps(rec.to_dict())
    parsed = json.loads(blob)
    assert parsed["summary"]["router_paths"] == summary_count(rec)


def summary_count(rec: DebugRecorder) -> int:
    return len(rec.router_paths)


# ---------------------------------------------------------------------------
# save_debug + HTML
# ---------------------------------------------------------------------------

def test_save_debug_writes_html(tmp_path: pathlib.Path):
    d = Diagram(body=Row(
        Anchor("a", Box("alpha")),
        Anchor("b", Box("beta")),
        Connect("a", "b"),
    ))
    out = d.save_debug(tmp_path / "out.html")
    assert out.exists()
    text = out.read_text()
    assert text.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in text
    assert "const DATA = {" in text


def test_save_debug_embeds_recording(tmp_path: pathlib.Path):
    d = Diagram(body=Row(
        Anchor("a", Box("alpha")),
        Anchor("b", Box("beta")),
        Connect("a", "b", label="edge"),
    ))
    out = d.save_debug(tmp_path / "out.html")
    text = out.read_text()
    match = re.search(r"const DATA = (\{.*?\});", text)
    assert match, "DATA token was not substituted"
    data = json.loads(match.group(1))
    assert data["summary"]["router_paths"] >= 1
    assert all("src_name" in r for r in data["router_paths"])


def test_save_debug_has_no_unsubstituted_tokens(tmp_path: pathlib.Path):
    d = Diagram(body=Row(Box("lone")))
    out = d.save_debug(tmp_path / "out.html")
    text = out.read_text()
    unresolved = [tok for tok in ("__SVG__", "__DATA__", "__TITLE__",
                                  "__W__", "__H__", "__SUMMARY_LINE__")
                  if tok in text]
    assert unresolved == [], f"leftover tokens: {unresolved}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_main_renders_debug_page(tmp_path: pathlib.Path):
    script = tmp_path / "demo.py"
    script.write_text(textwrap.dedent("""
        from sciviz import Diagram, Row, Anchor, Box, Connect
        DIAGRAM = Diagram(body=Row(
            Anchor("a", Box("alpha")),
            Anchor("b", Box("beta")),
            Connect("a", "b"),
        ))
    """))
    out = tmp_path / "demo.debug.html"
    from sciviz._cli.debug import main
    rc = main([str(script), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "<!DOCTYPE html>" in out.read_text()


def test_cli_subprocess_smoke(tmp_path: pathlib.Path):
    script = tmp_path / "demo.py"
    script.write_text(textwrap.dedent("""
        from sciviz import Diagram, Row, Box
        DIAGRAM = Diagram(body=Row(Box("a"), Box("b")))
    """))
    out = tmp_path / "demo.debug.html"
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sciviz_debug.py"),
         str(script), "-o", str(out)],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_cli_errors_when_no_diagram(tmp_path: pathlib.Path):
    script = tmp_path / "demo.py"
    script.write_text("x = 1\n")
    out = tmp_path / "demo.debug.html"
    from sciviz._cli.debug import main
    with pytest.raises(LookupError):
        main([str(script), "-o", str(out)])
