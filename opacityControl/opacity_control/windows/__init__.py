"""Windows backend: exposes the platform-neutral controls from interfaces.py."""

from __future__ import annotations

from ..backend import Backend
from .hotkey import WindowsHotkeyManager
from .movement import WindowsMovementController
from .opacity import WindowsOpacityController
from .provider import WindowsWindowProvider

__all__ = ["Backend", "create_backend"]


def create_backend() -> Backend:
    return Backend(
        windows=WindowsWindowProvider(),
        opacity=WindowsOpacityController(),
        movement=WindowsMovementController(),
        hotkeys=WindowsHotkeyManager(),
    )
