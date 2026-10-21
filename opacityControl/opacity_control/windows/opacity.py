"""Per-window alpha via WS_EX_LAYERED (FR-2).

Applied windows are remembered so the original extended style can be
restored exactly, including windows that were already layered before we
touched them.
"""

from __future__ import annotations

from ..models import WindowInfo
from . import api


def _percent_to_alpha(percent: int) -> int:
    return max(1, min(255, round(percent * 255 / 100)))


class WindowsOpacityController:
    def __init__(self) -> None:
        # handle -> True when *we* added WS_EX_LAYERED and must remove it again
        self._added_layered: dict[int, bool] = {}
        self._applied: set[int] = set()

    def apply(self, window: WindowInfo, percent: int) -> None:
        hwnd = window.handle
        if not api.is_window(hwnd):
            return

        style = api.ex_style(hwnd)
        added = not (style & api.WS_EX_LAYERED)
        if added:
            api.set_ex_style(hwnd, style | api.WS_EX_LAYERED)

        if api.set_alpha(hwnd, _percent_to_alpha(percent)):
            self._added_layered[hwnd] = self._added_layered.get(hwnd, False) or added
            self._applied.add(hwnd)

    def restore(self, window: WindowInfo) -> None:
        self._restore_handle(window.handle)

    def restore_all(self) -> None:
        for hwnd in list(self._applied):
            self._restore_handle(hwnd)

    def _restore_handle(self, hwnd: int) -> None:
        if api.is_window(hwnd):
            api.set_alpha(hwnd, 255)
            if self._added_layered.get(hwnd):
                style = api.ex_style(hwnd)
                if style & api.WS_EX_LAYERED:
                    api.set_ex_style(hwnd, style & ~api.WS_EX_LAYERED)
        self._added_layered.pop(hwnd, None)
        self._applied.discard(hwnd)
