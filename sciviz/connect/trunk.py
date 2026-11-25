"""Trunk connector: several sources join into ONE trunk, which forks onto several targets.

The form of a tuning fork at each end: every source sends a short leg along
the trunk axis to the *join* level, the legs meet on the trunk, the trunk
runs as a single line to the *fork* level, and there it splits into one leg
per target. A source or target that already stands on the trunk gets a
straight leg. With one source and one target on the trunk the route is one
straight line, so the single and the forked connectors of a figure share one
form.

This module is pure geometry (no canvas, no theme), so a diagram element and
a plot script draw the same route: :func:`trunk_route` returns the legs as
polylines, :meth:`TrunkRoute.commands` rounds their corners into ``M`` /
``L`` / ``Q`` path commands and :meth:`TrunkRoute.svg_path` prints them as
an SVG path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]

__all__ = ["TrunkRoute", "trunk_route", "round_corners"]


def _dedupe(points: Sequence[Point]) -> List[Point]:
    out: List[Point] = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if not out or abs(out[-1][0] - p[0]) > 1e-9 or abs(out[-1][1] - p[1]) > 1e-9:
            out.append(p)
    return out


def round_corners(points: Sequence[Point], radius: float) -> List[tuple]:
    """One polyline as path commands, each inner corner cut by a quadratic arc.

    Returns ``[("M", p), ("L", p), ("Q", control, p), ...]``. A corner keeps
    at most half of each of its two sides, so two corners on one short side
    never overlap; ``radius <= 0`` leaves the corners sharp.
    """
    pts = _dedupe(points)
    if not pts:
        return []
    cmds: List[tuple] = [("M", pts[0])]
    for k in range(1, len(pts)):
        p = pts[k]
        if k == len(pts) - 1 or radius <= 0.0:
            cmds.append(("L", p))
            continue
        a, b = pts[k - 1], pts[k + 1]
        if abs((p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])) <= 1e-9:
            continue                             # no turn at this point: the side runs on
        la = ((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5
        lb = ((b[0] - p[0]) ** 2 + (b[1] - p[1]) ** 2) ** 0.5
        r = min(float(radius), la / 2.0, lb / 2.0)
        if r <= 1e-9:
            cmds.append(("L", p))
            continue
        start = (p[0] + (a[0] - p[0]) * r / la, p[1] + (a[1] - p[1]) * r / la)
        end = (p[0] + (b[0] - p[0]) * r / lb, p[1] + (b[1] - p[1]) * r / lb)
        cmds.append(("L", start))
        cmds.append(("Q", p, end))
    return cmds


def _toward(a: Point, b: Point, d: float) -> Point:
    """The point ``d`` from ``a`` toward ``b``, at most halfway."""
    length = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    if length <= 1e-9 or d <= 0.0:
        return a
    t = min(d, length / 2.0) / length
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


@dataclass(frozen=True)
class TrunkRoute:
    """The legs of a trunk connector, each a polyline with sharp corners.

    ``source_legs[i]`` runs from source ``i`` to the trunk's join point,
    ``trunk`` from the join point to the fork point, ``target_legs[j]`` from
    the fork point to target ``j``.
    """

    source_legs: Tuple[Tuple[Point, ...], ...]
    trunk: Tuple[Point, Point]
    target_legs: Tuple[Tuple[Point, ...], ...]

    @property
    def polylines(self) -> List[Tuple[Point, ...]]:
        """Every source leg, the trunk and every target leg, in that order."""
        return [*self.source_legs, self.trunk, *self.target_legs]

    def commands(self, radius: float = 0.0) -> List[List[tuple]]:
        """One command list per stroke, the corners rounded by ``radius``.

        The trunk is one stroke. Every leg is its own stroke and runs two
        corner lengths into the trunk (over the trunk.s own ink), so a leg that
        comes in from the side rounds into the trunk with a full corner and the
        two sides of a fork mirror each other.
        """
        j, f = self.trunk
        strokes: List[List[tuple]] = [[("M", j), ("L", f)]]
        for leg in self.source_legs:
            strokes.append(round_corners([*leg, _toward(j, f, 2.0 * radius)], radius))
        for leg in self.target_legs:
            strokes.append(round_corners([_toward(f, j, 2.0 * radius), *leg], radius))
        return strokes

    def svg_path(self, radius: float = 0.0, precision: int = 2) -> str:
        """The whole connector as one SVG path string."""
        out = []
        for stroke in self.commands(radius):
            for cmd in stroke:
                nums = " ".join(f"{v:.{precision}f}" for pt in cmd[1:] for v in pt)
                out.append(f"{cmd[0]}{nums}")
        return " ".join(out)


def trunk_route(sources: Sequence[Point], targets: Sequence[Point], *, join: float, fork: float,
                trunk: Optional[float] = None, axis: str = "vertical") -> TrunkRoute:
    """Route several sources through one trunk onto several targets.

    Parameters
    ----------
    sources, targets : sequences of ``(x, y)``
        The end points (at least one of each).
    join, fork : float
        The levels along the trunk axis where the source legs meet the trunk
        and where the trunk splits (``y`` values for a vertical trunk, ``x``
        values for a horizontal one). Each lies between its end points and
        the other level, so no leg doubles back.
    trunk : float, optional
        The trunk's position across its axis (``x`` for a vertical trunk).
        Default: the mean of all end points across the axis.
    axis : {"vertical", "horizontal"}
        The trunk's direction.
    """
    if axis not in ("vertical", "horizontal"):
        raise ValueError(f"axis must be 'vertical' or 'horizontal'; got {axis!r}")
    if not sources or not targets:
        raise ValueError("a trunk connector needs at least one source and one target")
    flip = axis == "horizontal"

    def uv(p):                                   # (across, along) of a point
        return (float(p[1]), float(p[0])) if flip else (float(p[0]), float(p[1]))

    def xy(c, a):                                # back to (x, y)
        return (a, c) if flip else (c, a)

    src, tgt = [uv(p) for p in sources], [uv(p) for p in targets]
    join, fork = float(join), float(fork)
    sign = 1.0 if fork >= join else -1.0         # the trunk's direction along its axis
    for name, pts, level, toward in (("source", src, join, 1.0), ("target", tgt, fork, -1.0)):
        for _, a in pts:
            if (level - a) * sign * toward < -1e-9:
                raise ValueError(f"a {name} at {a:g} lies past its level {level:g}: its leg would double back")
    across = (sum(c for c, _ in src + tgt) / len(src + tgt)) if trunk is None else float(trunk)
    j, f = xy(across, join), xy(across, fork)
    source_legs = tuple(tuple(_dedupe([xy(c, a), xy(c, join), j])) for c, a in src)
    target_legs = tuple(tuple(_dedupe([f, xy(c, fork), xy(c, a)])) for c, a in tgt)
    return TrunkRoute(source_legs=source_legs, trunk=(j, f), target_legs=target_legs)
