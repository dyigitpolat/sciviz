"""Labels are part of the route contract.

1. A labeled connection between two facing pinned sides reserves a
   corridor sized from the *measured* caption, so the caption always has
   a home along the wire (pre-layout margin reservation).
2. The planner treats a candidate route whose arms cannot carry the
   caption as invalid while alternatives exist (label-capacity aware
   routing).
3. A placed connector label never covers other visual elements: nodes,
   free text, other wires. Zero overlap is asserted through the debug
   recorder on every placement -- a label drawn on top of another
   element is erroneous behaviour, not a cosmetic tradeoff.
"""
from __future__ import annotations

from sciviz import Anchor, Box, Canvas, Column, Row, Spacer, Text, Theme
from sciviz.auto.debug import DebugRecorder, record_into
from sciviz.composition import Flow, Flowed
from sciviz.routing import Box as RBox, Endpoint, plan_path


def _render_recorded(body, flows) -> DebugRecorder:
    theme = Theme()
    d = Flowed(body, flows=flows)
    rec = DebugRecorder()
    with record_into(rec):
        size = d.measure(theme)
        canvas = Canvas()
        d.render(canvas, 0.0, 0.0, theme)
    return rec


# ---------------------------------------------------------------------------
# 1. corridor reservation grows with the measured caption
# ---------------------------------------------------------------------------

def test_direct_corridor_reserves_caption_space():
    theme = Theme()
    caption = "a rather long caption that needs room"

    def build(label):
        return Flowed(
            Row(Anchor("a", Box("A", width=60, height=26)),
                Anchor("b", Box("B", width=60, height=26)),
                gap="sm", align="center"),
            flows=[Flow("a", "b", src_side="right", dst_side="left",
                        label=label)],
        )

    unlabeled_w = build(None).measure(theme).w
    labeled_w = build(caption).measure(theme).w
    lbl_w = theme.text_width(
        caption, getattr(theme, "connector_label_size", "small"))
    # The labeled layout must be wide enough that the corridor between
    # the two cards can carry the caption.
    assert labeled_w >= unlabeled_w + lbl_w * 0.8, (
        f"labeled={labeled_w}, unlabeled={unlabeled_w}, caption={lbl_w}")


def test_multiline_caption_reserves_less_corridor():
    theme = Theme()

    def build(label):
        return Flowed(
            Row(Anchor("a", Box("A", width=60, height=26)),
                Anchor("b", Box("B", width=60, height=26)),
                gap="sm", align="center"),
            flows=[Flow("a", "b", src_side="right", dst_side="left",
                        label=label)],
        )

    one_line = build("earned parents, stage advance").measure(theme).w
    two_line = build("earned parents,\nstage advance").measure(theme).w
    assert two_line < one_line, (
        f"two-line caption should need less corridor: {two_line} vs "
        f"{one_line}")


# ---------------------------------------------------------------------------
# 2. planner: armless labeled candidates are invalid
# ---------------------------------------------------------------------------

def test_planner_detours_to_give_the_label_an_arm():
    # Two stacked nodes with a short direct corridor, walled left and
    # right so no caption fits near the direct route; open space to the
    # far right offers a long vertical arm. With a label the planner
    # must abandon the direct vertical and give the caption an arm.
    src = RBox(x=100, y=120, w=60, h=30, name="src")
    dst = RBox(x=100, y=0, w=60, h=30, name="dst")
    wall_l = RBox(x=60, y=30, w=38, h=90, name="wl")
    wall_r = RBox(x=162, y=30, w=38, h=90, name="wr")
    label_extent = (80.0, 10.0)

    plan = plan_path(
        Endpoint(src, "top"), Endpoint(dst, "bottom"),
        anchors=[src, dst, wall_l, wall_r],
        label_extent=label_extent, label_gap=6.0,
    )
    legs = []
    for i in range(len(plan.waypoints) - 1):
        (x1, y1), (x2, y2) = plan.waypoints[i], plan.waypoints[i + 1]
        legs.append(abs(x2 - x1) + abs(y2 - y1))
    assert max(legs) >= 80.0, (
        f"no arm long enough for the caption: waypoints={plan.waypoints}")


# ---------------------------------------------------------------------------
# 3. invariant: placed labels never cover other elements
# ---------------------------------------------------------------------------

def test_placed_labels_have_zero_overlap_in_dense_scene():
    body = Column(
        Row(Anchor("a", Box("alpha", width=70, height=28)),
            Anchor("b", Box("beta", width=70, height=28)),
            gap="lg", align="center"),
        Row(Text("a free-standing annotation between the rows",
                 size="tiny", color="muted"),
            gap="sm", align="center"),
        Row(Anchor("c", Box("gamma", width=70, height=28)),
            Anchor("d", Box("delta", width=70, height=28)),
            gap="lg", align="center"),
        gap="lg", align="center",
    )
    rec = _render_recorded(body, [
        Flow("a", "b", src_side="right", dst_side="left", label="ab edge"),
        Flow("c", "d", src_side="right", dst_side="left", label="cd edge"),
        Flow("a", "c", src_side="left", dst_side="left",
             label="feedback path"),
        Flow("b", "d", src_side="right", dst_side="right",
             label="forward path"),
    ])
    labels = rec.label_placements
    assert labels, "expected label placements to be recorded"
    for record in labels:
        assert record.chosen.overlap <= 0.0, (
            f"label {record.owner!r} placed with overlap "
            f"{record.chosen.overlap} at {record.chosen.rect}")


# ---------------------------------------------------------------------------
# 4. dog-leg side lanes hold the whole caption beside the wire
# ---------------------------------------------------------------------------

def test_dogleg_lane_reserves_full_caption_cross_extent():
    """A non-facing side pair (right toward right) reserves a lane that
    holds the wire plus the caption's full cross extent plus clearance,
    so the caption has an in-span home beside the long arm even when a
    third-party card neighbours the corridor."""
    from sciviz.auto.labels import measure_label
    from sciviz.composition._flow import label_corridor_reservation

    theme = Theme()
    flow = Flow("a", "b", src_side="right", dst_side="right",
                label="outcome evidence")
    lbl = measure_label(
        "outcome evidence", theme,
        getattr(theme, "connector_label_size", "small"))
    cross = min(lbl.width, lbl.height)
    base = 9.0
    reserved = label_corridor_reservation(flow, theme, "right", "right",
                                          base)
    assert reserved >= base / 2.0 + cross + 2.0 * theme.unit - 0.01, (
        f"lane {reserved} cannot hold wire + caption cross {cross}")
