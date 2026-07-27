"""Free-ink extraction for the connector subsystem.

The historical obstacle model for wire routing and label placement was
"named anchors only": rectangles that authors happened to wrap in
:class:`~sciviz.connect.Anchor`. Everything else that paints glyphs --
zone headers, captions, chips, stray annotations -- was invisible, so
routed wires could run straight through a title and labels could land on
free-standing text.

:func:`free_text_rects` closes that hole generically. The
:class:`~sciviz.core.Canvas` keeps a per-item ink ledger with real glyph
metrics; this module filters that ledger down to the text ink that is
*not* already represented by a registered anchor rectangle (text inside
an anchored card is protected by the card itself). The result is handed
to the router as additional obstacles and to the label placer as
additional collision rectangles.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

Rect = Tuple[float, float, float, float]


def _registry_rects(registry: dict) -> List[Rect]:
    out: List[Rect] = []
    for name, b in registry.items():
        if name.startswith("__"):
            continue
        if isinstance(b, tuple) and len(b) == 4:
            x, y, w, h = b
            out.append((x, y, x + w, y + h))
    return out


def _contained(inner: Rect, outer: Rect, eps: float) -> bool:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    return (ix0 >= ox0 - eps and iy0 >= oy0 - eps
            and ix1 <= ox1 + eps and iy1 <= oy1 + eps)


def free_text_rects(canvas, registry: dict, *,
                    eps: float = 1.0,
                    margin: float = 0.0) -> List[Rect]:
    """Text-ink rectangles not covered by any registered anchor.

    ``eps`` is the containment slack: a text run whose rect sits within
    an anchor rect grown by ``eps`` counts as that anchor's interior
    detail and is dropped (the anchor already acts as the obstacle).
    ``margin`` inflates the surviving rectangles, giving wires and
    labels breathing room around free-standing text.
    """
    ink = getattr(canvas, "ink_items", None)
    if ink is None:
        return []
    covers = _registry_rects(registry)
    out: List[Rect] = []
    for rect in canvas.ink_items("text"):
        if any(_contained(rect, cover, eps) for cover in covers):
            continue
        x0, y0, x1, y1 = rect
        if x1 - x0 <= 0.0 or y1 - y0 <= 0.0:
            continue
        out.append((x0 - margin, y0 - margin, x1 + margin, y1 + margin))
    return out


def rects_excluding_endpoints(rects: Sequence[Rect],
                              endpoint_bboxes: Sequence[Tuple[float, float,
                                                              float, float]],
                              *, eps: float = 0.5) -> List[Rect]:
    """Drop rects that intersect any endpoint bbox ``(x, y, w, h)``.

    The router treats its own endpoints as enterable, so ink that clings
    to an endpoint's boundary (its header text, a port glyph) must not
    forbid the wire from reaching that boundary.
    """
    out: List[Rect] = []
    for (x0, y0, x1, y1) in rects:
        hit = False
        for (bx, by, bw, bh) in endpoint_bboxes:
            if (x0 < bx + bw + eps and x1 > bx - eps
                    and y0 < by + bh + eps and y1 > by - eps):
                hit = True
                break
        if not hit:
            out.append((x0, y0, x1, y1))
    return out
