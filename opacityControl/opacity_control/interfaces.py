"""Platform boundary for window enumeration, opacity, input, movement and hotkeys.

Everything platform specific lives behind these protocols. A future Linux
backend only has to provide implementations of them (see PRD section 6.2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from .models import WindowInfo


class WindowProvider(Protocol):
    """Enumerates controllable windows and reports whether one still exists."""

    def list_windows(self) -> Sequence[WindowInfo]:
        """Return the currently selectable top-level windows."""

    def is_available(self, window: WindowInfo) -> bool:
        """Return False once the window was closed or destroyed."""


class WindowOpacityController(Protocol):
    """Applies and restores per-window alpha."""

    def apply(self, window: WindowInfo, percent: int) -> None:
        """Set the opacity of ``window`` to ``percent`` (10-100)."""

    def restore(self, window: WindowInfo) -> None:
        """Return ``window`` to full opacity, normal input and its original style."""

    def restore_all(self) -> None:
        """Return every window touched by this controller to its original state."""


class WindowInputController(Protocol):
    """Opt-in click-through: mouse input passes to the window behind.

    This is an explicit mode only. It must never be used as a way to lock a
    window's position, and it must always be reversible from outside the
    target window.
    """

    def set_click_through(self, window: WindowInfo, enabled: bool) -> None:
        """Toggle whether ``window`` ignores mouse input."""

    def disable_all_click_through(self) -> None:
        """Make every touched window receive input again."""


class WindowMovementController(Protocol):
    """Locks a window in place without swallowing its input."""

    @property
    def is_locked(self) -> bool:
        """True while the target window is pinned."""

    def lock(self, window: WindowInfo) -> None:
        """Pin ``window`` at its current position."""

    def unlock(self) -> None:
        """Allow the pinned window to move again."""


class HotkeyManager(Protocol):
    """Registers the global emergency-exit shortcut."""

    @property
    def shortcut(self) -> str:
        """Human-readable shortcut, e.g. ``Ctrl+Alt+Esc``."""

    @property
    def error(self) -> str | None:
        """Registration failure (usually a conflict), if any."""

    def register(self, callback: Callable[[], None]) -> None:
        """Start listening for the shortcut and call ``callback`` on press."""

    def unregister(self) -> None:
        """Stop listening and release the shortcut."""
