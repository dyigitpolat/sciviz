"""Convert an extracted @hugeicons/core-free-icons ESM tree into standalone SVGs.

Usage:
    npm pack @hugeicons/core-free-icons   # or download the tarball directly
    tar -xzf hugeicons-core-free-icons-*.tgz -C /tmp/hugeicons-pkg
    python3 convert_icons.py /tmp/hugeicons-pkg/package/dist/esm sciviz/_assets/hugeicons/icons

Reads dist/esm/*.js (React-array format: [["path", {d, stroke, ...}], ...]),
derives a kebab-case icon name from the PascalCase export name, and writes
one self-contained <svg> file per icon. Existing files for unchanged icons
are simply overwritten (idempotent); names not present in the new package
are left untouched -- diff `git status` after running to see what changed.
"""
from __future__ import annotations

import glob
import re
import sys


ATTR_JS_TO_SVG = {
    "strokeLinecap": "stroke-linecap",
    "strokeLinejoin": "stroke-linejoin",
    "strokeWidth": "stroke-width",
    "fillRule": "fill-rule",
    "clipRule": "clip-rule",
}
ATTR_ORDER = [
    "d", "cx", "cy", "r", "rx", "ry", "x", "y", "width", "height",
    "transform", "fill", "fill-rule", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "clip-rule", "opacity",
]

ENTRY_RE = re.compile(r'\[\s*"([a-zA-Z]+)"\s*,\s*\{([^}]*)\}\s*\]')
ATTR_RE = re.compile(r'(\w+):\s*"([^"]*)"')


def pascal_to_kebab(name: str) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '-', name)
    s = re.sub(r'(?<=[A-Za-z])(?=[0-9])', '-', s)
    return s.lower()


def parse_shapes(js_source: str) -> list[dict]:
    shapes = []
    for tag, body in ENTRY_RE.findall(js_source):
        attrs = {}
        for key, val in ATTR_RE.findall(body):
            if key == "key":
                continue
            attrs[ATTR_JS_TO_SVG.get(key, key)] = val
        shapes.append({"tag": tag, "attrs": attrs})
    return shapes


def shape_to_svg_element(shape: dict) -> str:
    attrs = shape["attrs"]
    ordered_keys = [k for k in ATTR_ORDER if k in attrs]
    ordered_keys += [k for k in attrs if k not in ATTR_ORDER]
    attr_str = " ".join(f'{k}="{attrs[k]}"' for k in ordered_keys)
    return f"<{shape['tag']} {attr_str}/>"


def icon_to_svg(shapes: list[dict]) -> str:
    inner = "".join(shape_to_svg_element(s) for s in shapes)
    return (
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" '
        f'xmlns="http://www.w3.org/2000/svg">{inner}</svg>\n'
    )


def main(src_dir: str, out_dir: str) -> None:
    files = sorted(f for f in glob.glob(f"{src_dir}/*.js") if not f.endswith(".js.map"))
    name_map: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    written = 0

    for path in files:
        export_name = path.rsplit("/", 1)[-1][: -len(".js")]
        if not export_name.endswith("Icon"):
            continue  # package infra files (index, loader.*, types, ...)
        kebab = pascal_to_kebab(export_name[: -len("Icon")])
        if not kebab:
            continue

        shapes = parse_shapes(open(path, encoding="utf-8").read())
        if not shapes:
            continue

        if kebab in name_map:
            collisions.setdefault(kebab, [name_map[kebab]]).append(export_name)
            continue
        name_map[kebab] = export_name

        with open(f"{out_dir}/{kebab}.svg", "w", encoding="utf-8") as fh:
            fh.write(icon_to_svg(shapes))
        written += 1

    print(f"files scanned: {len(files)}")
    print(f"svgs written: {written}")
    print(f"name collisions: {len(collisions)}")
    for k, v in list(collisions.items())[:10]:
        print(f"  {k}: {v}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
