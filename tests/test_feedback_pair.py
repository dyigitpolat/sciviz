from __future__ import annotations

from sciviz import Box, Canvas, FeedbackPair, Theme


def test_feedback_pair_exposes_named_anchors_and_bottom_alignment_landmark():
    theme = Theme()
    pair = FeedbackPair(
        "agent",
        Box("WM", width=100, height=50),
        Box("VLA", width=100, height=50),
    )
    assert pair.top_anchor == "agent_top"
    assert pair.bottom_anchor == "agent_bottom"
    content = pair.content_bbox(theme)
    assert content[2:] == (100, 50)
    assert content[1] > pair.measure(theme).h / 2


def test_feedback_pair_renders_channels_rollout_label_and_loop_marker():
    theme = Theme()
    pair = FeedbackPair("agent", Box("WM"), Box("VLA"))
    size = pair.measure(theme)
    canvas = Canvas()
    pair.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    assert "WM" in svg and "VLA" in svg
    assert ">O<" in svg and ">A<" in svg
    assert "𝒯" in svg
    assert "<path" in svg  # vector loop icon


def test_feedback_pair_can_express_one_way_unbounded_coupling():
    theme = Theme()
    pair = FeedbackPair(
        "reward", Box("WM"), Box("RL"),
        forward_label="Reward Modeling",
        return_label=None,
        loop_label=None,
        boundary=False,
    )
    canvas = Canvas()
    size = pair.measure(theme)
    pair.render(canvas, 0.0, 0.0, theme)
    svg = canvas.to_svg(size.w, size.h)
    assert ">Reward<" in svg and ">Modeling<" in svg
    assert "stroke-dasharray" not in svg


def test_long_vertical_channel_label_grows_sideways_not_between_nodes():
    theme = Theme()
    short = FeedbackPair(
        "short", Box("WM"), Box("RL"),
        forward_label="R", return_label=None,
        loop_label=None, boundary=False,
    )
    long = FeedbackPair(
        "long", Box("WM"), Box("RL"),
        forward_label="Reward Modeling", return_label=None,
        loop_label=None, boundary=False,
    )

    assert long.measure(theme).h == short.measure(theme).h
    assert long.measure(theme).w > short.measure(theme).w


def test_feedback_pairs_keep_peer_center_pitch_across_component_sizes():
    theme = Theme()
    large = FeedbackPair(
        "large", Box("A", width=100, height=50),
        Box("B", width=100, height=50), boundary=False,
    )
    small = FeedbackPair(
        "small", Box("A", width=60, height=30),
        Box("B", width=60, height=30), boundary=False,
    )

    def center_pitch(pair):
        top, band, bottom = [c.measure(theme) for c in pair.core.children]
        return top.h / 2.0 + band.h + bottom.h / 2.0

    assert center_pitch(large) == center_pitch(small)
    assert center_pitch(large) == theme.unit * FeedbackPair._CENTER_PITCH_UNITS
