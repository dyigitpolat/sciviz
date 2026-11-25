"""``inkcenter.keep_clear_of_discs``: lines of matplotlib text keep a floor of white between their glyph outlines and
the disc marks beside them, whatever the value a line prints.

A value that grows widens its line toward a mark (a count of 15,500,000 that becomes 20,000,000 moves its mark along a
log axis under the line's commas), and a fixed placement then stands closer than the floor. The rule moves each line
that stands too close, as a whole (the texts that share its baseline keep it), away from the nearest disc by the least
step that gives the floor, and leaves every other line where it is. ``ink_gap`` is the measure: the least distance in
points between a text's glyph outlines and a disc's edge.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from sciviz import inkcenter  # noqa: E402

FLOOR = 0.8
RADIUS = 1.5


def _figure():
    fig, ax = plt.subplots(figsize=(3.0, 1.0), dpi=300)
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")
    return fig, ax


def _row(ax, y, head, rest, lift=2.0):
    kw = dict(xycoords=("axes fraction", "data"), textcoords="offset points", va="baseline", fontsize=6.0)
    r = ax.annotate(rest, xy=(1.0, y), xytext=(0.0, lift), ha="right", **kw)
    fig = ax.figure
    fig.canvas.draw()
    w = r.get_window_extent(fig.canvas.get_renderer()).width * 72.0 / fig.dpi
    h = ax.annotate(head, xy=(1.0, y), xytext=(-w - 1.5, lift), ha="right", fontweight="bold", **kw)
    return [h, r]


def _disc_under(ax, t, frac, gap):
    """A disc whose edge stands ``gap`` points under the ink of ``t`` at the share ``frac`` of its width."""
    fig = ax.figure
    fig.canvas.draw()
    bb = t.get_window_extent(fig.canvas.get_renderer())
    px = fig.dpi / 72.0
    x, cy = bb.x0 + frac * bb.width, bb.y0 - 20.0 * px
    for _ in range(6):
        cy += (inkcenter.ink_gap(t, (x, cy), RADIUS) - gap) * px
    return (x, cy, RADIUS)


def test_a_line_too_close_moves_to_the_floor_and_keeps_its_baseline():
    fig, ax = _figure()
    line = _row(ax, 0.5, "0", "of 20,000,000")
    disc = _disc_under(ax, line[1], 0.55, 0.3)
    assert inkcenter.ink_gap(line[1], disc[:2], disc[2]) == pytest.approx(0.3, abs=0.05)
    y0 = [t.xyann[1] for t in line]
    shifts = inkcenter.keep_clear_of_discs([line], [disc], FLOOR)
    assert shifts[0] > 0.0
    assert min(inkcenter.ink_gap(t, disc[:2], disc[2]) for t in line) >= FLOOR - 1e-6
    assert [t.xyann[1] - y for t, y in zip(line, y0)] == pytest.approx([shifts[0]] * 2)
    plt.close(fig)


def test_a_line_already_clear_and_a_line_far_away_stay():
    fig, ax = _figure()
    near = _row(ax, 0.5, "0", "of 15,500,000")
    far = _row(ax, 0.1, "0", "of 600")
    disc = _disc_under(ax, near[1], 0.55, 1.2)
    before = [t.xyann for t in near + far]
    assert inkcenter.keep_clear_of_discs([near, far], [disc], FLOOR) == [0.0, 0.0]
    assert [t.xyann for t in near + far] == before
    plt.close(fig)


def test_the_measure_is_the_white_between_outline_and_disc_edge():
    fig, ax = _figure()
    t = _row(ax, 0.5, "0", "of 20,000,000")[1]
    a = _disc_under(ax, t, 0.5, 0.5)
    b = _disc_under(ax, t, 0.5, 1.0)
    assert inkcenter.ink_gap(t, a[:2], a[2]) == pytest.approx(0.5, abs=0.05)
    assert inkcenter.ink_gap(t, b[:2], b[2]) == pytest.approx(1.0, abs=0.05)
    plt.close(fig)


def test_a_line_that_cannot_reach_the_floor_within_the_limit_is_refused():
    fig, ax = _figure()
    line = _row(ax, 0.5, "0", "of 20,000,000")
    disc = _disc_under(ax, line[1], 0.55, 0.3)
    with pytest.raises(ValueError):
        inkcenter.keep_clear_of_discs([line], [disc], FLOOR, limit=0.1)
    plt.close(fig)
