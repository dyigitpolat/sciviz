from types import SimpleNamespace

from sciviz import Canvas
from sciviz.composition._flow import _draw_placed_label


def _svg_for(label: str) -> str:
    canvas = Canvas()
    placed = SimpleNamespace(rect=(0.0, 0.0, 100.0, 20.0),
                             rotation=0.0, anchor="middle")
    _draw_placed_label(canvas, placed, label, 10.0, "#111111")
    return canvas.to_svg(100.0, 20.0)


def test_connector_prose_is_upright_but_symbols_remain_italic():
    assert 'font-style="italic"' not in _svg_for("Reward Modeling")
    assert 'font-style="italic"' in _svg_for("O")
    assert 'font-style="italic"' in _svg_for("z_i")


def test_a_phrase_quoting_an_operator_stays_upright():
    # Two or more words make a phrase; the operator is part of the prose.
    assert 'font-style="italic"' not in _svg_for("dose per kilogram, ×0.25 to ×4")
    assert 'font-style="italic"' not in _svg_for("flow rate × duration")
    # Symbolic captions keep their italic.
    assert 'font-style="italic"' in _svg_for("W x + b")
    assert 'font-style="italic"' in _svg_for("λ × g")
