"""Image: raster or vector image embedded inline inside the SVG.

A single constructor handles the three common cases:

* PNG / JPEG on disk -- read, base64-encoded, MIME type sniffed from the
  first few bytes, intrinsic size (in px) extracted from the header so
  the author doesn't have to supply ``width``/``height``.
* SVG on disk -- read, base64-encoded; intrinsic size taken from
  ``viewBox`` (falling back to ``width``/``height`` attributes).
* Bytes -- same handling as a path, but the author supplies the bytes
  directly.

Authors can always override ``width=`` and/or ``height=`` to force a
size; if only one is given the other is computed from the intrinsic
aspect so the image doesn't squish.
"""

from __future__ import annotations

import base64
import os
import re
import struct
from pathlib import Path
from typing import Optional, Tuple, Union

from ..core import BBox, Canvas, Element, Theme


def _sniff_png_size(data: bytes) -> Optional[Tuple[int, int]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    # IHDR chunk starts at byte 8, length prefix (4) + type (4) then width/height.
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def _sniff_jpeg_size(data: bytes) -> Optional[Tuple[int, int]]:
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    n = len(data)
    while i < n - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        # Standalone markers (no length).
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > n:
            return None
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            # SOF marker: [len(2)][precision(1)][h(2)][w(2)]...
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            return int(w), int(h)
        i += seg_len
    return None


_SVG_VIEWBOX = re.compile(r'viewBox\s*=\s*"([^"]+)"')
_SVG_WIDTH = re.compile(r'\bwidth\s*=\s*"([0-9.]+)')
_SVG_HEIGHT = re.compile(r'\bheight\s*=\s*"([0-9.]+)')


def _sniff_svg_size(data: bytes) -> Optional[Tuple[float, float]]:
    try:
        head = data[:4096].decode("utf-8", errors="ignore")
    except Exception:
        return None
    m = _SVG_VIEWBOX.search(head)
    if m:
        parts = m.group(1).replace(",", " ").split()
        if len(parts) == 4:
            try:
                _, _, w, h = (float(p) for p in parts)
                return w, h
            except ValueError:
                pass
    mw = _SVG_WIDTH.search(head)
    mh = _SVG_HEIGHT.search(head)
    if mw and mh:
        try:
            return float(mw.group(1)), float(mh.group(1))
        except ValueError:
            return None
    return None


def _mime_for(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:200].lstrip().startswith(b"<") and b"<svg" in data[:4096]:
        return "image/svg+xml"
    # Fallback: let the renderer figure it out.
    return "application/octet-stream"


class Image(Element):
    """A raster or vector image embedded inline in the output SVG.

    Parameters
    ----------
    source : str, pathlib.Path, or bytes
        Path to an image file on disk, or raw bytes.
    width, height : float, optional
        Force rendered size. If only one is given, the other is inferred
        from the intrinsic aspect ratio. If neither is given, intrinsic
        pixel dimensions are used (PNG/JPEG/SVG all sniffed).
    fit : str
        How the image fills its bbox when both width and height are
        given and the aspect doesn't match: ``"contain"`` (default,
        letterbox) or ``"cover"`` (crop / fill, SVG ``slice``).
    opacity : float
    """

    def __init__(self, source: Union[str, "os.PathLike[str]", bytes], *,
                 width: Optional[float] = None,
                 height: Optional[float] = None,
                 fit: str = "contain",
                 opacity: float = 1.0):
        if isinstance(source, (str, os.PathLike)):
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"Image source not found: {path}")
            data = path.read_bytes()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            raise TypeError(
                f"Image source must be str, Path, or bytes; got {type(source)}")

        self._data = data
        self._mime = _mime_for(data)
        intrinsic = self._intrinsic_size()
        if intrinsic is None:
            if width is None or height is None:
                raise ValueError(
                    "Could not infer intrinsic size for this image; "
                    "please pass both width= and height=.")
            intrinsic = (width, height)
        iw, ih = intrinsic
        if width is None and height is None:
            w, h = iw, ih
        elif width is None:
            w = height * (iw / ih) if ih else height
            h = height
        elif height is None:
            h = width * (ih / iw) if iw else width
            w = width
        else:
            w, h = width, height
        self._w = float(w)
        self._h = float(h)
        if fit not in ("contain", "cover"):
            raise ValueError("fit must be 'contain' or 'cover'")
        self._fit = fit
        self._opacity = float(opacity)
        self._data_uri = (
            f"data:{self._mime};base64,"
            + base64.b64encode(self._data).decode("ascii")
        )

    def _intrinsic_size(self) -> Optional[Tuple[float, float]]:
        if self._mime == "image/png":
            size = _sniff_png_size(self._data)
            return (float(size[0]), float(size[1])) if size else None
        if self._mime == "image/jpeg":
            size = _sniff_jpeg_size(self._data)
            return (float(size[0]), float(size[1])) if size else None
        if self._mime == "image/svg+xml":
            return _sniff_svg_size(self._data)
        return None

    def measure(self, theme: Theme) -> BBox:
        return BBox(self._w, self._h)

    def render(self, canvas: Canvas, x: float, y: float, theme: Theme) -> None:
        par = "xMidYMid meet" if self._fit == "contain" else "xMidYMid slice"
        canvas.image(
            x, y, self._w, self._h,
            href=self._data_uri,
            preserve_aspect_ratio=par,
            opacity=self._opacity,
        )
