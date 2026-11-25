"""The shaft check: every drawn arrowhead with the straight shaft behind it.

An arrowhead that sits on the last bend of its wire reads as a triangle
glued to its target, not as an arrow that arrives. This module measures,
on the rendered SVG, the straight run between the last bend of each stroke
that carries an arrow marker and the stroke's end, and the part of that
run that stays visible behind the head's base. It reads the drawing, not
the connector objects, so it covers every primitive that draws a marker
(routed ``Connect``, bus taps, ``Arrow``, chart annotations) alike.

    ends = arrow_ends(diagram.render(embed_fonts=False))
    short = [e for e in ends if e.shaft < 8.0]

or, on a diagram, ``diagram.arrow_ends()`` and
``diagram.short_shafts(min_shaft)``.

Lengths are canvas units (printed points for ``Diagram.for_paper``).
A stroke inside a transformed group is measured in the group's own
units.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

__all__ = ["ArrowEnd", "arrow_ends", "short_shafts"]


@dataclass(frozen=True)
class ArrowEnd:
    """One drawn arrowhead and the run of stroke that enters it.

    ``tip``      -- the stroke end that carries the head.
    ``bend``     -- where the last straight run before the head starts
                    (the wire's last bend, or its other end).
    ``run``      -- length of that run.
    ``head``     -- length of the head along the shaft.
    ``shaft``    -- the run left visible behind the head's base (never
                    negative).
    ``straight`` -- False when the stroke enters the head on a curve (the
                    run is then the chord of the last curve).
    ``marker``   -- the marker's id.
    """
    tip: Tuple[float, float]
    bend: Tuple[float, float]
    run: float
    head: float
    shaft: float
    stroke_width: float
    straight: bool
    marker: str

    def describe(self) -> str:
        return (f"arrow into ({self.tip[0]:.1f}, {self.tip[1]:.1f}): "
                f"shaft {self.shaft:.2f} behind a {self.head:.2f} head "
                f"(run {self.run:.2f} from the bend at "
                f"({self.bend[0]:.1f}, {self.bend[1]:.1f}))")


_ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
_MARKER = re.compile(r"<marker\b([^>]*)>")
_STROKE = re.compile(r"<(line|path|polyline)\b([^>]*?)/?>")
_URL = re.compile(r"url\(#([^)]+)\)")
_TOKEN = re.compile(
    r"([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2,
         "A": 7}


def _attrs(text: str) -> dict:
    return dict(_ATTR.findall(text))


def _num(value: Optional[str], default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _path_vertices(d: str) -> List[Tuple[float, float, bool]]:
    """The vertices of a path as ``(x, y, straight)``: ``straight`` says
    whether the piece that ends on the vertex is a straight line."""
    seq: list = []
    for cmd, num in _TOKEN.findall(d):
        seq.append(cmd if cmd else float(num))
    out: List[Tuple[float, float, bool]] = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None
    i = 0
    while i < len(seq):
        if isinstance(seq[i], str):
            cmd = seq[i]
            i += 1
            if cmd in "Zz":
                out.append((start[0], start[1], True))
                cur = start
                continue
        if cmd is None or cmd in "Zz":
            break
        need = _ARGS[cmd.upper()]
        args = seq[i:i + need]
        if len(args) < need or any(isinstance(a, str) for a in args):
            break
        i += need
        rel, up = cmd.islower(), cmd.upper()
        if up == "H":
            x, y = args[0] + (cur[0] if rel else 0.0), cur[1]
        elif up == "V":
            x, y = cur[0], args[0] + (cur[1] if rel else 0.0)
        else:
            x = args[-2] + (cur[0] if rel else 0.0)
            y = args[-1] + (cur[1] if rel else 0.0)
        out.append((x, y, up in "MLHV"))
        cur = (x, y)
        if up == "M":
            start = cur
            cmd = "l" if rel else "L"      # further pairs are line-tos
    return out


def _vertices(tag: str, a: dict) -> List[Tuple[float, float, bool]]:
    if tag == "line":
        return [(_num(a.get("x1")), _num(a.get("y1")), True),
                (_num(a.get("x2")), _num(a.get("y2")), True)]
    if tag == "polyline":
        nums = [float(v) for v in
                re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", a.get("points", ""))]
        return [(x, y, True) for x, y in zip(nums[0::2], nums[1::2])]
    return _path_vertices(a.get("d", ""))


def _last_run(verts, at_end: bool):
    """(tip, bend, straight) of the stroke's last distinct run at one end."""
    pts = list(verts) if at_end else list(reversed(verts))
    if len(pts) < 2:
        return None
    tip = pts[-1]
    # at the start of a stroke the first piece's kind is on the next vertex
    straight = tip[2] if at_end else pts[-2][2]
    for prev in reversed(pts[:-1]):
        if math.hypot(tip[0] - prev[0], tip[1] - prev[1]) > 1e-6:
            return (tip[0], tip[1]), (prev[0], prev[1]), bool(straight)
    return None


def arrow_ends(svg: str, *, scale: float = 1.0) -> List[ArrowEnd]:
    """Every arrowhead drawn in ``svg`` with the run that enters it.

    ``scale`` multiplies every length and coordinate (canvas units to the
    unit the caller reports in).
    """
    markers = {}
    for m in _MARKER.finditer(svg):
        a = _attrs(m.group(1))
        if "id" not in a:
            continue
        box = [float(v) for v in
               re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", a.get("viewBox", ""))]
        vbw = box[2] if len(box) == 4 and box[2] > 0 else 0.0
        width = _num(a.get("markerWidth"), 3.0)
        ref = _num(a.get("refX"), 0.0)
        behind = (ref / vbw) if vbw else 0.0
        markers[a["id"]] = (width, behind,
                            a.get("markerUnits", "strokeWidth"))
    out: List[ArrowEnd] = []
    for m in _STROKE.finditer(svg):
        tag, a = m.group(1), _attrs(m.group(2))
        ends = []
        for key, at_end in (("marker-end", True), ("marker-start", False)):
            u = _URL.search(a.get(key, ""))
            if u and u.group(1) in markers:
                ends.append((u.group(1), at_end))
        if not ends:
            continue
        verts = _vertices(tag, a)
        sw = _num(a.get("stroke-width"), 1.0)
        for mid, at_end in ends:
            got = _last_run(verts, at_end)
            if got is None:
                continue
            tip, bend, straight = got
            width, behind, units = markers[mid]
            head = width * (sw if units == "strokeWidth" else 1.0)
            run = math.hypot(tip[0] - bend[0], tip[1] - bend[1])
            shaft = max(0.0, run - behind * head)
            out.append(ArrowEnd(
                tip=(tip[0] * scale, tip[1] * scale),
                bend=(bend[0] * scale, bend[1] * scale),
                run=run * scale, head=head * scale, shaft=shaft * scale,
                stroke_width=sw * scale, straight=straight, marker=mid))
    return out


def short_shafts(svg: str, min_shaft: float, *,
                 scale: float = 1.0) -> List[ArrowEnd]:
    """The arrowheads of ``svg`` whose entering shaft is under ``min_shaft``
    (in the scaled unit)."""
    return [e for e in arrow_ends(svg, scale=scale)
            if e.shaft < float(min_shaft) - 1e-6]
