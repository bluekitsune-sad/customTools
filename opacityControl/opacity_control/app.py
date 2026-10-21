"""Application controller: wires the UI to the platform backend.

All UI-facing methods are expected to run on the Tk thread. The global
hotkey callback only pushes an event into a queue, which the UI drains on a
timer, so no Tk object is ever touched from a background thread.
"""

from __future__ import annotations

import queue
from collections.abc import Callable

from .backend import Backend
from .models import WindowInfo
from .state import Mode, StateError, WindowState

_DEACTIVATE = "deactivate"


class OpacityApp:
    def __init__(self, backend: Backend) -> None:
        self._backend = backend
        self._state = WindowState()
        self._windows: list[WindowInfo] = []
        self._events: queue.SimpleQueue[str] = queue.SimpleQueue()
        self.notice: str | None = None
        self.on_change: Callable[[], None] | None = None

        try:
            backend.hotkeys.register(lambda: self._events.put(_DEACTIVATE))
        except RuntimeError as exc:  # pragma: no cover - platform dependent
            self.notice = str(exc)

    # -- read-only view ----------------------------------------------------
    @property
    def state(self) -> WindowState:
        return self._state

    @property
    def windows(self) -> list[WindowInfo]:
        return self._windows

    @property
    def shortcut(self) -> str:
        return self._backend.hotkeys.shortcut

    @property
    def hotkey_error(self) -> str | None:
        return self._backend.hotkeys.error

    # -- target selection --------------------------------------------------
    def refresh_windows(self) -> list[WindowInfo]:
        self._windows = list(self._backend.windows.list_windows())
        return self._windows

    def select_window(self, window: WindowInfo) -> None:
        if self._state.target == window:
            return
        self._release_target()
        self._state = self._state.select(window)
        self.notice = None
        self._changed()

    # -- opacity -----------------------------------------------------------
    def set_opacity(self, percent: int) -> None:
        try:
            new_state = self._state.with_opacity(percent)
        except StateError as exc:
            self.notice = str(exc)
            self._changed()
            return
        self._state = new_state
        target = self._state.target
        if target is not None:
            self._backend.opacity.apply(target, new_state.opacity)
        self.notice = None
        self._changed()

    # -- modes -------------------------------------------------------------
    def enter_move_mode(self) -> None:
        self._backend.movement.unlock()
        try:
            self._state = self._state.in_move_mode()
            self.notice = None
        except StateError as exc:
            self.notice = str(exc)
        self._changed()

    def enter_interactive_mode(self) -> None:
        target = self._state.target
        if target is None:
            self.notice = "Select a target window first."
            self._changed()
            return
        try:
            self._backend.movement.lock(target)
        except RuntimeError as exc:
            self.notice = str(exc)
            self._changed()
            return
        self._state = self._state.in_interactive_mode()
        self.notice = None
        self._changed()

    def deactivate(self) -> None:
        """Restore full opacity and movement (FR-5)."""
        target = self._state.target
        self._backend.movement.unlock()
        if target is not None:
            self._backend.opacity.restore(target)
        self._state = self._state.restored()
        self.notice = None
        self._changed()

    # -- lifecycle ---------------------------------------------------------
    def process_events(self) -> None:
        """Drain cross-thread requests (global hotkey)."""
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            if event == _DEACTIVATE:
                self.deactivate()

    def check_target(self) -> None:
        """Drop the target when its window was closed (FR-1 / edge cases)."""
        target = self._state.target
        if target is None:
            return
        if not self._backend.windows.is_available(target):
            self._backend.movement.unlock()
            self._state = self._state.clear_target()
            self.notice = "The target window was closed."
            self._changed()

    def shutdown(self) -> None:
        self._backend.shutdown()
        self._state = self._state.clear_target()

    # -- helpers -----------------------------------------------------------
    def _release_target(self) -> None:
        target = self._state.target
        if target is None:
            return
        self._backend.movement.unlock()
        self._backend.opacity.restore(target)

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()


__all__ = ["Mode", "OpacityApp"]
