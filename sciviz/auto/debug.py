"""Layout debug recorder.

A :class:`DebugRecorder` is an append-only log of decisions made by the
two automatic subsystems in :mod:`sciviz.auto`:

* :mod:`sciviz.auto.router` -- the topological path planner used by
  :class:`~sciviz.connect.Connect` in routed / bus mode.
* :mod:`sciviz.auto.labelplacer` -- the geometric label placer used by
  every bus / long-wire label.

Recording is off by default: the instrumentation sites are a
no-op unless a recorder has been pushed onto the active
:data:`_ACTIVE` stack via :func:`record_into` (or equivalently by
``Diagram.save_debug``).

The recorder intentionally knows nothing about rendering. It stores
plain Python dicts with pixel-coordinate rectangles and scalar scores;
a separate HTML template turns those into an interactive overlay.

Example::

    from sciviz.auto.debug import DebugRecorder, record_into

    rec = DebugRecorder()
    with record_into(rec):
        diagram.save("out.svg")
    rec.summary()  # -> dict with per-decision statistics
"""
from __future__ import annotations

import contextlib
import copy
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple


Rect = Tuple[float, float, float, float]
Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# record types
# ---------------------------------------------------------------------------

@dataclass
class LabelCandidate:
    """One of the candidates the label placer considered."""
    rect: Rect
    side: str
    overlap: float
    extrapolated: bool
    preference_penalty: int
    clearance: float
    distance_to_midpoint: float


@dataclass
class LabelPlacementRecord:
    """What the label placer was asked and what it chose."""
    owner: str                            # hint for the debug UI (e.g. "bus:foo")
    segment: Tuple[Point, Point]
    label_size: Tuple[float, float]
    prefer: str
    obstacles: List[Rect]
    candidates: List[LabelCandidate]
    chosen: LabelCandidate
    chosen_index: int


@dataclass
class RouterRecord:
    """What the orthogonal path planner was asked and what it returned."""
    owner: str
    src_name: str
    dst_name: str
    src_side: str
    dst_side: str
    anchors: List[Tuple[str, Rect]]
    regions: List[Tuple[str, Rect]]
    required_crossings: List[str]
    waypoints: List[Point]
    style_hint: str
    retried_without_clearance: bool
    min_clearance: float


@dataclass
class DebugRecorder:
    """Append-only log of automatic-layout decisions."""
    label_placements: List[LabelPlacementRecord] = field(default_factory=list)
    router_paths: List[RouterRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def record_label(self, record: LabelPlacementRecord) -> None:
        self.label_placements.append(record)

    def record_router(self, record: RouterRecord) -> None:
        self.router_paths.append(record)

    def summary(self) -> Dict[str, Any]:
        lp = self.label_placements
        rp = self.router_paths
        return {
            "label_placements": len(lp),
            "label_overlap_nonzero": sum(1 for r in lp if r.chosen.overlap > 0.0),
            "router_paths": len(rp),
            "router_retried": sum(1 for r in rp if r.retried_without_clearance),
            "notes": list(self.notes),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Cheap snapshot suitable for JSON serialisation."""
        def _rec(r: Any) -> Any:
            return asdict(copy.copy(r))
        return {
            "label_placements": [_rec(r) for r in self.label_placements],
            "router_paths":     [_rec(r) for r in self.router_paths],
            "notes":            list(self.notes),
            "summary":          self.summary(),
        }


# ---------------------------------------------------------------------------
# context-var wiring
# ---------------------------------------------------------------------------

_ACTIVE: ContextVar[Optional[DebugRecorder]] = ContextVar(
    "sciviz_debug_recorder", default=None,
)


def active() -> Optional[DebugRecorder]:
    """Return the currently installed recorder, or ``None``."""
    return _ACTIVE.get()


@contextlib.contextmanager
def record_into(recorder: DebugRecorder) -> Iterator[DebugRecorder]:
    """Install ``recorder`` as the active debug sink for the duration of
    the ``with`` block.

    Instrumentation sites call :func:`active` and, if a recorder is
    installed, append their records to it. Nested ``record_into`` calls
    temporarily replace the active recorder and restore the outer one on
    exit.
    """
    token = _ACTIVE.set(recorder)
    try:
        yield recorder
    finally:
        _ACTIVE.reset(token)


# ---------------------------------------------------------------------------
# helpers for instrumentation sites
# ---------------------------------------------------------------------------

def emit_label(owner: str,
               segment: Tuple[Point, Point],
               label_size: Tuple[float, float],
               prefer: str,
               obstacles: Sequence[Rect],
               candidates: Sequence[LabelCandidate],
               chosen_index: int) -> None:
    """Helper used by :mod:`sciviz.auto.labelplacer` to log a placement.

    Cheap no-op when no recorder is installed.
    """
    rec = _ACTIVE.get()
    if rec is None:
        return
    chosen = candidates[chosen_index]
    rec.record_label(LabelPlacementRecord(
        owner=owner,
        segment=segment,
        label_size=label_size,
        prefer=prefer,
        obstacles=list(obstacles),
        candidates=list(candidates),
        chosen=chosen,
        chosen_index=chosen_index,
    ))


def emit_route(owner: str,
               *,
               src_name: str, dst_name: str,
               src_side: str, dst_side: str,
               anchors: Sequence[Tuple[str, Rect]],
               regions: Sequence[Tuple[str, Rect]],
               required_crossings: Sequence[str],
               waypoints: Sequence[Point],
               style_hint: str,
               retried_without_clearance: bool,
               min_clearance: float) -> None:
    """Helper used by :mod:`sciviz.auto.router` to log a routed path."""
    rec = _ACTIVE.get()
    if rec is None:
        return
    rec.record_router(RouterRecord(
        owner=owner,
        src_name=src_name, dst_name=dst_name,
        src_side=src_side, dst_side=dst_side,
        anchors=list(anchors), regions=list(regions),
        required_crossings=list(required_crossings),
        waypoints=list(waypoints),
        style_hint=style_hint,
        retried_without_clearance=retried_without_clearance,
        min_clearance=min_clearance,
    ))
