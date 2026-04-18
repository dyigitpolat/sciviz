"""Paxos (single-decree): two phases to agreement.

Refactored to use the generic ``Sequence`` UML-style sequence diagram
(proper cross-lane arrows on lifelines, not bars on a timeline).  Colours
are role-based (info/success/alert) rather than hex codes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sciviz import (Diagram, Column, Row, Panel, Section, TextBlock,
                    Sequence, Caption)

# Lifelines and timeline messages.  Each message: (t, src, dst, label, role)
seq = Sequence(
    actors=["Proposer", "Acceptor 1", "Acceptor 2", "Acceptor 3", "Learner"],
    messages=[
        # Phase 1: prepare / promise
        (0, "Proposer",  "Acceptor 1", "prepare(n)",  "blue"),
        (1, "Proposer",  "Acceptor 2", "prepare(n)",  "blue"),
        (2, "Proposer",  "Acceptor 3", "prepare(n)",  "blue"),
        (3, "Acceptor 1","Proposer",   "promise",     "green"),
        (4, "Acceptor 2","Proposer",   "promise",     "green"),
        (5, "Acceptor 3","Proposer",   "promise",     "green"),
        # Phase 2: accept / accepted
        (6, "Proposer",  "Acceptor 1", "accept(n,v)", "blue"),
        (7, "Proposer",  "Acceptor 2", "accept(n,v)", "blue"),
        (8, "Proposer",  "Acceptor 3", "accept(n,v)", "blue"),
        (9, "Acceptor 1","Learner",    "accepted",    "green"),
        (10,"Acceptor 2","Learner",    "accepted",    "green"),
        (11,"Acceptor 3","Learner",    "accepted",    "green"),
        (12,"Learner",   "Learner",    "decide v",    "amber"),
    ],
    width=620, row_h=22,
)

phase1 = Section(
    "Phase 1 -- prepare", TextBlock(
        "Proposer chooses ballot n, broadcasts prepare(n).  An acceptor "
        "responds promise(n, v', n') if n is the highest it has seen, where "
        "(n', v') is its last accepted value (None if none).",
        size="small", color="muted", max_width=280),
    kicker="protocol",
)
phase2 = Section(
    "Phase 2 -- accept", TextBlock(
        "On a majority of promises, proposer sends accept(n, v) where v is "
        "the highest-ballot v' returned (else its own).  Acceptors reply "
        "accepted; the learner observes the chosen value.",
        size="small", color="muted", max_width=280),
    kicker="protocol",
)
safety = Section(
    "Safety", TextBlock(
        "Any two majorities overlap, so a later ballot always sees an earlier "
        "accepted value and adopts it.  At most one value is ever chosen.",
        size="small", color="muted", max_width=280),
    kicker="invariant",
)

d = Diagram(
    title="Paxos (single-decree): two phases to agreement",
    subtitle="proposer + 3 acceptors + 1 learner; time runs downward along lifelines",
    body=Column(
        seq,
        Row(phase1, phase2, safety, gap="lg", align="start"),
        gap="lg", align="center",
    ),
)
d.save_all(Path(__file__).resolve().parent / "_out" / "paxos")
print("Rendered:", d.measure())
