"""Scoped memo for ``Element.measure`` / ``Element.content_bbox``.

Containers measure their children from ``measure``, ``content_bbox``
and their offset helpers, so an unmemoised tree re-measures each
subtree once per ancestor call and the cost multiplies with nesting
depth. Inside ``with measure_memo():`` every sciviz ``measure`` and
``content_bbox`` result is reused while nothing that could change it
has been written.

Soundness rules:

* Only inside the scope. :class:`~sciviz.Diagram` opens it around one
  fitter trial and one render; the cache dies when the scope exits, so
  author code and interactive mutation outside a render never see a
  memoised value.
* A global write epoch. Any attribute write that changes a value on an
  element that has already returned a measurement in the scope, and
  any call of a container mutator (``_bump_margin``,
  ``_apply_reflow``), bumps it.
  ``inflate_to`` bumps only through the attribute writes it makes: a
  floor it raises is a changed value, a floor already met writes
  nothing that changes. A result is stored only if the epoch did not
  move while it was computed, and reused only while the epoch is
  unchanged. Writes to elements not yet measured (a container built
  inside a ``measure``) cannot have influenced a stored result and do
  not bump.
* Measured elements are held (not just their ids) until the scope
  exits, so a container built later in the scope can never inherit a
  measured element's recycled ``id`` and have its constructor writes
  mistaken for layout writes.
* Keys carry the defining class, so a subclass ``measure`` that calls
  ``super().measure`` keeps two entries; entries hold the element and
  the theme themselves and hit only on identity, so a recycled ``id``
  never returns another object's size.

``SCIVIZ_MEASURE_MEMO=0`` disables the memo (for bisecting a suspected
stale size).
"""
from __future__ import annotations

import functools
import inspect
import os
from contextlib import contextmanager

from ._element import Element

_MEMOISED = ("measure", "content_bbox")
#: Mutators that may change a container in place (a margin dict, a
#: reflow choice), so every call bumps. ``inflate_to`` is not one: it
#: only raises floors through attribute writes, which the tracker sees.
_MUTATORS = ("_bump_margin", "_apply_reflow")
_PLAIN = (int, float, str, bool, type(None))
_MISSING = object()


class _State:
    depth = 0
    epoch = 0
    caches: list = []
    seen: dict = {}
    restore: list = []


def _bump() -> None:
    _State.epoch += 1


def _tracking_setattr(self, name, value):
    if _State.seen.get(id(self)) is self:
        old = getattr(self, "__dict__", {}).get(name, _MISSING)
        if old is not value and not (type(old) is type(value)
                                     and type(value) in _PLAIN
                                     and old == value):
            _State.epoch += 1
    object.__setattr__(self, name, value)


def _memoised(cls, name, fn):
    @functools.wraps(fn)
    def wrapper(self, theme, *args, **kwargs):
        if not _State.caches:
            return fn(self, theme, *args, **kwargs)
        if args or kwargs:
            result = fn(self, theme, *args, **kwargs)
            _State.seen[id(self)] = self
            return result
        cache = _State.caches[-1]
        key = (id(self), cls, name)
        epoch = _State.epoch
        hit = cache.get(key)
        if (hit is not None and hit[0] == epoch and hit[1] is self
                and hit[2] is theme):
            return hit[3]
        result = fn(self, theme)
        # Seen from its first result on: the writes an element makes
        # while producing that result (a fresh container settling its
        # own flags) precede every value anyone could have read from it.
        _State.seen[id(self)] = self
        if _State.epoch == epoch:
            cache[key] = (epoch, self, theme, result)
        return result
    return wrapper


def _mutating(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _bump()
        try:
            return fn(*args, **kwargs)
        finally:
            _bump()
    return wrapper


def _sciviz_classes():
    out, stack = [Element], [Element]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in out and sub.__module__.startswith("sciviz"):
                out.append(sub)
                stack.append(sub)
    return out


def _install() -> None:
    restore = _State.restore
    restore.append((Element, "__setattr__",
                    Element.__dict__.get("__setattr__", _MISSING)))
    Element.__setattr__ = _tracking_setattr
    for cls in _sciviz_classes():
        for name in _MEMOISED + _MUTATORS:
            fn = cls.__dict__.get(name)
            if not inspect.isfunction(fn):
                continue
            restore.append((cls, name, fn))
            setattr(cls, name, _memoised(cls, name, fn)
                    if name in _MEMOISED else _mutating(fn))


def _uninstall() -> None:
    for cls, name, fn in reversed(_State.restore):
        if fn is _MISSING:
            delattr(cls, name)
        else:
            setattr(cls, name, fn)
    _State.restore = []
    _State.seen = {}


def memo_value(owner, name, theme, compute):
    """``compute()``, reused for ``(owner, name, theme)`` inside the scope.

    For derived layout values that are not ``measure`` or
    ``content_bbox`` but are rebuilt from them on every call (a row's
    gap list, a shared gutter). The same soundness rules apply: the
    result is stored only if the write epoch did not move while it was
    computed, and reused only while it holds. ``name`` must carry
    anything the result depends on that an attribute write would not
    reveal (e.g. the size of a membership list). Outside the scope,
    ``compute()`` runs every time.
    """
    if not _State.caches:
        return compute()
    cache = _State.caches[-1]
    key = (id(owner), name)
    epoch = _State.epoch
    hit = cache.get(key)
    if (hit is not None and hit[0] == epoch and hit[1] is owner
            and hit[2] is theme):
        return hit[3]
    result = compute()
    if _State.epoch == epoch:
        cache[key] = (epoch, owner, theme, result)
    return result


def memo_enabled() -> bool:
    """Whether ``SCIVIZ_MEASURE_MEMO`` leaves the memo on (default)."""
    return os.environ.get("SCIVIZ_MEASURE_MEMO", "1") != "0"


@contextmanager
def measure_memo():
    """Memoise element measurement for the duration of the block.

    Re-entrant: a nested block gets its own cache (dropped when it
    exits), and the method wrappers are removed when the outermost
    block exits. A no-op when ``SCIVIZ_MEASURE_MEMO=0``.
    """
    if not memo_enabled():
        yield
        return
    if _State.depth == 0:
        _install()
    _State.depth += 1
    _State.caches.append({})
    try:
        yield
    finally:
        _State.caches.pop()
        _State.depth -= 1
        if _State.depth == 0:
            _uninstall()
