"""Connector-label placement priorities.

1. Span discipline: an offset caption stays within its arm's along-axis
   span whenever the arm can hold it; overhanging an endpoint or elbow
   survives only as a last-resort demotion, never a hard drop.
2. Satisficing clearance: breathing room beyond one gap unit buys
   nothing -- among collision-free in-span candidates the one nearest
   the arm midpoint wins, so captions hug their wires instead of
   drifting into regional voids.
3. Convex-side preference: a bent route's caption sits on the outside
   of the bend, away from the route's own perpendicular legs; straight
   routes keep the caller's preference.
"""
from __future__ import annotations

from sciviz.auto.labelplacer import overlap_area, place_label
from sciviz.auto.labels import LabelBox, place_polyline_label


# ---------------------------------------------------------------------------
# 1. span discipline
# ---------------------------------------------------------------------------

def test_offset_label_keeps_to_its_arm_span():
    # A long free arm with a card near its left half: a max-clearance
    # scorer chases the void on the far right and hangs the caption
    # past the arm's end (over the elbow); span discipline keeps every
    # collision-free caption on its own arm.
    segment = ((0.0, 0.0), (200.0, 0.0))
    card_below_left = (0.0, 8.0, 80.0, 40.0)
    rect, _anchor = place_label(segment, 60.0, 10.0,
                                obstacles=[card_below_left],
                                prefer="above", gap=6.0)
    assert rect[0] >= -0.5 and rect[2] <= 200.5, rect


def test_short_arm_label_overhangs_centred_not_dropped():
    # An arm shorter than its caption: every candidate exits the span,
    # so all carry the same demotion and the remaining keys decide --
    # the caption centres on the short arm instead of failing or
    # sliding arbitrarily.
    segment = ((0.0, 0.0), (40.0, 0.0))
    rect, _anchor = place_label(segment, 100.0, 10.0, obstacles=[],
                                prefer="above", gap=6.0)
    cx = (rect[0] + rect[2]) / 2.0
    assert abs(cx - 20.0) < 1e-6, rect
    assert (rect[2] - rect[0]) == 100.0


def test_overhang_is_last_resort_when_arm_is_walled():
    # Cards wall the arm's middle above and below; the only
    # collision-free slots hang past the arm's ends. The demotion must
    # not become a drop: the placer accepts the overhang rather than
    # covering ink.
    segment = ((0.0, 0.0), (120.0, 0.0))
    wall_above = (25.0, -40.0, 95.0, -2.0)
    wall_below = (25.0, 2.0, 95.0, 40.0)
    rect, _anchor = place_label(segment, 60.0, 10.0,
                                obstacles=[wall_above, wall_below],
                                prefer="above", gap=6.0)
    assert overlap_area(rect, wall_above) == 0.0
    assert overlap_area(rect, wall_below) == 0.0
    assert rect[0] < -0.5 or rect[2] > 120.5, rect


# ---------------------------------------------------------------------------
# 2. satisficing clearance, centrality decides
# ---------------------------------------------------------------------------

def test_clearance_beyond_the_floor_buys_nothing():
    # The midpoint slot clears the floor comfortably; the far-right
    # slot clears it by 5x. Surplus clearance must not pull the caption
    # off the midpoint.
    segment = ((0.0, 0.0), (200.0, 0.0))
    card_below_left = (0.0, 8.0, 80.0, 40.0)
    rect, _anchor = place_label(segment, 60.0, 10.0,
                                obstacles=[card_below_left],
                                prefer="above", gap=6.0)
    cx = (rect[0] + rect[2]) / 2.0
    assert abs(cx - 100.0) < 1e-6, rect
    assert rect[3] < 0.0, rect  # on the preferred (above) side


def test_clearance_floor_outranks_pure_centrality():
    # A chip hugs the arm just above its midpoint: the midpoint slot
    # exists but has sub-floor breathing room, so the placer steps
    # aside to the nearest slot that clears the floor instead of
    # squeezing the caption against the chip.
    segment = ((0.0, 0.0), (200.0, 0.0))
    chip = (85.0, -20.0, 115.0, -17.0)
    rect, _anchor = place_label(segment, 40.0, 10.0,
                                obstacles=[chip],
                                prefer="above", gap=6.0)
    cx = (rect[0] + rect[2]) / 2.0
    assert min(abs(cx - 40.0), abs(cx - 160.0)) < 1e-6, rect


# ---------------------------------------------------------------------------
# 3. convex-side preference on bent routes
# ---------------------------------------------------------------------------

def test_dogleg_caption_prefers_the_convex_side():
    # An n-shaped route: both verticals descend from the top arm, so
    # the route's own legs mark the concave (inner) side. The caption
    # must sit above the arm even when the caller prefers "below".
    pts = [(0.0, 50.0), (0.0, 0.0), (160.0, 0.0), (160.0, 50.0)]
    label = LabelBox(text="earned parents", width=50.0, height=10.0,
                     size_px=10.0)
    placed = place_polyline_label(pts, label, obstacles=[],
                                  prefer="below", gap=6.0)
    assert placed.rotation == 0.0
    assert placed.rect[3] < 0.0, placed.rect  # above the top arm


def test_vertical_arm_caption_sits_outside_the_bend():
    # A [-shaped route: both horizontals extend left of the vertical
    # arm, so the rotated caption belongs on the right -- the outside
    # of the bend -- even when the caller prefers "left".
    pts = [(-40.0, 0.0), (0.0, 0.0), (0.0, 120.0), (-40.0, 120.0)]
    label = LabelBox(text="outcome evidence", width=80.0, height=10.0,
                     size_px=10.0)
    placed = place_polyline_label(pts, label, obstacles=[],
                                  prefer="left", gap=6.0)
    assert placed.rotation == 90.0
    assert placed.rect[0] > 0.0, placed.rect  # right of the arm


def test_straight_route_keeps_caller_preference():
    # No bend, no geometric signal: the caller's preference stands.
    pts = [(0.0, 0.0), (0.0, 100.0)]
    label = LabelBox(text="caption", width=30.0, height=10.0,
                     size_px=10.0)
    placed = place_polyline_label(pts, label, obstacles=[],
                                  prefer="right", gap=6.0)
    assert placed.rect[0] > 0.0, placed.rect


# ---------------------------------------------------------------------------
# 4. multi-line captions never prefer rotation
# ---------------------------------------------------------------------------

def test_multiline_caption_never_prefers_rotation():
    # The leg is long enough that a single-line caption of this width
    # would rotate to read along the wire; a two-line block must stay
    # horizontal -- a rotated block renders as parallel columns of
    # tilted text. Rotation remains available only as a collision
    # fallback.
    pts = [(0.0, 0.0), (0.0, 100.0)]
    label = LabelBox(text="objectives,\ncost, receipt", width=48.0,
                     height=22.0, size_px=10.0)
    placed = place_polyline_label(pts, label, obstacles=[],
                                  prefer="right", gap=6.0)
    assert placed.rotation == 0.0, placed
