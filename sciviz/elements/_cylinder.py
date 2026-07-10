"""Cylinder: semantic storage/cache element for architecture diagrams."""

from __future__ import annotations

from ..core import BBox, Canvas, Element, Theme
from ._obstacles import _register_implicit_obstacle
from ._text import Text, TextBlock


class Cylinder(Element):
    """A compact database/cache cylinder with measured label content.

    ``size`` is semantic; labels may be plain/multiline strings or any
    element (including :class:`~sciviz.Math`). The silhouette grows for its
    content, so authors never specify width, height, or ellipse depth.
    """

    _SIZE_UNITS = {
        "sm": (9.0, 5.0),
        "md": (12.0, 6.5),
        "lg": (15.0, 8.0),
    }

    # Database/storage silhouettes become visually ambiguous when a long
    # label makes them almost flat. Keep enough body depth for the top ellipse
    # and label hierarchy without asking authors for width/height pairs.
    _MAX_ASPECT = 1.7

    def __init__(self, label: str | Element, *, size: str = "md",
                 fill="bg_subtle", stroke="border_strong",
                 text_color="text", text_size="small"):
        if size not in self._SIZE_UNITS:
            allowed = ", ".join(self._SIZE_UNITS)
            raise ValueError(f"Cylinder.size must be one of {allowed}")
        if isinstance(label, Element):
            self.label = label
        elif "\n" in str(label):
            self.label = TextBlock(
                str(label), size=text_size, color=text_color,
                align="center", line_spacing=1.1,
            )
        else:
            self.label = Text(
                str(label), size=text_size, color=text_color,
                align="center", weight="600",
            )
        self.size = size
        self.fill = fill
        self.stroke = stroke
        self._min_w = 0.0
        self._min_h = 0.0

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self._min_w = max(self._min_w, float(min_w))
        self._min_h = max(self._min_h, float(min_h))

    def _geometry(self, theme: Theme):
        label = self.label.measure(theme)
        min_w_u, min_h_u = self._SIZE_UNITS[self.size]
        pad_x = theme.unit * 1.1
        pad_y = theme.unit * 0.7
        w = max(theme.unit * min_w_u, label.w + 2 * pad_x, self._min_w)
        h = max(
            theme.unit * min_h_u,
            label.h + 2 * pad_y,
            w / self._MAX_ASPECT,
            self._min_h,
        )
        cap_h = min(theme.unit * 2.2, h * 0.30)
        return label, w, h, cap_h

    def measure(self, theme: Theme) -> BBox:
        _label, w, h, _cap_h = self._geometry(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        label, w, h, cap_h = self._geometry(theme)
        fill = theme.paint_of(self.fill)
        stroke = theme.paint_of(self.stroke)
        mid_top = y + cap_h / 2
        mid_bottom = y + h - cap_h / 2
        body = (
            f"M {x:.3f},{mid_top:.3f} "
            f"C {x:.3f},{y:.3f} {x + w:.3f},{y:.3f} "
            f"{x + w:.3f},{mid_top:.3f} "
            f"L {x + w:.3f},{mid_bottom:.3f} "
            f"C {x + w:.3f},{y + h:.3f} {x:.3f},{y + h:.3f} "
            f"{x:.3f},{mid_bottom:.3f} Z"
        )
        top = (
            f"M {x:.3f},{mid_top:.3f} "
            f"C {x:.3f},{y:.3f} {x + w:.3f},{y:.3f} "
            f"{x + w:.3f},{mid_top:.3f} "
            f"C {x + w:.3f},{y + cap_h:.3f} {x:.3f},{y + cap_h:.3f} "
            f"{x:.3f},{mid_top:.3f}"
        )
        canvas.path(
            body, fill=fill, stroke=stroke,
            stroke_width=theme.hairline,
            ink_bbox=(x, y, x + w, y + h),
        )
        canvas.path(
            top, fill=fill, stroke=stroke,
            stroke_width=theme.hairline,
            ink_bbox=(x, y, x + w, y + cap_h),
        )
        _register_implicit_obstacle(x, y, w, h)
        self.label.render(
            canvas,
            x + (w - label.w) / 2,
            y + (h - label.h) / 2 + cap_h * 0.12,
            theme,
        )
