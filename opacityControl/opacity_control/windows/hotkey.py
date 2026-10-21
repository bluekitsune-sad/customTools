"""Global emergency-exit shortcut (FR-5).

RegisterHotKey + a dedicated message loop runs off the UI thread, so the
shortcut keeps working regardless of which window has focus.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable

from . import api


class WindowsHotkeyManager:
    HOTKEY_ID = 0xA11C

    def __init__(self, modifiers: int = api.MOD_CONTROL | api.MOD_ALT,
                 virtual_key: int = api.VK_ESCAPE) -> None:
        self._modifiers = modifiers
        self._virtual_key = virtual_key
        self._label = self._describe(modifiers, virtual_key)
        self._callback: Callable[[], None] | None = None
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None

    @property
    def shortcut(self) -> str:
        return self._label

    @property
    def error(self) -> str | None:
        return self._error

    def register(self, callback: Callable[[], None]) -> None:
        self.unregister()
        self._callback = callback
        self._error = None
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, name="opacity-control-hotkey", daemon=True
        )
        self._thread.start()
        self._ready.wait(2.0)

    def unregister(self) -> None:
        thread = self._thread
        if thread is not None:
            if self._thread_id:
                api.post_quit_message(self._thread_id)
            thread.join(2.0)
        self._thread = None
        self._thread_id = 0
        self._callback = None

    def _run(self) -> None:
        self._thread_id = api.thread_id()
        modifiers = self._modifiers | api.MOD_NOREPEAT
        if not api.user32.RegisterHotKey(
            None, self.HOTKEY_ID, modifiers, self._virtual_key
        ):
            self._error = (
                f"{self._label} is already used by another application; "
                "use the panel's Restore button instead."
            )
            self._ready.set()
            return

        message = api.MSG()
        try:
            self._ready.set()
            while api.user32.GetMessageW(
                ctypes.byref(message), None, 0, 0
            ) > 0:
                if (
                    message.message == api.WM_HOTKEY
                    and message.wParam == self.HOTKEY_ID
                    and self._callback is not None
                ):
                    self._callback()
                api.user32.TranslateMessage(ctypes.byref(message))
                api.user32.DispatchMessageW(ctypes.byref(message))
        finally:
            api.user32.UnregisterHotKey(None, self.HOTKEY_ID)

    @staticmethod
    def _describe(modifiers: int, virtual_key: int) -> str:
        parts = []
        if modifiers & api.MOD_CONTROL:
            parts.append("Ctrl")
        if modifiers & api.MOD_ALT:
            parts.append("Alt")
        if modifiers & api.MOD_SHIFT:
            parts.append("Shift")
        if modifiers & api.MOD_WIN:
            parts.append("Win")
        key = "Esc" if virtual_key == api.VK_ESCAPE else str(virtual_key)
        parts.append(key)
        return "+".join(parts)
