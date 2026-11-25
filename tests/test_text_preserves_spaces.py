"""A text run with leading or repeated spaces is drawn as it was measured."""
from sciviz import Diagram, Text


def test_indented_mono_line_preserves_its_spaces():
    svg = Diagram.for_paper(Text("    return x  # two", font="mono")).render()
    assert 'xml:space="preserve"' in svg


def test_plain_text_is_unchanged():
    svg = Diagram.for_paper(Text("plain words")).render()
    assert 'xml:space' not in svg
