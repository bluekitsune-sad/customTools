"""Enumeration of eligible top-level windows (FR-1)."""

from __future__ import annotations

import os

from ..models import WindowInfo
from . import api

# Shell windows that are technically visible top-level windows but should
# never appear in the picker.
_IGNORED_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
    "XamlExplorerHostIslandWindow",
    "ForegroundStaging",
}


class WindowsWindowProvider:
    """Lists visible, titled, non-minimized windows of other processes."""

    def list_windows(self) -> list[WindowInfo]:
        results: list[WindowInfo] = []
        own_pid = os.getpid()

        @api.WNDENUMPROC
        def _collect(hwnd: int, _lparam: int) -> bool:
            info = self._describe(hwnd, own_pid)
            if info is not None:
                results.append(info)
            return True

        api.user32.EnumWindows(_collect, 0)
        results.sort(key=lambda w: (w.process_name.lower(), w.title.lower()))
        return results

    def is_available(self, window: WindowInfo) -> bool:
        # Cloaked windows are still alive (another virtual desktop), so only
        # actual destruction clears the target.
        return api.is_window(window.handle)

    def _describe(self, hwnd: int, own_pid: int) -> WindowInfo | None:
        if not api.is_visible(hwnd) or api.is_minimized(hwnd):
            return None
        if api.owner_window(hwnd):
            return None
        if api.is_cloaked(hwnd):
            return None
        if api.ex_style(hwnd) & api.WS_EX_TOOLWINDOW:
            return None

        cls = api.class_name(hwnd)
        if cls in _IGNORED_CLASSES:
            return None

        title = api.window_title(hwnd).strip()
        if not title:
            return None

        pid = api.process_id(hwnd)
        if not pid or pid == own_pid:
            return None

        return WindowInfo(
            handle=int(hwnd),
            title=title,
            class_name=cls,
            process_name=api.process_name(hwnd),
            process_id=pid,
        )
