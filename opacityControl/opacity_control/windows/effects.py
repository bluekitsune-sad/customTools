"""Window opacity and click-through, kept consistent by one style owner.

Opacity and click-through both write the same extended window style, so they
must not fight over it. This class owns ``WS_EX_LAYERED`` and
``WS_EX_TRANSPARENT`` for every touched window and recomputes the desired
style from the active *features*, restoring the original style and alpha when
the last feature is turned off.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import WindowInfo
from . import api

_MANAGED_FLAGS = api.WS_EX_LAYERED | api.WS_EX_TRANSPARENT


@dataclass
class _Entry:
    hwnd: int
    original_style: int
    original_alpha: int | None
    opacity: int | None = None
    click_through: bool = False


class WindowsWindowEffects:
    """Implements WindowOpacityController and WindowInputController."""

    def __init__(self) -> None:
        self._entries: dict[int, _Entry] = {}

    # -- opacity -----------------------------------------------------------
    def apply(self, window: WindowInfo, percent: int) -> None:
        entry = self._entry(window.handle)
        if entry is None:
            return
        entry.opacity = percent
        self._sync(entry)

    def restore(self, window: WindowInfo) -> None:
        """Return ``window`` to full opacity and normal input."""
        entry = self._entries.get(window.handle)
        if entry is None:
            return
        entry.opacity = None
        entry.click_through = False
        self._sync(entry)

    def restore_all(self) -> None:
        for hwnd in list(self._entries):
            entry = self._entries.get(hwnd)
            if entry is not None:
                entry.opacity = None
                entry.click_through = False
                self._sync(entry)

    # -- click-through -----------------------------------------------------
    def set_click_through(self, window: WindowInfo, enabled: bool) -> None:
        entry = self._entry(window.handle)
        if entry is None:
            return
        entry.click_through = enabled
        self._sync(entry)

    def disable_all_click_through(self) -> None:
        for hwnd in list(self._entries):
            entry = self._entries.get(hwnd)
            if entry is not None and entry.click_through:
                entry.click_through = False
                self._sync(entry)

    # -- internals ---------------------------------------------------------
    def _entry(self, hwnd: int) -> _Entry | None:
        if not api.is_window(hwnd):
            return None
        entry = self._entries.get(hwnd)
        if entry is not None:
            return entry

        original_style = api.ex_style(hwnd)
        entry = _Entry(
            hwnd=hwnd,
            original_style=original_style,
            original_alpha=api.layered_alpha(hwnd),
        )
        self._entries[hwnd] = entry
        return entry

    def _sync(self, entry: _Entry) -> None:
        hwnd = entry.hwnd
        if not api.is_window(hwnd):
            self._entries.pop(hwnd, None)
            return

        wanted = 0
        if entry.opacity is not None:
            wanted |= api.WS_EX_LAYERED
        if entry.click_through:
            wanted |= api.WS_EX_LAYERED | api.WS_EX_TRANSPARENT

        current = api.ex_style(hwnd)
        target = (current & ~_MANAGED_FLAGS) | wanted
        if target != current:
            api.set_ex_style(hwnd, target)

        if wanted:
            alpha = round(
                (entry.opacity if entry.opacity is not None else 100) * 255 / 100
            )
            api.set_alpha(hwnd, max(1, min(255, alpha)))
        elif entry.original_alpha is not None:
            api.set_alpha(hwnd, entry.original_alpha)

        if not wanted:
            self._entries.pop(hwnd, None)
