"""The invisible text layer that keeps an outlined PDF selectable.

Outlining is what makes every glyph render on a PDF backend with no font
fallback -- but it throws the *text* away.  An outlined figure cannot be
selected, searched, copied, or read aloud by a screen reader, and a reader who
tries to quote a label out of a figure gets nothing.

``text_mode="hybrid"`` fixes that without touching a printed pixel: the
outlined paths remain the only thing that paints, and an all-but-transparent
copy of the original ``<text>`` is laid over them to carry the characters.

The two guarantees this file locks down are therefore:

1. **The shadow is invisible** -- and stays invisible for text whose authored
   attributes are hostile (a stroke, an opacity, an unparseable fill).
2. **The visible layer is untouched** -- byte for byte the same geometry that
   ``text_mode="outline"`` produces, so turning selectability on can never be
   a visual regression.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

import pytest

from sciviz import Diagram, Text, Theme
from sciviz.core import FontRegistry, outline_svg_text
from sciviz.core._fonts import (
    _SHADOW_FILL,
    _SHADOW_FILL_OPACITY,
    _selectable_shadow,
)

THEME = Theme()


def _registry() -> FontRegistry:
    return FontRegistry.default(THEME.font_family)


def _svg_of(diagram) -> str:
    return diagram.render(embed_fonts=False)


def _outlined(svg: str, *, selectable: bool) -> str:
    return outline_svg_text(svg, _registry(), THEME.font_family,
                            selectable=selectable)


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1] if "}" in el.tag else el.tag


def _is_shadow(el: ET.Element) -> bool:
    return el.attrib.get("fill-opacity") == _SHADOW_FILL_OPACITY


def _shadows(svg: str) -> list:
    return [el for el in ET.fromstring(svg).iter() if _is_shadow(el)]


def _skeleton(svg: str) -> list:
    """Every non-shadow element as ``(tag, sorted attributes)``.

    This is the layer that reaches paper; comparing it across modes is the
    test that "selectable" cannot become "different".
    """
    return [(_tag(el), sorted(el.attrib.items()))
            for el in ET.fromstring(svg).iter() if not _is_shadow(el)]


def _sample():
    return Diagram.for_paper(Text("Selectable lane label"))


# ---------------------------------------------------------------------------
# 1. The shadow carries the text
# ---------------------------------------------------------------------------

def test_hybrid_outlines_the_ink_and_keeps_the_characters():
    svg = _outlined(_svg_of(_sample()), selectable=True)
    assert "<path" in svg, "hybrid must still outline the visible glyphs"
    assert "Selectable lane label" in svg, (
        "hybrid must keep the characters somewhere in the file, or the PDF "
        "has nothing to select")


def test_outline_mode_adds_no_shadow():
    """``outline`` keeps its old meaning exactly: paths, and nothing else."""
    svg = _outlined(_svg_of(_sample()), selectable=False)
    assert _shadows(svg) == []
    assert "Selectable lane label" not in svg


def test_shadow_text_matches_the_visible_text():
    shadows = _shadows(_outlined(_svg_of(_sample()), selectable=True))
    assert shadows, "expected one shadow per replaced text node"
    assert "".join(shadows[0].itertext()) == "Selectable lane label"


# ---------------------------------------------------------------------------
# 2. The shadow is invisible -- by construction, not by luck
# ---------------------------------------------------------------------------

def test_shadow_alpha_clears_cairos_floor_without_becoming_visible():
    """Cairo composites in 8-bit alpha and DROPS anything that rounds to 0.

    A shadow at ``fill-opacity="0"`` is elided from the PDF entirely -- no
    glyphs, no font, nothing to select -- so 1/255 is a hard floor, not a
    preference.  The ceiling is what keeps it invisible on the page.
    """
    alpha = float(_SHADOW_FILL_OPACITY)
    assert alpha >= 1.0 / 255.0, (
        "below 1/255 the converter optimises the whole layer away")
    assert alpha <= 2.0 / 255.0, (
        "the shadow may cost at most one grey level out of 255")


def test_shadow_drops_the_synthetic_semibold_stroke():
    """The stroke is painted at FULL opacity, so it must not survive.

    ``Canvas.apply_text_stroke`` paints a hairline of the glyph's own colour
    under it to synthesise a semibold weight.  ``fill-opacity`` does not touch
    a stroke, so a shadow that kept one would print in plain sight.
    """
    theme = Theme()
    theme.text_stroke_ratio = 0.013
    diagram = Diagram.for_paper(Text("stroked"), theme=theme)
    svg = diagram.render(embed_fonts=False)
    assert "stroke-width" in svg, "fixture must actually carry a text stroke"
    for shadow in _shadows(outline_svg_text(svg, FontRegistry.default(
            theme.font_family), theme.font_family, selectable=True)):
        for el in shadow.iter():
            assert el.attrib.get("stroke") == "none"
            for attr in ("stroke-width", "paint-order", "stroke-linejoin",
                         "stroke-opacity"):
                assert attr not in el.attrib


def test_shadow_drops_opacity_so_faded_text_does_not_vanish():
    """``opacity`` MULTIPLIES ``fill-opacity``.

    A half-faded note would land at 0.002, back under the 1/255 floor, and
    that run alone would silently lose its selectable layer.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">'
           '<text x="1" y="10" font-size="9" fill="#0b1220" opacity="0.5">'
           'faded</text></svg>')
    shadow, = _shadows(_outlined(svg, selectable=True))
    assert "opacity" not in shadow.attrib
    assert shadow.attrib["fill-opacity"] == _SHADOW_FILL_OPACITY


def test_shadow_pins_its_fill_so_an_unresolved_colour_cannot_paint():
    """An unparseable fill makes CairoSVG ABANDON ``fill-opacity``.

    Regression: a thesis figure reached the SVG with ``fill="fg"`` -- a colour
    token that never got resolved.  CairoSVG cannot parse it, silently ignores
    the 0.4% alpha, and stamps the run on the page at full strength.  The
    shadow therefore names its own colour instead of inheriting one; at 1/255
    alpha the choice is immaterial, and being parseable is not.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">'
           '<text x="1" y="10" font-size="9" fill="fg">token</text></svg>')
    shadow, = _shadows(_outlined(svg, selectable=True))
    assert shadow.attrib["fill"] == _SHADOW_FILL
    assert "fg" not in shadow.attrib.values()


def test_shadow_drops_per_run_fills_too():
    """A ``tspan`` inherits ``fill-opacity`` but can override ``fill``."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">'
           '<text x="1" y="10" font-size="9" fill="#0b1220">a'
           '<tspan fill="url(#nope)">b</tspan></text></svg>')
    shadow, = _shadows(_outlined(svg, selectable=True))
    for el in shadow.iter():
        assert el.attrib.get("fill", _SHADOW_FILL) == _SHADOW_FILL


def test_shadow_does_not_intercept_pointer_events():
    shadow, = _shadows(_outlined(
        '<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">'
        '<text x="1" y="10" font-size="9" fill="#0b1220">hi</text></svg>',
        selectable=True))
    assert shadow.attrib["pointer-events"] == "none"


def test_selectable_shadow_does_not_mutate_the_node_it_copies():
    node = ET.fromstring('<text fill="#0b1220" opacity="0.5" '
                         'stroke="#0b1220" stroke-width="0.12">x</text>')
    _selectable_shadow(node)
    assert node.attrib["fill"] == "#0b1220"
    assert node.attrib["opacity"] == "0.5"
    assert node.attrib["stroke-width"] == "0.12"


# ---------------------------------------------------------------------------
# 3. The visible layer is untouched
# ---------------------------------------------------------------------------

def test_hybrid_paints_exactly_what_outline_paints():
    """The whole point: selectability is additive, never a visual change."""
    svg = _svg_of(_sample())
    assert _skeleton(_outlined(svg, selectable=True)) == \
        _skeleton(_outlined(svg, selectable=False))


def test_shadow_follows_the_paths_it_shadows():
    """Ink first, text second: the layer order is explicit, not incidental."""
    root = ET.fromstring(_outlined(_svg_of(_sample()), selectable=True))
    for parent in root.iter():
        kids = list(parent)
        for i, el in enumerate(kids):
            if _is_shadow(el):
                assert i > 0 and _tag(kids[i - 1]) in ("path", "g"), (
                    "a shadow must sit directly after the geometry it covers")


def test_shadow_geometry_tracks_the_original_text_node():
    """Baseline, size and weight are kept so the shadow sits on the ink."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">'
           '<text x="12.5" y="9.25" font-size="9" fill="#0b1220" '
           'text-anchor="middle" font-weight="700">hi</text></svg>')
    shadow, = _shadows(_outlined(svg, selectable=True))
    assert shadow.attrib["y"] == "9.25"
    assert shadow.attrib["font-size"] == "9"
    assert shadow.attrib["font-weight"] == "700"


# ---------------------------------------------------------------------------
# 3b. The shadow is pinned to the ink, not laid out beside it
# ---------------------------------------------------------------------------
# The shadow is laid out by the CONVERTER, from whatever face it resolves for
# the named family; the visible glyphs were laid out by the outliner, from the
# font file it opened itself.  Where the two faces differ the shadow advances
# at its own rate, and the selection a reader drags across a label stops short
# of the word (the reported defect: "the invisible text ... does not align with
# the starting and ending of the actually rendered text").  Explicit
# per-character positions take the renderer's metrics out of the answer.

def _paths(svg: str) -> list:
    return [el for el in ET.fromstring(svg).iter() if _tag(el) == "path"]


def _translate_x(el: ET.Element) -> float:
    import re
    return float(re.findall(r"translate\(([-0-9.]+)", el.attrib["transform"])[0])


def _positions(el: ET.Element) -> list:
    return [float(v) for v in el.attrib["x"].split()]


def _pinned_svg(text, **attrs):
    extra = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="20">'
            f'<text x="80" y="14" font-size="9" fill="#0b1220" {extra}>'
            f'{text}</text></svg>')


@pytest.mark.parametrize("anchor", ["start", "middle", "end"])
def test_shadow_starts_exactly_where_the_ink_starts(anchor):
    """Whatever the anchor, character one sits on glyph one."""
    svg = _outlined(_pinned_svg("Selectable lane label", **{
        "text-anchor": anchor}), selectable=True)
    shadow, = _shadows(svg)
    assert _positions(shadow)[0] == pytest.approx(
        _translate_x(_paths(svg)[0]), abs=1e-3)


def test_shadow_carries_one_position_per_character_in_reading_order():
    svg = _outlined(_pinned_svg("Selectable lane label"), selectable=True)
    shadow, = _shadows(svg)
    xs = _positions(shadow)
    assert len(xs) == len("Selectable lane label")
    assert xs == sorted(xs), "positions must advance with the reading order"


def test_shadow_never_declares_textlength():
    """The spec's own mechanism for this loses to the renderers.

    ``textLength`` with ``lengthAdjust="spacingAndGlyphs"`` says exactly what
    the positions say.  CairoSVG, which writes the PDF, does not implement it.
    resvg does -- per text CHUNK, and an absolutely positioned character IS a
    chunk, so every glyph gets stretched to the width of the whole label; the
    stretched copies pile up and 0.4% alpha accumulates into a visible smear
    (measured at 36/255 on a figure otherwise within 1/255).  Regression guard.
    """
    shadow, = _shadows(_outlined(_pinned_svg("Selectable lane label"),
                                 selectable=True))
    assert "textLength" not in shadow.attrib
    assert "lengthAdjust" not in shadow.attrib


def test_pinned_shadow_is_anchored_at_start():
    """An absolutely positioned character is its own text chunk.

    Left anchored, the renderer places each one at the coordinate given; under
    the authored ``middle`` it would re-centre every character on its own
    coordinate instead, and the label would collapse into a pile.
    """
    shadow, = _shadows(_outlined(
        _pinned_svg("centred", **{"text-anchor": "middle"}), selectable=True))
    assert shadow.attrib["text-anchor"] == "start"


def test_pinned_shadow_preserves_white_space():
    """Collapsing runs of spaces would slip the positions off the characters.

    A converter trims and collapses white space by default, so the character
    stream it lays out stops matching the one the outliner measured, and every
    position after the first collapsed space addresses the wrong character.
    """
    shadow, = _shadows(_outlined(_pinned_svg("two  spaces"), selectable=True))
    assert shadow.attrib["{http://www.w3.org/XML/1998/namespace}space"] == \
        "preserve"
    assert len(_positions(shadow)) == len("two  spaces")


def test_every_run_of_a_structured_label_is_positioned():
    """Text between runs is a *tail*, and a tail cannot carry an attribute.

    sciviz writes an unstyled run as bare text, so a rich label routinely has
    one.  Each is wrapped in a plain ``<tspan>`` (which inherits everything and
    changes nothing) purely so it has somewhere to put its positions.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="20">'
           '<text x="80" y="14" font-size="9" fill="#0b1220">'
           '<tspan font-weight="700">(a)</tspan> Lowering</text></svg>')
    shadow, = _shadows(_outlined(svg, selectable=True))
    assert [_tag(el) for el in shadow] == ["tspan", "tspan"]
    runs = [_positions(el) for el in shadow]
    assert [len(r) for r in runs] == [len("(a)"), len(" Lowering")]
    assert runs[0] + runs[1] == _positions(shadow), (
        "the element list must address the same characters as the run lists")


def test_a_run_the_authored_family_covers_keeps_the_authored_metrics(
        monkeypatch):
    """The whole point of pinning: no drift, so no re-flowed families.

    Unpinned, one family for the whole node protects reading order (see
    ``test_shadow_names_the_one_family_that_covers_the_whole_node``).  Pinned,
    the positions protect it instead, and re-flowing covered text through a
    fallback design would push every character off its own glyph -- enough,
    after a dozen of them, for a text extractor to read word breaks inside
    words.
    """
    _with_coverage(
        monkeypatch,
        {"/p.ttf": set(map(ord, "abcdef ")), "/fa.ttf": {ord("a"), 0x2264}},
        fallbacks=((FALLBACK_A, "/fa.ttf"),),
    )
    from sciviz.core._fonts import _selectable_shadow
    shadow = _selectable_shadow(_text_node("≤ face"), _FakeRegistry("/p.ttf"),
                                "Primary, FallbackA",
                                positions=[float(i) for i in range(6)])
    families = [el.attrib.get("font-family") for el in shadow]
    assert families == [FALLBACK_A, None], (
        "only the run the authored family cannot draw may change family")
    assert "".join(shadow.itertext()) == "≤ face"


def test_pinning_is_skipped_when_the_positions_do_not_match_the_characters():
    """A list out of step with the text would place it worse than not at all."""
    from sciviz.core._fonts import _selectable_shadow
    node = ET.fromstring('<text x="5" y="9" font-size="9">abc</text>')
    shadow = _selectable_shadow(node, positions=[1.0, 2.0])
    assert shadow.attrib["x"] == "5", "the authored position must survive"
    assert "{http://www.w3.org/XML/1998/namespace}space" not in shadow.attrib


# ---------------------------------------------------------------------------
# 4. Every codepoint reaches the text layer, whatever it takes
# ---------------------------------------------------------------------------
# A converter with no glyph-level fallback resolves ONE face per run and draws
# `.notdef` for anything outside it.  A `.notdef` has no character behind it,
# so it reaches the text layer as a HOLE: the page prints a "less than or
# equal" sign that copies as nothing.  The shadow therefore has to name a face
# that can actually draw each codepoint.
#
# The decision logic is unit-tested against synthetic coverage so it holds on
# any machine, whatever fonts happen to be installed.

PRIMARY = Path_ = type(_registry().primary.ttf_path)
FALLBACK_A = "FallbackA"
FALLBACK_B = "FallbackB"


class _FakeFace:
    def __init__(self, path):
        self.ttf_path = path


class _FakeRegistry:
    def __init__(self, path):
        self._face = _FakeFace(path)

    def face_for(self, weight="normal", style="normal"):
        return self._face


def _with_coverage(monkeypatch, coverage, fallbacks=()):
    """Pin glyph coverage per font file, and the fallback stack."""
    from sciviz.core import _fonts

    monkeypatch.setattr(_fonts, "_codepoints",
                        lambda p: frozenset(coverage.get(str(p), ())))
    monkeypatch.setattr(_fonts, "_fallback_families",
                        lambda *a, **k: fallbacks)


def _text_node(text):
    return ET.fromstring(
        f'<text x="5" y="9" font-size="9" fill="#0b1220">{text}</text>')


def _shadow_of(node, path):
    from sciviz.core._fonts import _selectable_shadow
    return _selectable_shadow(node, _FakeRegistry(path), "Primary, FallbackA")


def test_shadow_is_left_alone_when_the_authored_family_covers_everything(
        monkeypatch):
    _with_coverage(monkeypatch, {"/p.ttf": {ord("a"), ord("b")}})
    shadow = _shadow_of(_text_node("ab"), "/p.ttf")
    assert "font-family" not in shadow.attrib
    assert list(shadow) == [], "no run splitting for fully covered text"


def test_shadow_names_the_one_family_that_covers_the_whole_node(monkeypatch):
    """One family, one run, one alignment -- so reading order survives.

    Splitting a centred or right-aligned label into pieces makes the converter
    align each piece SEPARATELY, and the text layer then reads back scrambled
    ("4096 Loihi: output edges <=").  Naming a single family avoids that
    entirely, so it is tried before any splitting.
    """
    _with_coverage(
        monkeypatch,
        {"/p.ttf": {ord("a")}, "/fa.ttf": {ord("a"), 0x2264}},
        fallbacks=((FALLBACK_A, "/fa.ttf"),),
    )
    shadow = _shadow_of(_text_node("a≤"), "/p.ttf")
    assert shadow.attrib["font-family"] == FALLBACK_A
    assert list(shadow) == [], "one covering family must not split the node"
    assert "".join(shadow.itertext()) == "a≤"


def test_shadow_splits_per_run_only_when_no_single_family_covers(monkeypatch):
    _with_coverage(
        monkeypatch,
        {"/p.ttf": {ord("a")}, "/fa.ttf": {0x2264}, "/fb.ttf": {0x2248}},
        fallbacks=((FALLBACK_A, "/fa.ttf"), (FALLBACK_B, "/fb.ttf")),
    )
    shadow = _shadow_of(_text_node("a≤≈"), "/p.ttf")
    assert "font-family" not in shadow.attrib
    families = [el.attrib.get("font-family") for el in shadow]
    assert families == [None, FALLBACK_A, FALLBACK_B]
    assert "".join(shadow.itertext()) == "a≤≈", (
        "splitting must not drop or reorder a single character")


def test_the_grapheme_survives_even_when_no_face_can_draw_it(monkeypatch):
    """The character matters more than the glyph.

    If nothing in the stack can draw it, the shadow still CARRIES it: pasted
    somewhere with a font that has the glyph, it becomes visible again.  A
    missing character is unrecoverable; an unrenderable one is not.
    """
    _with_coverage(monkeypatch, {"/p.ttf": {ord("a")}}, fallbacks=())
    shadow = _shadow_of(_text_node("a≤"), "/p.ttf")
    assert "≤" in "".join(shadow.itertext())


def test_split_runs_keep_their_own_size_and_weight(monkeypatch):
    """Per-run metrics drive the converter's cursor.

    A shadow that advances differently from the ink it covers hands the reader
    a selection that does not track the words.
    """
    _with_coverage(
        monkeypatch,
        {"/p.ttf": {ord("a")}, "/fa.ttf": {0x2264}, "/fb.ttf": {0x2248}},
        fallbacks=((FALLBACK_A, "/fa.ttf"), (FALLBACK_B, "/fb.ttf")),
    )
    node = ET.fromstring(
        '<text x="5" y="9" font-size="9" fill="#0b1220">a'
        '<tspan font-size="6" font-weight="700">≤≈</tspan></text>')
    shadow = _shadow_of(node, "/p.ttf")
    carried = [(el.attrib.get("font-size"), el.attrib.get("font-weight"))
               for el in shadow if el.attrib.get("font-family")]
    assert carried == [("6", "700"), ("6", "700")]


def test_split_tspans_stay_in_the_documents_namespace(monkeypatch):
    """A tspan in the null namespace is not an SVG tspan."""
    _with_coverage(
        monkeypatch,
        {"/p.ttf": {ord("a")}, "/fa.ttf": {0x2264}, "/fb.ttf": {0x2248}},
        fallbacks=((FALLBACK_A, "/fa.ttf"), (FALLBACK_B, "/fb.ttf")),
    )
    ns = "{http://www.w3.org/2000/svg}"
    node = ET.fromstring(
        '<text xmlns="http://www.w3.org/2000/svg" x="5" y="9" '
        'font-size="9" fill="#0b1220">a≤≈</text>')
    shadow = _shadow_of(node, "/p.ttf")
    assert shadow.tag == f"{ns}text"
    assert [el.tag for el in shadow] == [f"{ns}tspan"] * 3


def test_fallback_faces_still_returns_plain_paths():
    """The outliner consumes files, the live layer consumes names.

    Both read the same stack; only the projection differs.
    """
    from sciviz.core._fonts import _fallback_faces, _fallback_families
    stack = "'Latin Modern Roman', DejaVu Sans, serif"
    assert _fallback_faces(stack, False, False) == \
        tuple(path for _name, path in _fallback_families(stack, False, False))


# ---------------------------------------------------------------------------
# 5. The export surface
# ---------------------------------------------------------------------------

def test_pdf_hybrid_hands_cairosvg_both_layers(monkeypatch, tmp_path):
    calls = {}

    class FakeCairoSvg:
        @staticmethod
        def svg2pdf(*, bytestring, write_to):
            calls["svg"] = bytestring.decode("utf-8")

    monkeypatch.setitem(sys.modules, "cairosvg", FakeCairoSvg)
    monkeypatch.setattr("shutil.which", lambda name: None)
    Diagram.for_paper(Text("quote me")).save(tmp_path / "out.pdf",
                                             text_mode="hybrid")
    assert "<path" in calls["svg"]
    assert "quote me" in calls["svg"]
    assert f'fill-opacity="{_SHADOW_FILL_OPACITY}"' in calls["svg"]


def test_png_hybrid_hands_resvg_both_layers(monkeypatch, tmp_path):
    calls = {}

    class FakeResvg:
        @staticmethod
        def svg_to_bytes(*, svg_string, width, height):
            calls["svg"] = svg_string
            return b"png"

    monkeypatch.setitem(sys.modules, "resvg_py", FakeResvg)
    Diagram.for_paper(Text("quote me")).save(tmp_path / "out.png",
                                             text_mode="hybrid")
    assert "<path" in calls["svg"]
    assert "quote me" in calls["svg"]


def test_unknown_text_mode_names_every_supported_mode(tmp_path):
    with pytest.raises(ValueError, match="hybrid"):
        Diagram.for_paper(Text("x")).save(tmp_path / "out.pdf",
                                          text_mode="nonsense")
