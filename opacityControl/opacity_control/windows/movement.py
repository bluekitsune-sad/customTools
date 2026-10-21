"""Movement locking without blocking input (FR-4).

Windows does not let another process intercept a foreign window's
WM_NCLBUTTONDOWN, and installing a global CBT hook would require injecting
code. Instead we subscribe to EVENT_OBJECT_LOCATIONCHANGE for the target and
push it back to its anchor position whenever it is moved. Input keeps flowing
to the application because the window is never disabled, never made
click-through and never re-parented.
"""

from __future__ import annotations

import ctypes
import threading

from ..models import WindowInfo
from . import api

_TIMEOUT = 2.0


class WindowsMovementController:
    def __init__(self) -> None:
        self._hwnd: int | None = None
        self._anchor: tuple[int, int] | None = None
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: str | None = None
        self._snapping = False
        self._hook = None
        self._callback_ref = None

    @property
    def is_locked(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def lock(self, window: WindowInfo) -> None:
        self.unlock()
        rect = api.get_rect(window.handle)
        if rect is None:
            raise RuntimeError("The target window is no longer available.")

        self._hwnd = window.handle
        self._anchor = (rect[0], rect[1])
        self._error = None
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, name="opacity-control-movement", daemon=True
        )
        self._thread.start()
        self._ready.wait(_TIMEOUT)
        if not self._ready.is_set():
            self._error = "The movement watcher did not start."
        if self._error:
            message = self._error
            self.unlock()
            raise RuntimeError(message)

    def unlock(self) -> None:
        thread = self._thread
        if thread is not None:
            if self._thread_id:
                api.post_quit_message(self._thread_id)
            thread.join(_TIMEOUT)
        self._thread = None
        self._thread_id = 0
        self._hwnd = None
        self._anchor = None
        self._snapping = False
        self._error = None

    # -- worker thread -----------------------------------------------------
    def _run(self) -> None:
        self._thread_id = api.thread_id()
        self._callback_ref = api.WINEVENTPROC(self._on_location_change)
        hook = api.user32.SetWinEventHook(
            api.EVENT_OBJECT_LOCATIONCHANGE,
            api.EVENT_OBJECT_LOCATIONCHANGE,
            None,
            self._callback_ref,
            0,
            0,
            api.WINEVENT_OUTOFCONTEXT | api.WINEVENT_SKIPOWNPROCESS,
        )
        if not hook:
            self._error = (
                "Could not install the movement watcher "
                f"(error {ctypes.get_last_error()})."
            )
            self._ready.set()
            return

        message = api.MSG()
        try:
            self._ready.set()
            while api.user32.GetMessageW(
                ctypes.byref(message), None, 0, 0
            ) > 0:
                api.user32.TranslateMessage(ctypes.byref(message))
                api.user32.DispatchMessageW(ctypes.byref(message))
        finally:
            api.user32.UnhookWinEvent(hook)

    def _on_location_change(
        self,
        _hook: int,
        _event: int,
        hwnd: int,
        _id_object: int,
        _id_child: int,
        _thread: int,
        _time: int,
    ) -> None:
        if self._snapping or hwnd != self._hwnd or self._anchor is None:
            return
        if not api.is_window(hwnd):
            return

        rect = api.get_rect(hwnd)
        if rect is None or (rect[0], rect[1]) == self._anchor:
            return

        self._snapping = True
        try:
            api.set_position(hwnd, *self._anchor)
        finally:
            self._snapping = False
