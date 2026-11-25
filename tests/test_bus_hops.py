"""A bus hops the wires it crosses, like a routed wire does.

A bus segment that crosses a wire drawn before it jumps it with the
routed wires' hop arc, so the crossing never reads as a junction (a
bus's own T-joins are its only junctions). A bus that crosses nothing
draws exactly the lines it drew before.
"""

from __future__ import annotations

from sciviz import Anchor, Box, Canvas, Column, Row, Theme
from sciviz.auto import router as R
from sciviz.composition import Bus, Flowed


def _render(elem) -> str:
    theme = Theme()
    size = elem.measure(theme)
    canvas = Canvas()
    elem.render(canvas, 0.0, 0.0, theme)
    return canvas.to_svg(size.w, size.h)


def _fan_in(prior_segments=()):
    body = Column(
        Row(Anchor("a", Box("left source")), Anchor("b", Box("right source")),
            gap="xl"),
        Anchor("s", Box("sink")),
        gap="xl", align="center")

    class _Prior:
        """A wire drawn before the bus (a horizontal run across the
        bus's taps, in the gap between sources and sink)."""
        def _render(self, canvas, theme, registry, defer_label=False):
            registry.setdefault("__drawn_segments__", []).extend(
                prior_segments(registry) if callable(prior_segments)
                else prior_segments)
            return None
    return Flowed(body, flows=[_Prior(), Bus(sources=["a", "b"], sinks="s")])


def _hop_arcs(svg: str) -> int:
    import re
    return sum(len(re.findall(r"\bA\s*[\d.]", d))
               for d in re.findall(r'<path[^>]* d="([^"]+)"', svg))


def test_bus_crossing_nothing_is_unchanged():
    """No drawn wire in the way: plain lines, no arcs, and the lines of
    a bus drawn through the hop helper equal the ones drawn before."""
    svg = _render(_fan_in())
    assert _hop_arcs(svg) == 0
    import re
    assert len(re.findall(r"<line ", svg)) >= 3


def test_bus_hops_a_wire_it_crosses():
    def across_taps(registry):
        ax, ay, aw, ah = registry["a"]
        bx, by, bw, bh = registry["b"]
        sy = registry["s"][1]
        # a quarter of the way down the gap: both source taps cross it
        y = ay + ah + 0.25 * (sy - ay - ah)
        return [(ax - 20.0, y, bx + bw + 20.0, y)]
    svg = _render(_fan_in(across_taps))
    assert _hop_arcs(svg) == 2
