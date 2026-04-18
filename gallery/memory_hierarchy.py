"""Memory hierarchy of a modern CPU.

Six storage levels with three aligned annotation columns.  Colours are
automatically shaded by depth -- no hex codes in user code.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import Diagram, Pyramid, Caption, Column, Palette

pyramid = Pyramid([
    ("Registers", ["~1 KB",   "~0.3 ns", "~20 TB/s"]),
    ("L1 cache",  ["~64 KB",  "~1 ns",   "~5 TB/s"]),
    ("L2 cache",  ["~1 MB",   "~4 ns",   "~2 TB/s"]),
    ("L3 cache",  ["~32 MB",  "~12 ns",  "~400 GB/s"]),
    ("DRAM",      ["~256 GB", "~80 ns",  "~90 GB/s"]),
    ("NVMe SSD",  ["~8 TB",   "~80 us",  "~7 GB/s"]),
], width=420, tip_width=90, level_h=34, side_col_gap=18, color=Palette.blue)

d = Diagram(
    title="Memory Hierarchy: the five-decade capacity / speed tradeoff",
    subtitle="typical values for a modern server CPU",
    body=Column(
        pyramid,
        Caption("capacity grows ~10x per level; bandwidth shrinks ~10x; "
                "latency grows ~10x below L1"),
        gap="md", align="center",
    ),
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "memory_hierarchy")
print("Rendered:", d.measure())
