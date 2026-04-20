"""Curated Lucide icon subset, bundled as SVG path data.

Source: `lucide.dev <https://lucide.dev>`_ (MIT-licensed).

Every icon in this module is a stroke-only SVG drawn on a 24x24 viewBox
with ``fill="none"`` and ``stroke-linecap="round" stroke-linejoin="round"``.
:class:`sciviz.Icon` emits a nested ``<svg>`` with this viewBox, so the
icon scales to any requested size while preserving stroke weight
perception.

The selection targets the vocabulary of ML / systems / science papers:

* Media/IO: ``image``, ``video``, ``file-text``, ``database``,
  ``download``, ``upload``.
* Hardware: ``cpu``, ``memory-stick``, ``server``, ``hard-drive``.
* Geometry: ``box``, ``cube``, ``circle``, ``square``, ``triangle``,
  ``hexagon``.
* Flow: ``arrow-right``, ``arrow-down``, ``refresh-cw``, ``play``,
  ``pause``, ``git-branch``, ``shuffle``.
* People/entities: ``user``, ``users``, ``bot``, ``brain``.
* Abstract: ``zap`` (energy), ``flame`` (heat), ``lock``, ``unlock``,
  ``eye``, ``key``, ``shield``.
* Decisions: ``check``, ``x``, ``help-circle``, ``info``, ``alert-triangle``.
* Math: ``sigma``, ``pi``, ``function-square``.
* Layout: ``layers``, ``grid``, ``list``, ``table``.
* Misc: ``search``, ``filter``, ``settings``, ``clock``.

Add new icons by pasting the inner path(s) from the Lucide SVG, split
into a list (one entry per ``<path d="...">``).
"""

from __future__ import annotations

from typing import Dict, List


LUCIDE_VIEWBOX = (0.0, 0.0, 24.0, 24.0)


LUCIDE_ICONS: Dict[str, List[str]] = {
    # --- media / io ---
    "image": [
        "M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z",
        "M9 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
        "m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21",
    ],
    "video": [
        "m22 8-6 4 6 4V8Z",
        "M14 6H4a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2z",
    ],
    "file-text": [
        "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z",
        "M14 2v4a2 2 0 0 0 2 2h4",
        "M10 9H8",
        "M16 13H8",
        "M16 17H8",
    ],
    "database": [
        "M4 6a8 3 0 1 0 16 0A8 3 0 1 0 4 6",
        "M4 6v6a8 3 0 0 0 16 0V6",
        "M4 12v6a8 3 0 0 0 16 0v-6",
    ],
    "download": [
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
        "M7 10l5 5 5-5",
        "M12 15V3",
    ],
    "upload": [
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
        "M17 8l-5-5-5 5",
        "M12 3v12",
    ],

    # --- hardware ---
    "cpu": [
        "M4 4h16v16H4z",
        "M9 9h6v6H9z",
        "M9 2v2",
        "M15 2v2",
        "M9 20v2",
        "M15 20v2",
        "M2 9h2",
        "M2 15h2",
        "M20 9h2",
        "M20 15h2",
    ],
    "memory-stick": [
        "M6 19v-3",
        "M10 19v-3",
        "M14 19v-3",
        "M18 19v-3",
        "M8 11V9",
        "M16 11V9",
        "M12 11V9",
        "M2 15h20",
        "M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1.1a2 2 0 0 0 0 3.837V17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-5.1a2 2 0 0 0 0-3.837Z",
    ],
    "server": [
        "M2 3h20v5H2z",
        "M2 10h20v5H2z",
        "M6 6h.01",
        "M6 13h.01",
        "M2 17h20v5H2z",
        "M6 20h.01",
    ],
    "hard-drive": [
        "M22 12H2",
        "M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
        "M6 16h.01",
        "M10 16h.01",
    ],

    # --- geometry ---
    "box": [
        "m21 16-9 5-9-5V8l9-5 9 5Z",
        "m7.5 4.27 9 5.15",
        "M3.3 7 12 12l8.7-5",
        "M12 22V12",
    ],
    "cube": [
        "M12 2 3 7v10l9 5 9-5V7l-9-5z",
        "M3.3 7 12 12l8.7-5",
        "M12 22V12",
    ],
    "circle": [
        "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z",
    ],
    "square": [
        "M4 4h16v16H4z",
    ],
    "triangle": [
        "M21.73 18 13.73 3.99a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z",
    ],
    "hexagon": [
        "M21 16.2V7.8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 7.8v8.4a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16.2z",
    ],

    # --- flow ---
    "arrow-right": [
        "M5 12h14",
        "m12 5 7 7-7 7",
    ],
    "arrow-down": [
        "M12 5v14",
        "m19 12-7 7-7-7",
    ],
    "arrow-up": [
        "M12 19V5",
        "m5 12 7-7 7 7",
    ],
    "arrow-left": [
        "M19 12H5",
        "m12 19-7-7 7-7",
    ],
    "refresh-cw": [
        "M3 12a9 9 0 0 1 15-6.74L21 8",
        "M21 3v5h-5",
        "M21 12a9 9 0 0 1-15 6.74L3 16",
        "M3 21v-5h5",
    ],
    "play": [
        "M6 3l14 9-14 9z",
    ],
    "pause": [
        "M6 4h4v16H6z",
        "M14 4h4v16h-4z",
    ],
    "git-branch": [
        "M6 3v12",
        "M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        "M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        "M15 6a9 9 0 0 0-9 9",
    ],
    "shuffle": [
        "m18 14 4 4-4 4",
        "m18 2 4 4-4 4",
        "M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22",
        "M2 6h1.972a4 4 0 0 1 3.6 2.2",
        "M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45",
    ],

    # --- people / entities ---
    "user": [
        "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
        "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    ],
    "users": [
        "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2",
        "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
        "M23 21v-2a4 4 0 0 0-3-3.87",
        "M16 3.13a4 4 0 0 1 0 7.75",
    ],
    "bot": [
        "M12 8V4H8",
        "M4 12h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z",
        "M2 14h2",
        "M20 14h2",
        "M15 13v2",
        "M9 13v2",
    ],
    "brain": [
        "M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z",
        "M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z",
    ],

    # --- abstract ---
    "zap": [
        "M13 2 3 14h9l-1 8 10-12h-9l1-8z",
    ],
    "flame": [
        "M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z",
    ],
    "lock": [
        "M5 11h14v11H5z",
        "M7 11V7a5 5 0 0 1 10 0v4",
    ],
    "unlock": [
        "M5 11h14v11H5z",
        "M7 11V7a5 5 0 0 1 9.9-1",
    ],
    "eye": [
        "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    ],
    "key": [
        "M15.5 7.5a5 5 0 1 0-6.93 6.93L2 21l2 2 1-1 1 1 1-1 1 1 2.57-2.57A5 5 0 0 0 15.5 7.5z",
        "M14 7h.01",
    ],
    "shield": [
        "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    ],

    # --- decisions ---
    "check": [
        "M20 6 9 17l-5-5",
    ],
    "x": [
        "M18 6 6 18",
        "M6 6l12 12",
    ],
    "help-circle": [
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
        "M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3",
        "M12 17h.01",
    ],
    "info": [
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
        "M12 16v-4",
        "M12 8h.01",
    ],
    "alert-triangle": [
        "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z",
        "M12 9v4",
        "M12 17h.01",
    ],
    "circle-dot": [
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
        "M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
    ],

    # --- math ---
    "sigma": [
        "M18 7V4H6l6 8-6 8h12v-3",
    ],
    "pi": [
        "M9 4v16",
        "M15 4v16",
        "M3 4h18",
    ],
    "function-square": [
        "M4 4h16v16H4z",
        "M9 17c2 0 2-8 4-8h2",
        "M7 13h5",
    ],
    "percent": [
        "m19 5-14 14",
        "M6.5 9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
        "M17.5 20a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
    ],

    # --- layout ---
    "layers": [
        "m12 2 9 4-9 4-9-4 9-4z",
        "m3 12 9 4 9-4",
        "m3 17 9 4 9-4",
    ],
    "grid": [
        "M4 4h7v7H4z",
        "M13 4h7v7h-7z",
        "M4 13h7v7H4z",
        "M13 13h7v7h-7z",
    ],
    "list": [
        "M8 6h13",
        "M8 12h13",
        "M8 18h13",
        "M3 6h.01",
        "M3 12h.01",
        "M3 18h.01",
    ],
    "table": [
        "M12 3v18",
        "M3 9h18",
        "M3 15h18",
        "M3 3h18v18H3z",
    ],

    # --- misc ---
    "search": [
        "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z",
        "m21 21-4.3-4.3",
    ],
    "filter": [
        "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
    ],
    "settings": [
        "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    ],
    "clock": [
        "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z",
        "M12 6v6l4 2",
    ],
    "star": [
        "m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
    ],
    "heart": [
        "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
    ],
    # --- symbol glyphs ---
    "hash": [
        "M4 9h16",
        "M4 15h16",
        "M10 3 8 21",
        "M16 3l-2 18",
    ],
    "type": [
        "M4 7V4h16v3",
        "M9 20h6",
        "M12 4v16",
    ],
    "link": [
        "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71",
        "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
    ],
    "boxes": [
        "M2.97 12.92 2 6l10-4 10 4-.97 6.92a4 4 0 0 1-2.44 3.16L12 20l-6.59-3.92a4 4 0 0 1-2.44-3.16z",
        "M2 6 12 9.5 22 6",
        "M12 9.5V20",
    ],
    "scan": [
        "M3 7V5a2 2 0 0 1 2-2h2",
        "M17 3h2a2 2 0 0 1 2 2v2",
        "M21 17v2a2 2 0 0 1-2 2h-2",
        "M7 21H5a2 2 0 0 1-2-2v-2",
        "M7 12h10",
    ],
    "mountain": [
        "m8 3 4 8 5-5 5 15H2L8 3z",
    ],
    # --- figure-specific glyphs ---
    # Slab-serif capital T used as a "text" glyph inside tiles.
    "serif-t": [
        "M4 6h16",
        "M4 4v4",
        "M20 4v4",
        "M12 6v14",
        "M8 20h8",
    ],
    # Two offset rounded frames (back + front) for "stacked windows".
    "frames-stacked": [
        "M9 4h11v11",
        "M4 9h11v11H4z",
    ],
    # Filled mask-blob: closed smooth outline, intended to be rendered
    # with fill="match" so the whole shape is a solid coloured patch.
    "blob": [
        "M12 4c3.2 0 6 1.8 7 4.5.8 2.3-.3 5-2.3 6.7-2 1.7-5 2.6-7.5 1.8-2.5-.8-4.7-3.1-5-5.7-.3-2.6 1.8-5.3 4.3-6.4A7.7 7.7 0 0 1 12 4z",
    ],
    # Three horizontally-spaced filled ovals, drifting to the right.
    "ovals-stack": [
        "M6 12c0-1.7 1.1-3 2.5-3s2.5 1.3 2.5 3-1.1 3-2.5 3S6 13.7 6 12z",
        "M10.5 12c0-1.7 1.1-3 2.5-3s2.5 1.3 2.5 3-1.1 3-2.5 3-2.5-1.3-2.5-3z",
        "M15 12c0-1.7 1.1-3 2.5-3s2.5 1.3 2.5 3-1.1 3-2.5 3-2.5-1.3-2.5-3z",
    ],
    # Two-peak mountain with a baseline underline.
    "peaks": [
        "M3 18 8 8l3 5 3-7 7 12Z",
        "M3 20h18",
    ],
}
