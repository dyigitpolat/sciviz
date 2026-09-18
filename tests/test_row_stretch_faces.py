"""Row(align="stretch") equalises painted faces, not anchor outer boxes.

An Anchor with flow-lane margins measures taller than the card it wraps;
equalising the outer boxes left the margin-less sibling's card taller
than the margined ones by exactly their margins (Fig. 1's bottom row).
"""

from __future__ import annotations

from sciviz import Anchor, Box, Card, DEFAULT_THEME, Palette, Row, card_header

T = DEFAULT_THEME


def _card(name: str, *body) -> Card:
    return Card(card_header(name, size="micro"), *body, role=Palette.gray,
                padding="xs")


def test_margined_anchor_and_bare_sibling_share_one_face_height():
    a = _card("A", Box("one line"))
    b = _card("B", Box("one line"))
    c = _card("C", Box("one line"), Box("second line"))
    row = Row(Anchor("a", a, margin_top=8.0), Anchor("b", b), c,
              gap="xs", align="stretch", equal_widths=True)
    row.measure(T)
    ha, hb, hc = (x.measure(T).h for x in (a, b, c))
    assert abs(ha - hc) < 1e-6 and abs(hb - hc) < 1e-6
    # The anchored child's outer box carries its margin on top of the face.
    assert abs(row.children[0].measure(T).h - (ha + 8.0)) < 1e-6
