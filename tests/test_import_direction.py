"""Guard the sciviz package import direction.

Lower layers must not depend on higher layers. The rules encoded here
mirror the architecture note in ``.cursor/rules/sciviz-workflow.mdc``:

* ``sciviz.core``       --  must not import from any other sciviz package.
* ``sciviz.layout``     --  may import ``core`` only.
* ``sciviz.elements``   --  may import ``core`` and ``layout``.
* ``sciviz.palette``    --  must not import from ``sciviz`` at all.

Testing this keeps accidental cycles and upward references from creeping
in as we split packages further.
"""
from __future__ import annotations

import ast
import pathlib
import pytest


SCIVIZ_ROOT = pathlib.Path(__file__).resolve().parents[1] / "sciviz"


def _module_imports(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Resolve relative imports against the containing package.
            if node.level:
                parts = path.relative_to(SCIVIZ_ROOT.parent).with_suffix("").parts
                # parts begins with "sciviz"; strip the file name to get the
                # package, then drop `level-1` segments.
                pkg = parts[:-1]
                if node.level > 1:
                    pkg = pkg[: -(node.level - 1)]
                out.append(".".join([*pkg, node.module]))
            else:
                out.append(node.module)
        elif isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
    return out


def _all_py(package: str) -> list[pathlib.Path]:
    return list((SCIVIZ_ROOT / package).rglob("*.py"))


def _imports_in(package: str) -> set[str]:
    mods: set[str] = set()
    for path in _all_py(package):
        for mod in _module_imports(path):
            if mod.startswith("sciviz."):
                mods.add(mod)
    return mods


@pytest.mark.parametrize(
    "package, forbidden_prefixes",
    [
        # core must not reach sideways or upward at all.
        (
            "core",
            [
                "sciviz.layout",
                "sciviz.elements",
                "sciviz.composition",
                "sciviz.grid",
                "sciviz.charts",
                "sciviz.primitives",
                "sciviz.specialized",
                "sciviz.structures",
                "sciviz.graphs",
                "sciviz.connect",
                "sciviz.routing",
                "sciviz.auto",
                "sciviz.math",
                "sciviz.diagram",
            ],
        ),
        # layout may use core but not higher layers.
        (
            "layout",
            [
                "sciviz.elements",
                "sciviz.composition",
                "sciviz.grid",
                "sciviz.charts",
                "sciviz.primitives",
                "sciviz.specialized",
                "sciviz.structures",
                "sciviz.graphs",
                "sciviz.connect",
                "sciviz.diagram",
            ],
        ),
        # palette must not import anything from sciviz (it is a leaf).
        (
            "palette",
            [
                "sciviz.core",
                "sciviz.layout",
                "sciviz.elements",
                "sciviz.composition",
                "sciviz.grid",
                "sciviz.charts",
                "sciviz.primitives",
                "sciviz.specialized",
                "sciviz.structures",
                "sciviz.graphs",
                "sciviz.connect",
                "sciviz.routing",
                "sciviz.auto",
                "sciviz.math",
                "sciviz.diagram",
            ],
        ),
    ],
)
def test_import_direction(package: str, forbidden_prefixes: list[str]):
    imports = _imports_in(package)
    violations = sorted(
        m for m in imports
        if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)
    )
    assert not violations, (
        f"sciviz.{package} imports disallowed higher-level packages: "
        f"{violations}"
    )
