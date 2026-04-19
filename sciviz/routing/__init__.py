"""Backwards-compatible shim: re-exports :mod:`sciviz.auto.router`.

Authors should not import from this module directly; the canonical
location is :mod:`sciviz.auto.router`. This shim keeps internal
imports (``from .. import routing as _rt``) functional during the
reorganization.
"""

from ..auto.router import *  # noqa: F401, F403
from ..auto import router as _router  # noqa: F401

# Intra-package code uses ``routing.plan_path``, ``routing.Endpoint`` etc.
# as attribute access. Expose every public name from the underlying
# module on this package.
from ..auto.router import (  # noqa: F401
    Box, Endpoint, Plan, CrossPolicy,
    plan_path,
    render_orthogonal, render_curved,
    arrow_marker,
)
