"""GroupedBarChart: vertical bars organised into per-title groups.

A general-purpose grouped bar chart for the "N treatments across K
benchmarks" pattern.  Every decoration is optional and separately
toggleable so the same primitive renders:

* a classic 2-bar comparison with delta arrow and gain label
  (``Baseline vs. Method``),
* a 3+ bar ablation grid without delta annotations,
* a "target line only" chart for upper-bound references, or
* a flat grouped-bar chart with no cards or target lines at all.

Data model::

    BarGroup("AIME 2024", values=[16.7, 43.3], annotation="+159.3%")

Styling model::

    BarSeries(name="TTRL", color="#1d3557", value_color="#ffffff")

Authors pass the data; placement, axis, ticks, and card layout come
from the chart.  All colours accept either a hex string or a
:class:`~sciviz.Theme` token (``"primary_fill"``, ``"highlight"`` ...).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BarSeries:
    """Per-series styling for a :class:`GroupedBarChart`.

    Parameters
    ----------
    name : str
        Optional legend / caption label (reserved for future use).
    color : ColorRef or str
        Bar fill.  Accepts a hex literal or a theme token
        (``"primary_fill"``, ``"accent_soft"`` ...).
    stroke : ColorRef or str, optional
        Bar border.  When ``None``, inherits ``color`` (flat bar).
    value_color : ColorRef or str, optional
        In-bar numeric label colour.  When ``None``, the chart picks
        ``theme.color_of("text")`` for pale fills and white for dark
        fills via a simple luminance check.
    """
    name: str = ""
    color: str = "primary_fill"
    stroke: Optional[str] = None
    value_color: Optional[str] = None


@dataclass(frozen=True)
class BarGroup:
    """One group of bars (one benchmark / scenario / condition).

    ``values`` is a sequence with one entry per :class:`BarSeries`.
    ``annotation`` is a free-form label (e.g. ``"+74.9%"``, ``"p<.01"``)
    drawn just above the group's target line.  ``target`` overrides the
    horizontal dashed reference line; by default the chart places it at
    ``max(values)``.
    """
    title: str
    values: Sequence[float]
    annotation: Optional[str] = None
    target: Optional[float] = None
    color: Optional[str] = None
    value_color: Optional[str] = None


# Convenience inputs: the chart accepts raw tuples as well as dataclasses.
GroupLike = Union[
    BarGroup,
    Tuple[str, Sequence[float]],
    Tuple[str, Sequence[float], Optional[str]],
    Tuple[str, float, float],                       # legacy 2-bar shape
    Tuple[str, float, float, Optional[str]],        # legacy 2-bar + annotation
]
SeriesLike = Union[BarSeries, str, Tuple[str, str], Tuple[str, str, str]]


def _coerce_group(g: GroupLike) -> BarGroup:
    if isinstance(g, BarGroup):
        return g
    if not isinstance(g, tuple) or len(g) < 2:
        raise TypeError(f"bar group must be BarGroup or tuple; got {g!r}")
    # Legacy 2-bar shape: (title, baseline, treatment[, annotation]).
    if len(g) >= 3 and isinstance(g[1], (int, float)) \
            and isinstance(g[2], (int, float)):
        title = g[0]
        vals = [float(g[1]), float(g[2])]
        ann = g[3] if len(g) > 3 else None
        return BarGroup(title, vals, annotation=ann)
    # New shape: (title, [values][, annotation]).
    if len(g) == 2:
        title, values = g
        return BarGroup(title, [float(v) for v in values])
    if len(g) == 3:
        title, values, ann = g
        return BarGroup(title, [float(v) for v in values], annotation=ann)
    raise TypeError(
        "bar group must be (title, [values]) or "
        "(title, baseline, treatment[, annotation]); "
        f"got {g!r}"
    )


def _coerce_series(s: SeriesLike) -> BarSeries:
    if isinstance(s, BarSeries):
        return s
    if isinstance(s, str):
        return BarSeries(color=s)
    if isinstance(s, tuple):
        if len(s) == 2:
            color, value_color = s
            return BarSeries(color=color, value_color=value_color)
        if len(s) == 3:
            name, color, value_color = s
            return BarSeries(name=name, color=color, value_color=value_color)
    raise TypeError(
        "series must be BarSeries, hex string, (color, value_color), or "
        f"(name, color, value_color); got {s!r}"
    )


# Sensible series defaults that adapt to the number of bars per group.
# Two bars -> paper-standard ``(baseline = primary_soft, treatment = primary)``
# pair. Any other count -> cycle a short categorical palette so authors can
# drop in an N-series chart without hand-picking colours.
_TWO_BAR_DEFAULT = (
    BarSeries(color="primary_soft"),
    BarSeries(color="primary", value_color="#ffffff"),
)
_CATEGORICAL_DEFAULT = (
    "primary", "accent", "highlight", "warning", "purple", "blue",
)


def _default_series(n_bars: int) -> Sequence[BarSeries]:
    if n_bars == 2:
        return _TWO_BAR_DEFAULT
    return tuple(
        BarSeries(color=_CATEGORICAL_DEFAULT[i % len(_CATEGORICAL_DEFAULT)])
        for i in range(max(1, n_bars))
    )


# ---------------------------------------------------------------------------
# Element
# ---------------------------------------------------------------------------

class GroupedBarChart(Element):
    """Grouped vertical bar chart with independently toggleable decorations.

    Parameters
    ----------
    groups : sequence
        Each entry is a :class:`BarGroup`, a ``(title, [values])`` tuple,
        a ``(title, [values], annotation)`` tuple, or -- for the common
        2-bar case -- a ``(title, baseline, treatment[, annotation])``
        tuple.
    series : sequence, optional
        Per-bar styling.  Either :class:`BarSeries` instances or short
        tuples (see :func:`_coerce_series`).  Defaults to a 2-series
        ``(primary_soft, primary)`` pair.
    y_max, y_step : float, optional
        Explicit axis extent and tick spacing.  When ``y_max=None``, the
        chart uses ``1.05 * max(all values / targets)``.
    y_label : str
        Vertical axis label (rotated 90 degrees).
    show_cards, show_target_line, show_delta_arrow, show_values,
    show_titles, show_axis : bool
        Decoration toggles.  Disable any subset to simplify the chart.
    delta_from, delta_to : int
        Series indices joined by the delta arrow (negative indices count
        from the end, so ``delta_to=-1`` always targets the last series).
        Ignored unless ``show_delta_arrow``.
    annotation_color, card_fill, card_stroke, wash, axis_color,
    target_color, delta_color, title_color : str
        Theme tokens or hex literals for each decoration.
    value_formatter : callable
        ``float -> str`` formatter for in-bar numerics.  Defaults to
        trimming trailing zeros (``16.70 -> "16.7"``).
    """

    _PLOT_SIZES = {
        "sm": (240.0, 150.0),
        "md": (300.0, 190.0),
        "lg": (360.0, 260.0),
        "xl": (440.0, 300.0),
    }

    def __init__(self,
                 groups: Sequence[GroupLike],
                 *,
                 series: Optional[Sequence[SeriesLike]] = None,
                 y_max: Optional[float] = None,
                 y_step: float = 20.0,
                 y_label: str = "",
                 plot_width: Optional[float] = None,
                 plot_height: Optional[float] = None,
                 size: str = "lg",
                 bar_width: float = 34.0,
                 intra_gap: float = 8.0,
                 inter_gap: float = 18.0,
                 panel_pad: float = 12.0,
                 show_cards: bool = True,
                 show_target_line: bool = True,
                 show_delta_arrow: bool = True,
                 show_values: bool = True,
                 show_titles: bool = True,
                 show_axis: bool = True,
                 grid: Optional[bool] = None,
                 delta_from: int = 0,
                 delta_to: int = -1,
                 annotation_color: str = "highlight",
                 card_fill: str = "bg_panel",
                 card_stroke: str = "border",
                 wash: str = "bg_subtle",
                 axis_color: str = "muted",
                 target_color: str = "text",
                 delta_color: str = "text",
                 title_color: str = "text",
                 value_formatter: Optional[Callable[[float], str]] = None):
        self.groups = [_coerce_group(g) for g in groups]
        if not self.groups:
            raise ValueError("GroupedBarChart requires at least one group")
        widths = {len(g.values) for g in self.groups}
        if len(widths) > 1:
            raise ValueError(
                f"all groups must have the same number of bars; got {widths}")
        n_bars = len(self.groups[0].values)
        if series is None:
            series = _default_series(n_bars)
        self.series = [_coerce_series(s) for s in series]
        if n_bars and len(self.series) < n_bars:
            raise ValueError(
                f"need at least {n_bars} series for {n_bars} bars per group; "
                f"got {len(self.series)}")
        self.y_max = y_max
        self.y_step = float(y_step)
        self.y_label = y_label
        if size not in self._PLOT_SIZES:
            allowed = ", ".join(self._PLOT_SIZES)
            raise ValueError(f"GroupedBarChart.size must be one of {allowed}")
        default_width, default_height = self._PLOT_SIZES[size]
        self.plot_width = float(
            default_width if plot_width is None else plot_width
        )
        self.plot_height = float(
            default_height if plot_height is None else plot_height
        )
        self.bar_width = float(bar_width)
        self.intra_gap = float(intra_gap)
        self.inter_gap = float(inter_gap)
        self.panel_pad = float(panel_pad)
        self.show_cards = show_cards
        self.show_target_line = show_target_line
        self.show_delta_arrow = show_delta_arrow
        self.show_values = show_values
        self.show_titles = show_titles
        self.show_axis = show_axis
        # Card comparisons already provide strong row/column structure;
        # conventional flat bar charts need quiet horizontal guides.  The
        # automatic default follows that distinction without another style
        # decision at each call site.
        self.grid = (not show_cards) if grid is None else bool(grid)
        self.delta_from = int(delta_from)
        self.delta_to = int(delta_to)
        self.annotation_color = annotation_color
        self.card_fill = card_fill
        self.card_stroke = card_stroke
        self.wash = wash
        self.axis_color = axis_color
        self.target_color = target_color
        self.delta_color = delta_color
        self.title_color = title_color
        self.value_formatter = value_formatter or _default_fmt

    # --- axis helpers ----------------------------------------------------

    def _resolved_y_max(self) -> float:
        if self.y_max is not None:
            return float(self.y_max)
        peak = 0.0
        for g in self.groups:
            for v in g.values:
                peak = max(peak, v)
            if g.target is not None:
                peak = max(peak, g.target)
        return max(peak * 1.05, self.y_step)

    def _margins(self, theme: Theme):
        titles_above = self.show_titles and self.show_cards
        titles_below = self.show_titles and not self.show_cards
        top = (theme.text_height("panel") + theme.unit * 1.6
               if titles_above else theme.unit * 0.8)
        # Flat charts place values above bar tops. Reserve a real text band
        # so auto-scaled maxima never clip at the top of the element.
        if not self.show_cards:
            value_lines = 1 if self.show_values else 0
            annotation_lines = max(
                (len(g.annotation.splitlines()) if g.annotation else 0
                 for g in self.groups),
                default=0,
            )
            # Values and annotations are separate information layers.  They
            # must receive additive space: reserving only the larger layer
            # makes a two-line callout collide with the numeric value at the
            # top of the same bar.
            top += value_lines * theme.text_height("label")
            top += annotation_lines * theme.text_height("small")
            if value_lines and annotation_lines:
                top += theme.unit * 0.55
            if value_lines or annotation_lines:
                top += theme.unit * 0.4
        title_lines = max(
            (len(g.title.splitlines()) for g in self.groups), default=1
        ) if titles_below else 0
        bot = theme.text_height("tiny") + theme.unit * 0.8
        if titles_below:
            bot += title_lines * theme.text_height("tiny") + theme.unit * 0.6
        ymax = self._resolved_y_max()
        tick_w = theme.text_width(f"{int(ymax)}", "tiny", bold=False) \
            if self.show_axis else 0.0
        left  = tick_w + theme.unit * (1.4 if self.show_axis else 0.4)
        if self.y_label:
            left += theme.text_height("label") + theme.unit * 0.2
        right = theme.unit * 1.2
        return top, right, bot, left

    def _group_geometry(self, theme: Theme, plot_width: float):
        """Return group/bar geometry guaranteed to fit the plot width.

        Flat categorical charts use one equal slot per category. Card-style
        grouped comparisons retain their requested geometry when it fits and
        proportionally compact it when it does not. This keeps bar widths,
        padding, and gaps coherent instead of letting edge groups escape the
        axis frame.
        """
        n_groups = max(1, len(self.groups))
        n_series = max(1, len(self.groups[0].values))
        requested_bar = self.bar_width
        requested_intra = self.intra_gap
        requested_inter = self.inter_gap
        requested_pad = self.panel_pad
        if not self.show_cards:
            panel_w = plot_width / n_groups
            intra = min(requested_intra, panel_w * 0.10)
            max_bar = (
                panel_w - theme.unit * 1.2 - intra * (n_series - 1)
            ) / n_series
            bar_w = max(theme.unit * 0.9, min(requested_bar, max_bar))
            inner_w = n_series * bar_w + (n_series - 1) * intra
            pad = max(0.0, (panel_w - inner_w) / 2)
            return 0.0, panel_w, 0.0, bar_w, intra, pad

        natural_inner = (
            n_series * requested_bar + (n_series - 1) * requested_intra
        )
        natural_panel = natural_inner + 2 * requested_pad
        natural_total = (
            n_groups * natural_panel + (n_groups - 1) * requested_inter
        )
        scale = min(1.0, plot_width / natural_total) if natural_total else 1.0
        bar_w = requested_bar * scale
        intra = requested_intra * scale
        pad = requested_pad * scale
        panel_w = natural_panel * scale
        inter = requested_inter * scale
        total = n_groups * panel_w + (n_groups - 1) * inter
        return (plot_width - total) / 2, panel_w, inter, bar_w, intra, pad

    # --- geometry --------------------------------------------------------

    def measure(self, theme: Theme) -> BBox:
        top, right, bot, left = self._margins(theme)
        return BBox(left + self.plot_width + right,
                    top + self.plot_height + bot)

    # --- rendering -------------------------------------------------------

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        top, right, bot, left = self._margins(theme)
        px = x + left
        py = y + top
        pw, ph = self.plot_width, self.plot_height
        ymax = self._resolved_y_max()

        wash_col = theme.color_of(self.wash)
        canvas.rect(x, y, left + pw + right, top + ph + bot,
                    fill=wash_col, stroke="none")

        if self.y_label:
            self._draw_rotated_label(canvas, theme,
                                     x + theme.unit * 0.6,
                                     py + ph / 2)

        (group_offset, panel_w, inter_gap, bar_width,
         intra_gap, panel_pad) = self._group_geometry(theme, pw)
        group_x0 = px + group_offset

        if self.show_axis:
            self._draw_axis(canvas, theme, px, py, pw, ph, ymax)

        head = canvas.define_arrow_marker(
            color=theme.color_of(self.delta_color),
            stroke_width=theme.line,
            arrow_size=5.5, name_hint="gbc_delta")

        for i, g in enumerate(self.groups):
            px0 = group_x0 + i * (panel_w + inter_gap)
            base_y = py + ph
            self._draw_group(canvas, theme, g, px0, py, panel_w, base_y,
                             ph, ymax, head, y, i, bar_width,
                             intra_gap, panel_pad)

    # --- per-group ------------------------------------------------------

    def _draw_group(self, canvas: Canvas, theme: Theme,
                    g: BarGroup, px0: float, py: float,
                    panel_w: float, base_y: float, ph: float,
                    ymax: float, head: str, y_outer: float,
                    group_index: int, bar_width: float,
                    intra_gap: float, panel_pad: float) -> None:
        if self.show_cards:
            canvas.rect(px0, py, panel_w, ph,
                        fill=theme.color_of(self.card_fill),
                        stroke=theme.color_of(self.card_stroke),
                        stroke_width=theme.hairline, rx=2.0)

        if self.show_titles and self.show_cards:
            canvas.text(px0 + panel_w / 2,
                        y_outer + theme.size_px("panel") + theme.unit * 0.3,
                        g.title,
                        size=theme.size_px("panel"),
                        fill=theme.color_of(self.title_color),
                        anchor="middle", weight="700")

        # Bars.
        bar_xs = []
        bar_heights = []
        value_ys = []
        for j, (v, s) in enumerate(zip(g.values, self.series)):
            bx = px0 + panel_pad + j * (bar_width + intra_gap)
            bh = (v / ymax) * ph
            by = base_y - bh
            group_color = g.color if len(g.values) == 1 else None
            fill = theme.color_of(group_color or s.color)
            stroke_spec = s.stroke if s.stroke is not None else (group_color or s.color)
            stroke = theme.color_of(stroke_spec)
            canvas.rect(bx, by, bar_width, bh,
                        fill=fill, stroke=stroke,
                        stroke_width=theme.hairline)
            bar_xs.append(bx + bar_width / 2)
            bar_heights.append((by, bh))
            if self.show_values:
                text_h = theme.text_height("label")
                if not self.show_cards or bh < text_h * 1.8:
                    value_y = by - theme.unit * 0.45
                    value_color = theme.color_of(g.value_color or "text")
                else:
                    value_y = by + text_h
                    value_color = theme.color_of(
                        g.value_color) if g.value_color else self._value_color(
                            s, fill, theme)
                canvas.text(
                    bar_xs[-1], value_y, self.value_formatter(v),
                    size=theme.size_px("label"), fill=value_color,
                    anchor="middle", weight="700",
                )
                value_ys.append(value_y)

        if self.show_titles and not self.show_cards:
            lines = g.title.splitlines() or [g.title]
            title_y = base_y + theme.text_height("tiny")
            for line_index, line in enumerate(lines):
                canvas.text(
                    px0 + panel_w / 2,
                    title_y + line_index * theme.text_height("tiny"),
                    line,
                    size=theme.size_px("tiny"),
                    fill=theme.color_of(self.title_color),
                    anchor="middle",
                )

        # Target line at the configured target (default = max value).
        target_v = g.target if g.target is not None else max(g.values)
        target_y = base_y - (target_v / ymax) * ph
        if self.show_target_line:
            canvas.line(px0 + panel_pad * 0.4, target_y,
                        px0 + panel_w - panel_pad * 0.4, target_y,
                        stroke=theme.color_of(self.target_color),
                        stroke_width=theme.hairline,
                        dasharray="5,3")

        # Delta arrow between two series.
        if self.show_delta_arrow and len(g.values) >= 2:
            try:
                src = self._series_index(self.delta_from, len(g.values))
                dst = self._series_index(self.delta_to,   len(g.values))
            except IndexError:
                src = dst = None
            if src is not None and dst is not None and src != dst:
                x_arrow = bar_xs[src]
                y_src, _ = bar_heights[src]
                y_dst, _ = bar_heights[dst]
                canvas.line(x_arrow, y_src, x_arrow, y_dst + 1.2,
                            stroke=theme.color_of(self.delta_color),
                            stroke_width=theme.line,
                            marker_end=head)

        # Per-group annotation (free-form label).
        if g.annotation:
            # Centred horizontally over the whole bar block.  In a flat
            # chart the annotation forms a stack above the value label;
            # card comparisons retain the historical target-line caption.
            centre_x = (bar_xs[0] + bar_xs[-1]) / 2 if bar_xs else px0
            lines = g.annotation.splitlines()
            line_h = theme.text_height("small")
            if not self.show_cards and value_ys:
                last_y = (
                    min(value_ys)
                    - theme.text_height("label")
                    - theme.unit * 0.55
                )
            else:
                last_y = target_y - theme.unit * 0.7
            start_y = last_y - max(0, len(lines) - 1) * line_h
            for line_index, line in enumerate(lines):
                canvas.text(
                    centre_x,
                    start_y + line_index * line_h,
                    line,
                    size=theme.size_px("small"),
                    fill=theme.color_of(self.annotation_color),
                    anchor="middle",
                    weight="700",
                )

    # --- helpers --------------------------------------------------------

    @staticmethod
    def _series_index(i: int, n: int) -> int:
        if i < 0:
            i += n
        if not (0 <= i < n):
            raise IndexError(i)
        return i

    def _draw_axis(self, canvas: Canvas, theme: Theme,
                   px: float, py: float, pw: float,
                   ph: float, ymax: float) -> None:
        muted = theme.color_of(self.axis_color)
        canvas.line(px, py, px, py + ph,
                    stroke=muted, stroke_width=theme.hairline)
        canvas.line(px, py + ph, px + pw, py + ph,
                    stroke=muted, stroke_width=theme.hairline)
        # Include the last tick inclusively.
        k = 0
        while k * self.y_step <= ymax + 1e-6:
            v = k * self.y_step
            ty = py + ph - (v / ymax) * ph
            if self.grid and v > 0:
                canvas.line(px, ty, px + pw, ty,
                            stroke=theme.color_of("grid"),
                            stroke_width=theme.hairline,
                            opacity=0.18)
            canvas.line(px - 3, ty, px, ty,
                        stroke=muted, stroke_width=theme.hairline)
            canvas.text(px - 5, ty + theme.size_px("tiny") * 0.35,
                        f"{int(v)}" if v == int(v) else f"{v:g}",
                        size=theme.size_px("tiny"),
                        fill=muted, anchor="end")
            k += 1

    def _draw_rotated_label(self, canvas: Canvas, theme: Theme,
                            lx: float, ly: float) -> None:
        """Emit a vertically-rotated label anchored at ``(lx, ly)``."""
        ink = theme.color_of(self.title_color)
        canvas._body.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" '
            f'font-size="{theme.size_px("small"):.2f}" fill="{ink}" '
            f'font-weight="600" text-anchor="middle" '
            f'font-family="{theme.font_family}" '
            f'transform="rotate(-90 {lx:.2f} {ly:.2f})">'
            f'{self.y_label}</text>'
        )

    def _value_color(self, s: BarSeries, bar_fill: str,
                     theme: Theme) -> str:
        if s.value_color is not None:
            return theme.color_of(s.value_color)
        # Pick black / white by simple luminance heuristic on the fill.
        hex_ = bar_fill.lstrip("#")
        if len(hex_) != 6:
            return theme.color_of("text")
        r, g, b = (int(hex_[i:i+2], 16) for i in (0, 2, 4))
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return "#ffffff" if lum < 0.55 else theme.color_of("text")


# ---------------------------------------------------------------------------
# Default formatter
# ---------------------------------------------------------------------------

def _default_fmt(v: float) -> str:
    """Trim trailing zeros from a bar-value label.

    ``16.70 -> "16.7"``, ``20.0 -> "20"``, ``0.0 -> "0"``.  Authors that
    need a different look (``f"{v:.2f}"`` or a currency formatter) can
    pass ``value_formatter=...`` to :class:`GroupedBarChart`.
    """
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s or "0"
