"""Declared printed shape: the aspect-ratio vocabulary.

A figure -- or any subtree inside one -- can *declare the shape it wants
to print at* instead of the author hand-tuning containers until the
proportions come out right::

    Diagram.for_paper(body, target_width_pt=505, target_aspect="landscape")
    Aspect("landscape", staged_loop)          # one inner component only

:class:`AspectSpec` is the value type behind both surfaces: a
width-to-height band plus a penalty function the layout engine minimises.
Named shapes are read the way people say them aloud -- a *landscape*
figure is wider than it is tall -- so bands are stored as ``w / h``.

The named bands are deliberately broad. A name states the *intent*
("this should read as a wide strip"); pass ``ratio=`` to tighten it to a
specific proportion when a venue or a page budget demands one.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple, Union

#: Named width:height bands. Adjacent names share an edge, so every
#: positive ratio falls in exactly one named shape (``portrait`` below
#: 0.85, ``square`` around 1, ``landscape`` above 1.2, ``panorama`` for
#: banner strips).
NAMED_ASPECTS: dict = {
    "portrait": (0.40, 0.85),
    "square": (0.85, 1.20),
    "landscape": (1.20, 2.60),
    "panorama": (2.40, 6.00),
}

AspectLike = Union[str, "AspectSpec", float, int, Sequence[float], None]


class AspectSpec:
    """A declared width:height band.

    Parameters
    ----------
    name : str, optional
        A key of :data:`NAMED_ASPECTS`. Supplies the band when ``ratio``
        is not given, and names the goal in error messages.
    ratio : float or (float, float), optional
        Tightens the band. A single number is read as the wanted
        width:height proportion and is admitted with a small symmetric
        tolerance; a pair is a hard ``(min, max)`` band. When ``name`` is
        also given, the tightened band must lie inside the named one --
        contradicting the name is an authoring error, not a silent
        override.
    priority : str
        How the goal competes with the width target.
        ``"preferred"`` (default) keeps the historical contract: land
        ``target_width_pt`` first, use the shape to break ties.
        ``"required"`` says the shape is the point of the figure and the
        author will pay for it in print scale -- the width constraint
        then satisfices at ``min_effective_font_pt`` (the figure may
        overshoot the target as far as the type stays readable) and the
        shape decides among the candidates that clear that floor.
    """

    __slots__ = ("name", "min_ratio", "max_ratio", "priority")

    #: Half-width of the band synthesised around a single ``ratio=``
    #: number, as a multiplicative factor.
    _RATIO_TOLERANCE = 1.12

    #: Accepted ``priority`` values, weakest first.
    PRIORITIES = ("preferred", "required")

    def __init__(self, name: Optional[str] = None, *,
                 ratio: Union[float, Sequence[float], None] = None,
                 priority: str = "preferred"):
        if priority not in self.PRIORITIES:
            raise ValueError(
                f"aspect priority must be one of {self.PRIORITIES}")
        band: Optional[Tuple[float, float]] = None
        if name is not None:
            key = str(name).strip().lower()
            if key not in NAMED_ASPECTS:
                raise ValueError(
                    f"unknown aspect {name!r}; expected one of "
                    f"{sorted(NAMED_ASPECTS)} or an explicit ratio")
            name = key
            band = NAMED_ASPECTS[key]
        if ratio is not None:
            tight = self._band_from_ratio(ratio)
            if band is not None:
                lo, hi = band
                if tight[1] < lo or tight[0] > hi:
                    raise ValueError(
                        f"aspect ratio {ratio!r} lies outside the "
                        f"{name!r} band {band}; drop the name or widen "
                        f"the ratio")
                tight = (max(tight[0], lo), min(tight[1], hi))
            band = tight
        if band is None:
            raise ValueError("AspectSpec needs a name or a ratio")
        self.name = name
        self.priority = priority
        self.min_ratio, self.max_ratio = band

    # -- construction ---------------------------------------------------

    @staticmethod
    def _band_from_ratio(ratio) -> Tuple[float, float]:
        if isinstance(ratio, (int, float)):
            r = float(ratio)
            if r <= 0.0:
                raise ValueError("aspect ratio must be positive")
            tol = AspectSpec._RATIO_TOLERANCE
            return (r / tol, r * tol)
        if isinstance(ratio, (tuple, list)) and len(ratio) == 2:
            lo, hi = float(ratio[0]), float(ratio[1])
            if lo > hi:
                lo, hi = hi, lo
            if lo <= 0.0:
                raise ValueError("aspect ratio must be positive")
            return (lo, hi)
        raise TypeError(
            "ratio must be a number or a (min, max) pair of width:height "
            "proportions")

    @classmethod
    def parse(cls, value: AspectLike) -> Optional["AspectSpec"]:
        """Coerce the public ``target_aspect`` vocabulary to a spec.

        ``None`` passes through. A name or an existing spec is the new
        vocabulary. Bare numbers keep their historical
        ``Diagram(target_aspect=...)`` meaning -- *height over width*,
        with a single number read as a height ceiling -- so figures
        written before the vocabulary existed keep their shape.
        """
        if value is None:
            return None
        if isinstance(value, AspectSpec):
            return value
        if isinstance(value, str):
            return cls(value)
        if isinstance(value, (int, float)):
            hi_hw = float(value)
            if hi_hw <= 0.0:
                raise ValueError("target_aspect must be positive")
            # h/w <= hi  <=>  w/h >= 1/hi.
            return cls.from_band(1.0 / hi_hw, float("inf"))
        if isinstance(value, (tuple, list)) and len(value) == 2:
            lo_hw, hi_hw = float(value[0]), float(value[1])
            if lo_hw > hi_hw:
                lo_hw, hi_hw = hi_hw, lo_hw
            lo = 1.0 / hi_hw if hi_hw > 0.0 else 0.0
            hi = 1.0 / lo_hw if lo_hw > 0.0 else float("inf")
            return cls.from_band(lo, hi)
        raise TypeError(
            "target_aspect must be None, an aspect name, an AspectSpec, "
            "a number, or a (min, max) pair")

    @classmethod
    def from_band(cls, min_ratio: float, max_ratio: float, *,
                  priority: str = "preferred") -> "AspectSpec":
        """Build a spec straight from a width:height band (no name)."""
        obj = cls.__new__(cls)
        object.__setattr__(obj, "name", None)
        object.__setattr__(obj, "priority", priority)
        object.__setattr__(obj, "min_ratio", float(min_ratio))
        object.__setattr__(obj, "max_ratio", float(max_ratio))
        return obj

    @property
    def is_required(self) -> bool:
        return self.priority == "required"

    # -- evaluation -----------------------------------------------------

    def contains(self, width: float, height: float) -> bool:
        return self.penalty(width, height) <= 0.0

    def penalty(self, width: float, height: float) -> float:
        """Scale-free distance from the band (0.0 when satisfied).

        The penalty is expressed as a *relative* miss so goals declared
        on a small card and on the whole page are directly comparable,
        and so the engine can add several of them up.
        """
        if width <= 0.0 or height <= 0.0:
            return 0.0
        r = width / height
        if r < self.min_ratio:
            return (self.min_ratio - r) / self.min_ratio
        if self.max_ratio != float("inf") and r > self.max_ratio:
            return (r - self.max_ratio) / self.max_ratio
        return 0.0

    # -- interop --------------------------------------------------------

    def as_height_band(self) -> Tuple[float, float]:
        """The equivalent ``(min, max)`` band in height/width terms."""
        lo = 0.0 if self.max_ratio == float("inf") else 1.0 / self.max_ratio
        hi = float("inf") if self.min_ratio <= 0.0 else 1.0 / self.min_ratio
        return (lo, hi)

    def __eq__(self, other) -> bool:
        return (isinstance(other, AspectSpec)
                and self.min_ratio == other.min_ratio
                and self.max_ratio == other.max_ratio)

    def __hash__(self) -> int:
        return hash((self.min_ratio, self.max_ratio))

    def __repr__(self) -> str:
        band = f"ratio=({self.min_ratio:.2f}, {self.max_ratio:.2f})"
        prio = "" if self.priority == "preferred" else f", {self.priority}"
        if self.name:
            return f"AspectSpec({self.name!r}, {band}{prio})"
        return f"AspectSpec({band}{prio})"
