"""Backend for the ``sciviz-debug`` console script.

Identical behaviour to ``scripts/sciviz_debug.py`` but importable via
``sciviz._cli.debug:main``, which is what we register in
``pyproject.toml``.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
from typing import Optional

import sciviz


def _load_script(path: pathlib.Path) -> dict:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.__dict__


def _find_diagram(ns: dict, name: Optional[str]) -> sciviz.Diagram:
    if name is not None:
        if name not in ns:
            raise KeyError(f"{name!r} not found in the script's globals")
        value = ns[name]
        if not isinstance(value, sciviz.Diagram):
            raise TypeError(f"{name!r} is {type(value).__name__}, not Diagram")
        return value
    if "DIAGRAM" in ns and isinstance(ns["DIAGRAM"], sciviz.Diagram):
        return ns["DIAGRAM"]
    for value in ns.values():
        if isinstance(value, sciviz.Diagram):
            return value
    raise LookupError(
        "No Diagram instance found in the script. "
        "Either bind one to DIAGRAM = ... or pass --name NAME."
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sciviz-debug",
        description="Render an interactive HTML debug page for a sciviz Diagram.",
    )
    parser.add_argument("script", type=pathlib.Path,
                        help="Python file that constructs a Diagram.")
    parser.add_argument("-o", "--output", type=pathlib.Path, default=None,
                        help="Destination .html file "
                             "(default: <script>.debug.html)")
    parser.add_argument("--name", type=str, default=None,
                        help="Variable name of the Diagram in the script "
                             "(default: auto-detect)")
    args = parser.parse_args(argv)

    script: pathlib.Path = args.script.resolve()
    if not script.exists():
        parser.error(f"{script} does not exist")

    sys.path.insert(0, str(script.parent))
    ns = _load_script(script)
    diagram = _find_diagram(ns, args.name)

    out = args.output or script.with_suffix(".debug.html")
    out = out.resolve()
    diagram.save_debug(out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
