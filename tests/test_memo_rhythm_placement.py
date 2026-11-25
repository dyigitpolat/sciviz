"""Measure-memo soundness, Rhythm membership and Row placement.

* The memo's write epoch moves only for writes that can change a stored
  result: a container built and measured inside a measure (a composite's
  fresh Row) and a floor an ``inflate_to`` already meets do not
  invalidate it, and a new element never inherits a measured element's
  recycled ``id``.
* A Rhythm keeps one member per run of children, and a deep copy of a
  tree is spaced by its own containers.
* ``Row.render`` draws every child where ``Row._child_offsets`` (and so
  ``content_bbox``, ``first_baseline`` and ``flow_lanes``) says it is,
  for every alignment, including when the slack clamp binds.
"""
from __future__ import annotations

import copy

import pytest

from sciviz import DEFAULT_THEME, BBox, Box, Column, Group, Rhythm, Row
from sciviz.core import Canvas, Element
from sciviz.core import _measure_memo as MM
from sciviz.core._measure_memo import measure_memo

THEME = DEFAULT_THEME


# ---------------------------------------------------------------- memo


def test_fresh_container_measured_inside_a_measure_keeps_the_memo(
        monkeypatch):
    # Group builds a fresh Row around its children on every measure.
    built = []
    original = Group._row

    def counting_row(self):
        built.append(self)
        return original(self)

    monkeypatch.setattr(Group, "_row", counting_row)
    col = Column(Group("one", Box("a"), Box("b")),
                 Group("two", Box("c"), Box("d")), gap="sm")
    with measure_memo():
        first = col.measure(THEME)
        once = len(built)
        for _ in range(4):
            assert col.measure(THEME) == first
            col.content_bbox(THEME)
        # The fresh Row settling its own flags during its first measure
        # is not a layout write: nothing is measured twice.
        assert len(built) == once


def test_new_element_never_inherits_a_measured_elements_id():
    with measure_memo():
        for _ in range(200):
            r = Row(Box("x"), Box("y"), gap="sm")
            r.measure(THEME)
            del r
        epoch = MM._State.epoch
        for _ in range(200):
            Row(Box("u"), Box("v"), gap="sm")
        # Constructor writes of new containers are never layout writes.
        assert MM._State.epoch == epoch


def test_inflate_to_a_floor_already_met_keeps_the_memo():
    box = Box("label")
    with measure_memo():
        box.inflate_to(40.0, 20.0)
        size = box.measure(THEME)
        epoch = MM._State.epoch
        box.inflate_to(0.0, 0.0)
        box.inflate_to(40.0, 20.0)
        box.inflate_to(10.0, 5.0)
        assert MM._State.epoch == epoch
        box.inflate_to(size.w + 20.0, 0.0)
        assert MM._State.epoch != epoch
        assert box.measure(THEME).w == pytest.approx(size.w + 20.0)


# ------------------------------------------------------ Rhythm members


def test_rebuilt_container_replaces_its_predecessor_in_the_rhythm():
    beat = Rhythm("md")
    group = Group("label", Box("a"), Box("b"), gap=beat)
    # Keep every rebuilt row alive: membership must not depend on
    # garbage collection.
    rows = [group._row() for _ in range(6)]
    assert len(beat._members) == 1
    assert rows[-1] in beat._members


def test_distinct_children_are_distinct_members():
    beat = Rhythm("md")
    a, b, c = Box("a"), Box("b"), Box("c")
    keep = [Row(a, b, gap=beat), Row(b, c, gap=beat), Row(a, b, gap=beat)]
    assert len(beat._members) == 2
    assert keep[1] in beat._members and keep[2] in beat._members


def test_deep_copy_is_spaced_by_its_own_containers():
    beat = Rhythm("md")
    top = Row(Box("a"), Box("b"), gap=beat)
    bottom = Row(Box("c"), Box("d"), gap=beat)
    tree = Column(top, bottom, gap="md")
    dup = copy.deepcopy(tree)
    dup_beat = dup.children[0].gap
    assert dup_beat is not beat
    assert dup.children[1].gap is dup_beat
    assert set(map(id, dup_beat._members)) == set(map(id, dup.children))
    assert set(map(id, beat._members)) == {id(top), id(bottom)}


# ------------------------------------------------------ Row placement


class _Probe(Element):
    """Fixed box with a declared content box; records where it is drawn."""

    def __init__(self, w, h, cb, lanes=None):
        self.w, self.h, self.cb, self.lanes = w, h, cb, lanes
        self.drawn = []

    def measure(self, theme):
        return BBox(self.w, self.h)

    def content_bbox(self, theme):
        return self.cb

    def render(self, canvas, x, y, theme):
        self.drawn.append((x, y))


class _LanedProbe(_Probe):
    def flow_lanes(self, theme):
        return self.lanes


def _probes():
    # A tall child with its content at the top, and a short one whose
    # content sits low but surfaces a top lane: measure sizes the row
    # from the lane-reserve box, so a start alignment on the raw content
    # tops must be clamped into the slack.
    return [_Probe(10.0, 30.0, (0.0, 0.0, 10.0, 30.0)),
            _LanedProbe(10.0, 12.0, (0.0, 10.0, 10.0, 2.0),
                        lanes=(5.0, 0.0)),
            _Probe(10.0, 8.0, (0.0, 3.0, 10.0, 4.0))]


@pytest.mark.parametrize("align", ["start", "stretch", "center", "end"])
def test_row_draws_children_where_its_layout_queries_place_them(align):
    kids = _probes()
    row = Row(*kids, gap=4.0, align=align, equal_heights=False)
    offs = row._child_offsets(THEME)
    row.render(Canvas(), 100.0, 50.0, THEME)
    for (ox, oy, _s), kid in zip(offs, kids):
        assert kid.drawn[-1] == pytest.approx((100.0 + ox, 50.0 + oy))
    # content_bbox is the union of the content boxes as drawn.
    tops = [kid.drawn[-1][1] - 50.0 + kid.cb[1] for kid in kids]
    assert row.content_bbox(THEME)[1] == pytest.approx(min(tops))


def test_start_alignment_is_clamped_into_the_rows_slack():
    kids = _probes()
    row = Row(*kids, gap=4.0, align="start", equal_heights=False)
    H = row.measure(THEME).h
    for _ox, oy, size in row._child_offsets(THEME):
        assert 0.0 <= oy <= H - size.h + 1e-9


# ------------------------------------- placement adds no measure pass
#
# ``Row.render`` and the layout queries place through one function
# (``Row._place``), but each keeps its own historic measuring order: a
# query sizes the children before the row measures itself. A child
# whose measure is not idempotent (a stretched shared-column stack
# re-inflates its members on every pass, see the xfail below) would
# otherwise grow once more per query, and a figure's geometry would
# depend on how many queries ran (gallery fig02 widened by 21.6 pt).


class _Recorder(_Probe):
    def __init__(self, log):
        super().__init__(10.0, 10.0, (0.0, 0.0, 10.0, 10.0))
        self.log = log

    def measure(self, theme):
        self.log.append("child")
        return super().measure(theme)


def test_placement_query_sizes_children_before_measuring_the_row():
    log = []
    row = Row(_Recorder(log), _Recorder(log), gap=4.0)
    measure = Row.measure

    def logged_measure(theme):
        log.append("row")
        return measure(row, theme)

    row.measure = logged_measure
    row._child_offsets(THEME)
    assert log.index("child") < log.index("row")
    assert log.count("row") == 1


def test_query_and_render_place_through_one_function_at_any_origin():
    kids = _probes()
    row = Row(*kids, gap=4.0, align="center", equal_heights=False)
    local = row._child_offsets(THEME)
    row.render(Canvas(), 37.25, 11.5, THEME)
    for (ox, oy, _s), kid in zip(local, kids):
        assert kid.drawn[-1] == pytest.approx((37.25 + ox, 11.5 + oy))


@pytest.mark.xfail(strict=True, reason=(
    "Box.inflate_to forwards min_w - 12 to an element label, but the "
    "Box's real horizontal padding differs, so every AlignedStack("
    "stretch=True) pass re-inflates the panel a little wider. Fixing it "
    "shrinks figures whose geometry carries the accumulated growth "
    "(gallery fig02), so it waits for an owner decision."))
def test_stretched_shared_columns_measure_idempotently():
    from sciviz import AlignedStack, Text

    def panel(*labels):
        return Box(Column(*[Text(t) for t in labels], gap="xs",
                          align="start"))

    stack = AlignedStack(
        Row(Box(Text("Captioner")),
            panel("Frame 1 caption", "Frame 2 caption"), gap="lg"),
        Row(Box(Text("Other")), panel("Title"), gap="lg"),
        gap="md", align="start", stretch=True)
    widths = [stack.measure(THEME).w for _ in range(3)]
    assert widths[2] == pytest.approx(widths[1])
