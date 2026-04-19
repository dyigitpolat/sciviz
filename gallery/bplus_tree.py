"""B+ tree: separator keys above, linked leaves below.

Refactored: the bespoke BPlusTree class is replaced by the generic
``NodeTree``.  The whole tree is just a nested tuple ``(cells, children)``.
Leaf sibling pointers are drawn automatically.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, NodeTree, Math, Caption, Section,
                    Text, Box, Spacer, Inline, Legend, LegendItem)

# Tree structure: (cells, children) recursively.  Leaves have children=[].
tree = (["30", "60"], [
    (["10", "20"], [
        (["7", "9"], []), (["13", "17"], []), (["22", "28"], []),
    ]),
    (["40", "50"], [
        (["33", "37"], []), (["42", "48"], []), (["53", "58"], []),
    ]),
    (["70", "80"], [
        (["63", "67"], []), (["73", "77"], []), (["83", "89"], []),
    ]),
])
node_tree = NodeTree(tree, cell_w=30, cell_h=24, level_gap=40, page_gap=14)

legend = Legend(
    LegendItem(Box(width=18, height=14, fill="none", stroke="text", radius=1),
               "internal page (separator keys)"),
    LegendItem(Box(width=18, height=14, fill="accent_soft", stroke="text", radius=1),
               "leaf page (payload + sibling pointer)"),
    gap="lg",
)

complexity = Inline(
    Text("height", size="small", color="muted", weight="700"),
    r"$h = \lceil \log_B N \rceil$",
    Spacer(14, 0),
    Text("lookup", size="small", color="muted", weight="700"),
    r"$O(h)$",
    Spacer(14, 0),
    Text("range scan of k keys", size="small", color="muted", weight="700"),
    r"$O(h + k/B)$",
    gap="xs",
)

d = Diagram(
    title="B+ tree: separator keys above, linked leaves below",
    subtitle="internal pages route; leaves store data in key order with forward pointers",
    body=Column(node_tree, legend, complexity, gap="lg", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "bplus_tree")
print("Rendered:", d.measure())
