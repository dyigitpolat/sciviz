"""Timeline point events: a task with no duration is a typed marker on its
lane, repeats show a count, and lane and tick labels take size tokens so a
timeline fits in a card. Without these the timeline is unchanged."""
from __future__ import annotations

import pytest

from sciviz import Timeline
from sciviz.elements import Marker
from sciviz.core import Theme

from tests._recording_canvas import assert_inside, render

TH = Theme()


def _events():
    return [("Calibration", [(0.5, None, "start", Marker("square", color="#1f4e79")),
                                    (0.5, None, "start", Marker("square", color="#1f4e79"))]),
            ("Samples", [(g + 0.5, None, "sample", "#3b82f6")
                                 for g in (1, 3, 5, 7, 9)])]


def test_point_events_sit_at_their_times():
    tl = Timeline(_events(), t_min=0, t_max=10, width=100, lane_h=10,
                  lane_label_width="auto", label_size="tiny",
                  axis_size="tiny", tick_every=1, tick_labels="ends")
    canvas, box = render(tl, TH)
    circles = canvas.of("circle")
    assert len(circles) == 5
    xs = sorted(a[0] for a, _ in circles)
    step = xs[1] - xs[0]
    assert step == pytest.approx(20.0)
    assert len(canvas.of("rect")) == 1           # the square, drawn once
    texts = canvas.texts()
    assert "×2" in texts
    assert {"0", "10"} <= set(texts) and "5" not in texts
    assert_inside(tl, TH, canvas, box)


def test_label_size_sets_the_gutter():
    big = Timeline(_events(), lane_label_width="auto")
    small = Timeline(_events(), lane_label_width="auto", label_size="tiny")
    assert small._lane_label_width(TH) < big._lane_label_width(TH)
    assert small.measure(TH).h == big.measure(TH).h
    assert (Timeline(_events(), axis_size="tiny").measure(TH).h
            < big.measure(TH).h)


def test_tick_labels_are_validated():
    with pytest.raises(ValueError):
        Timeline(_events(), tick_labels="some")


def test_different_events_at_one_time_are_not_merged():
    tl = Timeline([("calls", [(0.5, None, "start", "#1f4e79"),
                              (0.5, None, "program", "#3b82f6")])],
                  t_max=10, width=100)
    canvas, _ = render(tl, TH)
    assert len(canvas.of("circle")) == 2
    assert not any(k.startswith("\u00d7") for k in canvas.texts())


def test_lane_grows_to_hold_its_largest_marker():
    tl = Timeline([("a", [(0.5, None, "e", Marker("circle", size=4.0))])],
                  t_max=2, width=40, lane_h=4)
    assert tl._lane_height(TH) == pytest.approx(9.0)
    canvas, box = render(tl, TH)
    assert_inside(tl, TH, canvas, box)
    plain = Timeline([("a", [(0, 1, "x")])], t_max=2, width=40, lane_h=4)
    assert plain._lane_height(TH) == 4.0
