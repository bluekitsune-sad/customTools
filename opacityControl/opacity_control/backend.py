"""Platform-neutral bundle of the controls the application needs."""

from __future__ import annotations

from dataclasses import dataclass

from .interfaces import (
    HotkeyManager,
    WindowInputController,
    WindowMovementController,
    WindowOpacityController,
    WindowProvider,
)


@dataclass(frozen=True)
class Backend:
    windows: WindowProvider
    opacity: WindowOpacityController
    input: WindowInputController
    movement: WindowMovementController
    hotkeys: HotkeyManager

    def shutdown(self) -> None:
        """Best-effort cleanup so no window is left transparent or pinned."""
        self.hotkeys.unregister()
        self.movement.unlock()
        self.input.disable_all_click_through()
        self.opacity.restore_all()
