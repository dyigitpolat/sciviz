"""Tests for :class:`sciviz.Image`."""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

import pytest

from sciviz import Canvas, DEFAULT_THEME, Image


def _make_png(w: int, h: int) -> bytes:
    """Minimal valid 1-channel PNG of dimensions ``(w, h)``."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data))
                + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    # Tiny 1-pixel row: for small test images the actual data is
    # irrelevant; we just need a valid IDAT / IEND pair.
    raw = b"\x00" * (1 + w) * h
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def test_image_from_bytes_infers_png_size():
    data = _make_png(80, 60)
    img = Image(data)
    b = img.measure(DEFAULT_THEME)
    assert (b.w, b.h) == (80.0, 60.0)


def test_image_width_only_preserves_aspect(tmp_path: Path):
    data = _make_png(100, 50)
    p = tmp_path / "img.png"
    p.write_bytes(data)
    img = Image(p, width=200)
    b = img.measure(DEFAULT_THEME)
    assert (b.w, b.h) == (200.0, 100.0)


def test_image_both_dimensions_override():
    data = _make_png(100, 50)
    img = Image(data, width=300, height=300)
    b = img.measure(DEFAULT_THEME)
    assert (b.w, b.h) == (300.0, 300.0)


def test_image_svg_source():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20"><rect width="40" height="20"/></svg>'
    img = Image(svg)
    b = img.measure(DEFAULT_THEME)
    assert (b.w, b.h) == (40.0, 20.0)


def test_image_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Image(tmp_path / "nope.png")


def test_image_render_emits_data_uri_image_tag():
    data = _make_png(10, 10)
    img = Image(data)
    canvas = Canvas()
    img.render(canvas, 2.0, 3.0, DEFAULT_THEME)
    svg = canvas.to_svg(40, 40)
    assert '<image ' in svg
    assert 'href="data:image/png;base64,' in svg
    assert 'x="2" y="3"' in svg
    assert 'width="10" height="10"' in svg


def test_image_fit_cover_uses_slice():
    data = _make_png(10, 10)
    img = Image(data, width=20, height=20, fit="cover")
    canvas = Canvas()
    img.render(canvas, 0, 0, DEFAULT_THEME)
    assert 'preserveAspectRatio="xMidYMid slice"' in canvas.to_svg(40, 40)
