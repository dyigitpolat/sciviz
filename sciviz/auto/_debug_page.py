"""Render the interactive debug page from a :class:`DebugRecorder`.

Standalone helper used by :meth:`sciviz.diagram.Diagram.save_debug` and
the ``sciviz-debug`` CLI.  The implementation is intentionally tiny:
it reads ``_debug_template.html``, substitutes a handful of tokens,
and writes out a single self-contained file the user can open in any
modern browser.

Token contract
--------------

The template contains these string tokens (not Jinja, not Mustache --
just ``str.replace``):

* ``__TITLE__``         --  `str`, inserted verbatim (HTML-escaped).
* ``__W__`` / ``__H__`` --  `float`, diagram size in SVG pixels.
* ``__SVG__``           --  the rendered SVG source.
* ``__SUMMARY_LINE__``  --  short human summary shown under the title.
* ``__DATA__``          --  JSON-serialised ``recorder.to_dict()``.
"""
from __future__ import annotations

import html
import json
import pathlib
from typing import Any

from .debug import DebugRecorder


_TEMPLATE_PATH = pathlib.Path(__file__).parent / "_debug_template.html"


def render_debug_html(*,
                      title: str,
                      svg: str,
                      svg_width: float,
                      svg_height: float,
                      recorder: DebugRecorder) -> str:
    """Return a complete HTML document for the debug viewer."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    data: Any = recorder.to_dict()
    data_json = json.dumps(data, default=_json_fallback, separators=(",", ":"))
    summary = data["summary"]
    summary_line = (
        f"{summary['router_paths']} routed paths "
        f"({summary['router_retried']} retried) · "
        f"{summary['label_placements']} label placements "
        f"({summary['label_overlap_nonzero']} with overlap)"
    )
    replacements = {
        "__TITLE__":        html.escape(title),
        "__W__":            _fmt(svg_width),
        "__H__":            _fmt(svg_height),
        "__SVG__":          _strip_xml_prolog(svg),
        "__SUMMARY_LINE__": html.escape(summary_line),
        "__DATA__":         data_json,
    }
    out = template
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _fmt(value: float) -> str:
    return f"{float(value):.3f}"


def _strip_xml_prolog(svg: str) -> str:
    """SVG produced by sciviz does not ship an <?xml ...?> prolog, but
    strip it defensively so the document stays HTML-valid if it ever
    grows one.
    """
    s = svg.lstrip()
    if s.startswith("<?xml"):
        s = s.split("?>", 1)[1].lstrip()
    return s


def _json_fallback(obj: Any) -> Any:
    """Escape-hatch for non-JSONable dataclass fields (tuples become
    lists automatically; anything exotic gets stringified)."""
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    return str(obj)
