"""LSM-tree: write path and level compaction.

Refactored: each level is a ``Strip(mode="equal")`` of small boxes for
SSTables; flow uses a vertical ``Column`` with ``Connector`` arrows.
Sidebar uses ``Section`` + ``Math``.  No hex colours in user code.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, Box, Connector, Math, Section,
                    TextBlock, Text, Strip, Spacer, Palette)

def sstable(w=14, h=12, role="info"):
    """A small SSTable rectangle, soft-tinted by role."""
    return Box(width=w, height=h,
               fill=Palette.literal({"info":"#dbe3f1","warn":"#f8edd0",
                                      "alert":"#fde8e8","success":"#c7e5df"}[role]),
               stroke=Palette.literal({"info":"#3b5fa0","warn":"#b45309",
                                        "alert":"#b91c1c","success":"#2d7a70"}[role]),
               radius=1.5)

def level(label, count, role, w=16, h=14, gap="xs", side=None):
    items = [sstable(w, h, role) for _ in range(count)]
    return Row(
        Text(label, size="small", weight="700"),
        Strip(*items, mode="equal", gap=gap),
        Text(side or "", size="small", color="muted"),
        gap="md", align="center",
    )

memtable = Box(label="MemTable  (in-RAM skiplist)",
               width=200, height=26, fill="#fde8e8",
               stroke=Palette.alert.dark(), text_color="text",
               text_size="small", text_weight="700")

flow = Column(
    memtable,
    Connector("flush", direction="down", length=14),
    level("L0", 4, "warn",  w=22, h=15, side="overlapping keys"),
    Connector("compact", direction="down", length=14),
    level("L1", 8, "info",  w=18, h=14, side="sorted, ~10x L0"),
    Connector("compact", direction="down", length=14),
    level("L2", 16, "info", w=15, h=13, side="~10x L1"),
    Connector("compact", direction="down", length=14),
    level("L3", 24, "info", w=13, h=12, side="~10x L2"),
    gap="sm", align="center",
)

sidebar = Column(
    Section("Write amplification",
            Math(r"$\mathrm{WA} \approx \sum_{L=0}^{L_\mathrm{max}} "
                 r"\frac{|L_{L+1}|}{|L_L|} \approx 10\, L_\mathrm{max}$"),
            caption="leveled compaction"),
    Section("Read amplification",
            TextBlock(
                "One bloom-filter probe per level so point reads are "
                "O(L_max).  After L0, at most 1 SSTable per level matches.",
                size="small", color="muted", max_width=300)),
    Section("Tiered vs. leveled",
            TextBlock(
                "Tiered: low write-amp, high space-amp (Cassandra default).\n"
                "Leveled: moderate write-amp, low space-amp (RocksDB default).",
                size="small", color="muted", max_width=300)),
    gap="lg", align="start",
)

d = Diagram(
    title="LSM tree: write path and level compaction",
    subtitle="writes coalesce in memory, then cascade down levels in ~10x size ratios",
    body=Row(flow, Spacer(40, 0), sidebar, gap="lg", align="center"),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "lsm_tree")
print("Rendered:", d.measure())
