"""Weight/style fidelity of text export and measurement.

Three related guarantees:

1. **Outlined PDF output keeps bold (and italic).** ``outline_svg_text``
   selects a real bold / italic font file per text run instead of
   flattening every run onto the regular face (which silently dropped
   ``weight="700"`` from every outlined PDF).
2. **Text measurement is weight-aware and matches the renderers.**
   ``Theme.text_width`` measures actual glyph advance widths with the
   same font files the exporters embed/outline, so bold labels centre
   symmetrically instead of overflowing their measured box.
3. **The legibility floor flags authored sizes.** A figure that fits
   ``target_width_pt`` no longer ships sub-floor text silently.
"""
from __future__ import annotations

import re
import warnings

import pytest

from sciviz import Card, Column, Diagram, Text, Theme, card_header
from sciviz.core import FontRegistry, outline_svg_text
from sciviz.core._fonts import measure_text_width


THEME = Theme()


def _registry() -> FontRegistry:
    return FontRegistry.default(THEME.font_family)


def _has_bold_face(reg: FontRegistry) -> bool:
    return any(f.bold for f in reg.fonts)


def _path_ink_width(d: str) -> float:
    """Ink width of an outlined text path (absolute M/L/Q/C commands)."""
    xs = [float(a) for a, _b in re.findall(
        r"([-+]?[0-9]*\.?[0-9]+),([-+]?[0-9]*\.?[0-9]+)", d)]
    assert xs, f"no coordinates in path: {d[:80]}"
    return max(xs) - min(xs)


# ---------------------------------------------------------------------------
# 1. Face resolution + outlining
# ---------------------------------------------------------------------------

def test_registry_resolves_a_distinct_bold_face():
    reg = _registry()
    assert _has_bold_face(reg), (
        "FontRegistry.default must register a bold face when the resolved "
        "family ships one (DejaVu Sans is always available via matplotlib)")
    regular = reg.face_for("normal")
    bold = reg.face_for("700")
    assert bold.ttf_path != regular.ttf_path
    assert bold.bold and not regular.bold


def test_face_for_weight_and_style_selection():
    reg = _registry()
    assert reg.face_for("normal") is reg.primary
    # Numeric and keyword bold weights map to the bold face.
    for weight in ("bold", "600", "700", 700):
        assert reg.face_for(weight).bold
    # Sub-600 weights stay regular.
    for weight in ("normal", "400", "500", None):
        assert not reg.face_for(weight).bold
    # Unknown weight strings degrade to regular rather than raising.
    assert not reg.face_for("wiggly").bold


def test_face_for_prefers_weight_match_over_style_match():
    """Dropping bold is worse than dropping the slant: with no
    bold-italic face registered, bold+italic resolves to plain bold."""
    from sciviz.core._fonts import FontAsset
    reg = _registry()
    subset = FontRegistry([f for f in reg.fonts
                           if not (f.bold and f.italic)])
    if not any(f.bold for f in subset.fonts):
        pytest.skip("no bold face available")
    face = subset.face_for("700", "italic")
    assert face.bold and not face.italic
    assert isinstance(face, FontAsset)


def test_css_declares_disjoint_weight_ranges_per_face():
    reg = _registry()
    if not _has_bold_face(reg):
        pytest.skip("no bold face available")
    css = reg.css()
    assert "font-weight: 100 500;" in css
    assert "font-weight: 600 900;" in css
    if any(f.italic for f in reg.fonts):
        assert "font-style: italic;" in css


def test_outline_svg_text_uses_bold_face_for_bold_text():
    reg = _registry()
    if not _has_bold_face(reg):
        pytest.skip("no bold face available")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 60">'
           '<text x="10" y="20" font-size="10">DFSynthesizer</text>'
           '<text x="10" y="40" font-size="10" font-weight="700">'
           'DFSynthesizer</text></svg>')
    out = outline_svg_text(svg, reg)
    paths = re.findall(r'<path d="([^"]+)"', out)
    assert len(paths) == 2
    w_regular = _path_ink_width(paths[0])
    w_bold = _path_ink_width(paths[1])
    assert w_bold > w_regular * 1.05, (
        f"outlined bold text must be materially wider than regular "
        f"(regular={w_regular:.1f}, bold={w_bold:.1f}); identical widths "
        f"mean the bold weight was flattened onto the regular face")


def test_outline_svg_text_uses_bold_face_inside_tspan_runs():
    reg = _registry()
    if not _has_bold_face(reg):
        pytest.skip("no bold face available")
    base = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 60">'
            '<text x="10" y="20" font-size="10">{run}</text></svg>')
    out_regular = outline_svg_text(
        base.format(run='<tspan fill="#111111">weighty</tspan>'), reg)
    out_bold = outline_svg_text(
        base.format(run='<tspan font-weight="700">weighty</tspan>'), reg)
    w_regular = _path_ink_width(
        re.search(r'<path d="([^"]+)"', out_regular).group(1))
    w_bold = _path_ink_width(
        re.search(r'<path d="([^"]+)"', out_bold).group(1))
    assert w_bold > w_regular * 1.05


def test_outline_svg_text_uses_italic_face_for_italic_text():
    reg = _registry()
    if not any(f.italic and not f.bold for f in reg.fonts):
        pytest.skip("no italic face available")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 60">'
           '<text x="10" y="20" font-size="10">calibration</text>'
           '<text x="10" y="40" font-size="10" font-style="italic">'
           'calibration</text></svg>')
    out = outline_svg_text(svg, reg)
    paths = re.findall(r'<path d="([^"]+)"', out)
    assert len(paths) == 2
    assert paths[0] != paths[1], (
        "italic text must outline with the italic face, not the regular")


# ---------------------------------------------------------------------------
# 2. Weight-aware text measurement
# ---------------------------------------------------------------------------

def test_text_width_matches_real_advance_widths():
    """Theme.text_width must track the actual glyph advances of the
    resolved font for both weights (the renderers use those same files)."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextToPath

    reg = _registry()
    ttp = TextToPath()
    for bold in (False, True):
        face = reg.face_for("bold" if bold else "normal")
        for s in ("DFSynthesizer", "SpiNeMap", "trained SNN", "minimise"):
            for size in (8.0, 10.0):
                truth, _h, _d = ttp.get_text_width_height_descent(
                    s, FontProperties(fname=str(face.ttf_path), size=size),
                    False)
                got = THEME.text_width(s, size, bold=bold)
                assert got == pytest.approx(truth, rel=0.02), (
                    f"text_width({s!r}, {size}, bold={bold}) = {got:.2f} "
                    f"but the rendered advance is {truth:.2f}")


def test_text_width_bold_is_wider_than_regular():
    if not _has_bold_face(_registry()):
        pytest.skip("no bold face available")
    for s in ("DFSynthesizer", "Hello world"):
        regular = THEME.text_width(s, "tiny")
        bold = THEME.text_width(s, "tiny", bold=True)
        assert bold > regular * 1.03


def test_measure_text_width_handles_empty_and_multiline():
    assert measure_text_width("", 10.0, THEME.font_family) == 0.0
    single = measure_text_width("wide line", 10.0, THEME.font_family)
    multi = measure_text_width("wide line\nx", 10.0, THEME.font_family)
    assert multi == pytest.approx(single)


def test_card_centers_long_bold_value_symmetrically():
    """End-to-end: a long bold value inside a Card must sit centred
    between the card borders (the fig_mapping_pipeline defect)."""
    card = Card(
        card_header("Schedule"),
        Column(
            Text("tool", size="tiny", color="muted", weight="700"),
            Text("DFSynthesizer", size="tiny", color="text", weight="700"),
            gap="none", align="center",
        ),
        role="blue",
    )
    d = Diagram.for_paper(card)
    svg = d.render(embed_fonts=False)
    outlined = outline_svg_text(svg, _registry())
    # The card body rect is the widest x-positioned rect (ET re-serialises
    # tags with a namespace prefix, so match on attributes only).
    rects = [(float(m.group(1)), float(m.group(2)))
             for m in re.finditer(r'rect x="([-0-9.]+)" [^>]*?'
                                  r'width="([-0-9.]+)"', outlined)]
    assert rects, "outlined SVG must keep the card rects"
    card_x, card_w = max(rects, key=lambda r: r[1])
    # The longest outlined glyph run is the DFSynthesizer line; its ink
    # spans [tx + min(xs), tx + max(xs)] in canvas coordinates.
    best = None
    for m in re.finditer(r'<path d="([^"]+)"[^>]*transform='
                         r'"translate\(([-0-9.]+),', outlined):
        xs = [float(a) for a, _b in re.findall(
            r"([-+]?[0-9]*\.?[0-9]+),([-+]?[0-9]*\.?[0-9]+)", m.group(1))]
        if not xs:
            continue
        tx = float(m.group(2))
        span = (tx + min(xs), tx + max(xs))
        if best is None or span[1] - span[0] > best[1] - best[0]:
            best = span
    ink_l, ink_r = best
    left = ink_l - card_x
    right = (card_x + card_w) - ink_r
    assert abs(left - right) <= 1.5, (
        f"bold value must centre symmetrically inside the card: "
        f"left margin {left:.2f}px vs right margin {right:.2f}px")


# ---------------------------------------------------------------------------
# 3. Legibility floor for authored sizes
# ---------------------------------------------------------------------------

def test_authored_size_below_floor_warns_even_when_figure_fits():
    d = Diagram.for_paper(Text("tiny print", size=4.5),
                          target_width_pt=200.0)
    with pytest.warns(UserWarning, match="legibility floor"):
        d.render()


def test_authored_sizes_at_or_above_floor_do_not_warn():
    d = Diagram.for_paper(Text("micro print", size="micro"),
                          target_width_pt=200.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d.render()


def test_theme_micro_token_clears_default_floor():
    """`micro` follows the label/small/tiny 1pt ladder and sits above the
    default legibility floor -- it must never be the illegible outlier."""
    theme = Theme()
    assert theme.font_micro == pytest.approx(theme.font_tiny - 1.0)
    assert theme.font_micro >= 6.0  # Diagram's default min_effective_font_pt
