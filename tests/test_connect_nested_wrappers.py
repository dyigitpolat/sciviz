"""Semantic wrappers remain transparent to connector discovery."""

from sciviz import Anchor, Banner, Box, Card, Column, Connect, Diagram, Palette, Row, Text


def test_connect_resolves_anchors_nested_in_card_and_banner():
    left = Banner(
        Card(
            "Source",
            Anchor("source", Box("A")),
            role=Palette.blue,
        ),
        above=Text("phase"),
    )
    right = Anchor("target", Box("B"))
    diagram = Diagram.for_paper(
        Column(
            Row(left, right, gap="lg"),
            Connect("source", "target", src_side="right", dst_side="left"),
        )
    )

    svg = diagram.render(embed_fonts=False)

    assert 'marker-end="url(#flow-' in svg
    assert "Source" in svg and ">A<" in svg and ">B<" in svg
