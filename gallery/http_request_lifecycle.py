"""What happens when you hit Enter: the HTTP request lifecycle.

Nine steps grouped into three role-coloured phases (connect / process /
respond), each a :class:`Card` of :class:`StepCell` rows inside a
:class:`Stripe`, chained with inline :class:`Connect` arrows annotated
with rough per-phase latency. All pictograms come from :class:`Icon`;
several (``globe``, ``handshake``, ``code-xml``, ``app-window``) only
exist because of the Hugeicons bank -- Lucide's curated subset doesn't
cover them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (
    Card, Connect, Diagram, Icon, Palette, Row, StepCell, Stripe, Text,
)

PHASES = [
    {
        "name": "Resolve & Connect",
        "icon": "globe",
        "role": Palette.blue,
        "steps": [
            ("DNS Lookup", "globe"),
            ("TCP Handshake", "handshake"),
            ("TLS Handshake", "lock"),
        ],
    },
    {
        "name": "Request & Process",
        "icon": "server",
        "role": Palette.amber,
        "steps": [
            ("HTTP Request Sent", "upload"),
            ("Server Routes Request", "server"),
            ("Database Query", "database"),
        ],
    },
    {
        "name": "Respond & Render",
        "icon": "app-window",
        "role": Palette.teal,
        "steps": [
            ("HTTP Response Streamed", "download"),
            ("HTML/CSS/JS Parsed", "code-xml"),
            ("Page Painted", "app-window"),
        ],
    },
]


def step_cell(label: str, icon_name: str, role, index: int) -> StepCell:
    return StepCell(label, Icon(icon_name, size=26, color=role), index=index, role=role)


def phase_card(phase: dict, start_index: int) -> Card:
    header = Row(
        Icon(phase["icon"], size=18, color="white"),
        Text(phase["name"], color="white", weight="700"),
        gap="xs",
    )
    cells = [
        step_cell(label, icon_name, phase["role"], start_index + i)
        for i, (label, icon_name) in enumerate(phase["steps"])
    ]
    return Card(header, Stripe(cells, role=phase["role"]), role=phase["role"])


idx = 1
cards = []
for phase in PHASES:
    cards.append(phase_card(phase, idx))
    idx += len(phase["steps"])

body = Row(
    cards[0], Connect(direction="right", label="~1-2 RTT"),
    cards[1], Connect(direction="right", label="~ms"),
    cards[2],
    gap="lg", align="center",
)

d = Diagram(
    title="What Happens When You Hit Enter",
    subtitle="The life of a single HTTP request, from address bar to painted pixels",
    body=body,
)
d.save_all(Path(__file__).resolve().parents[1] / "_out" / "http_request_lifecycle")
print("Rendered:", d.measure())
