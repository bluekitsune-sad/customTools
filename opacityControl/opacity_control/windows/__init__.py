"""Windows backend: exposes the platform-neutral controls from interfaces.py."""

from __future__ import annotations

from ..backend import Backend
from .effects import WindowsWindowEffects
from .hotkey import WindowsHotkeyManager
from .movement import WindowsMovementController
from .provider import WindowsWindowProvider

__all__ = ["Backend", "create_backend"]


def create_backend() -> Backend:
    effects = WindowsWindowEffects()
    return Backend(
        windows=WindowsWindowProvider(),
        opacity=effects,
        input=effects,
        movement=WindowsMovementController(),
        hotkeys=WindowsHotkeyManager(),
    )
