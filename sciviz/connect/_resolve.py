"""Mode detection and endpoint normalisation for :class:`Connect`.

Three modes are distinguished *by the shape of the arguments alone*:

* ``inline``  -- both endpoints are ``None`` (standalone in-row arrow).
* ``bus``     -- at least one endpoint is a list and the total number of
                 endpoint names is >= 3.
* ``routed``  -- both endpoints are single names or Elements.

Authors never pass ``mode=``. Ambiguous shapes raise ``TypeError`` so the
error surfaces at construction time, not render time.
"""
from __future__ import annotations

import itertools
from typing import List, Sequence, Tuple, Union

from ..core import Element


Endpoint = Union[None, str, Element]

_auto_id = itertools.count()


def _is_element(x) -> bool:
    return isinstance(x, Element)


def _coerce_endpoint_list(e) -> List[Endpoint]:
    """Normalise one side into a list of endpoints (names or Elements)."""
    if e is None:
        return []
    if isinstance(e, (str, Element)):
        return [e]
    return list(e)


def classify(
    src, dst,
    *,
    direction: Union[str, None],
    length: Union[float, None],
) -> str:
    """Return ``"inline"`` / ``"routed"`` / ``"bus"``.

    Raises ``TypeError`` on ambiguous shapes.
    """
    src_list = _coerce_endpoint_list(src)
    dst_list = _coerce_endpoint_list(dst)

    # Inline: neither endpoint supplied. Author must provide `direction`.
    if not src_list and not dst_list:
        if direction is None:
            raise TypeError(
                "Connect() with no endpoints requires `direction=` "
                "(it is then an inline arrow inside a Row/Column)."
            )
        return "inline"

    # Partial endpoints are illegal.
    if not src_list or not dst_list:
        raise TypeError(
            "Connect() requires both `src` and `dst` to be set "
            "(for routed/bus mode), or neither (for inline mode). "
            f"Got src={src!r}, dst={dst!r}."
        )

    # Bus: any side has >= 2 endpoints, OR total endpoints >= 3.
    if len(src_list) >= 2 or len(dst_list) >= 2:
        return "bus"

    # Routed: both sides have exactly one endpoint.
    return "routed"


def synth_anchor_name(kind: str = "src") -> str:
    """Generate a unique anchor name for auto-wrapped Element endpoints."""
    return f"__connect_{next(_auto_id)}_{kind}"


def resolve_endpoints(
    src, dst, *, kind_prefix: str = "",
) -> Tuple[List[Endpoint], List[Endpoint]]:
    """Return normalised lists of endpoints and leave `Element` items as-is.

    The caller is responsible for wrapping any `Element` in an `Anchor` and
    substituting the generated name into the returned list in a follow-up
    pass (so the actual wrapping happens in the connector module, not here).
    """
    return _coerce_endpoint_list(src), _coerce_endpoint_list(dst)
