"""Document: semantic folded-corner output artifact."""

from __future__ import annotations

from ..core import BBox, Canvas, Element, Theme
from ._obstacles import _register_implicit_obstacle
from ._text import Text, TextBlock


class Document(Element):
    """A measured portrait sheet with an automatically sized corner fold.

    ``Document`` represents a file/report/output artifact. Authors supply its
    semantic label and an optional size tier; the silhouette stays recognisably
    document-like even for very short labels and grows for mathematical or
    multiline content without authored width/height coordinates.
    """

    _SIZE_UNITS = {
        "sm": (7.0, 8.5),
        "md": (9.0, 11.0),
        "lg": (12.0, 14.0),
    }
    _MAX_WIDTH_HEIGHT = 0.82

    def __init__(self, label: str | Element, *, size: str = "md",
                 fill="bg_subtle", stroke="border_strong",
                 text_color="text", text_size="small"):
        if size not in self._SIZE_UNITS:
            allowed = ", ".join(self._SIZE_UNITS)
            raise ValueError(f"Document.size must be one of {allowed}")
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
        self.min_width = 0.0
        self.min_height = 0.0
        self.shape_key = "document"

    def inflate_to(self, min_w: float = 0.0, min_h: float = 0.0) -> None:
        self.min_width = max(self.min_width, float(min_w))
        self.min_height = max(self.min_height, float(min_h))

    def _geometry(self, theme: Theme):
        label = self.label.measure(theme)
        min_w_u, min_h_u = self._SIZE_UNITS[self.size]
        pad_x = theme.unit * 1.0
        pad_y = theme.unit * 1.0
        w = max(theme.unit * min_w_u, label.w + 2 * pad_x, self.min_width)
        h = max(
            theme.unit * min_h_u,
            label.h + 2 * pad_y,
            w / self._MAX_WIDTH_HEIGHT,
            self.min_height,
        )
        fold = min(theme.unit * 2.2, w * 0.25, h * 0.22)
        return label, w, h, fold

    def measure(self, theme: Theme) -> BBox:
        _label, w, h, _fold = self._geometry(theme)
        return BBox(w, h)

    def render(self, canvas: Canvas, x: float, y: float,
               theme: Theme) -> None:
        label, w, h, fold = self._geometry(theme)
        fill = theme.paint_of(self.fill)
        stroke = theme.paint_of(self.stroke)
        outline = (
            f"M {x:.3f},{y:.3f} "
            f"L {x + w - fold:.3f},{y:.3f} "
            f"L {x + w:.3f},{y + fold:.3f} "
            f"L {x + w:.3f},{y + h:.3f} "
            f"L {x:.3f},{y + h:.3f} Z"
        )
        crease = (
            f"M {x + w - fold:.3f},{y:.3f} "
            f"L {x + w - fold:.3f},{y + fold:.3f} "
            f"L {x + w:.3f},{y + fold:.3f}"
        )
        canvas.path(
            outline,
            fill=fill,
            stroke=stroke,
            stroke_width=theme.hairline,
            ink_bbox=(x, y, x + w, y + h),
        )
        canvas.path(
            crease,
            fill="none",
            stroke=stroke,
            stroke_width=theme.hairline,
            ink_bbox=(x + w - fold, y, x + w, y + fold),
        )
        _register_implicit_obstacle(x, y, w, h)
        # Centre on the usable sheet body, excluding the folded top-right
        # corner from the optical axis.
        usable_w = w - fold * 0.35
        self.label.render(
            canvas,
            x + (usable_w - label.w) / 2,
            y + (h - label.h) / 2 + fold * 0.12,
            theme,
        )
