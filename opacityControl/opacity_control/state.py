"""Mode and target tracking, independent of any platform API.

The invariants from the PRD live here:
* opacity is always within 10-100;
* Interactive Mode is only valid while a target window exists;
* activating a new target always starts from Move Mode at 100% opacity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .models import WindowInfo

MIN_OPACITY = 10
MAX_OPACITY = 100
DEFAULT_OPACITY = 100


class Mode(str, Enum):
    MOVE = "move"
    INTERACTIVE = "interactive"
    CLICK_THROUGH = "click-through"

    @property
    def label(self) -> str:
        return {
            Mode.MOVE: "Move Mode",
            Mode.INTERACTIVE: "Interactive Mode",
            Mode.CLICK_THROUGH: "Click-through Mode",
        }[self]

    @property
    def hint(self) -> str:
        return {
            Mode.MOVE: "Position unlocked: drag the window by its title bar. Input stays live.",
            Mode.INTERACTIVE: "Position locked: use the window normally.",
            Mode.CLICK_THROUGH: (
                "Mouse clicks pass to the window behind. "
                "Use the shortcut or Restore & Exit Mode to recover."
            ),
        }[self]


class StateError(RuntimeError):
    """Raised when a request contradicts the current state."""


@dataclass(frozen=True)
class WindowState:
    target: WindowInfo | None = None
    opacity: int = DEFAULT_OPACITY
    mode: Mode = Mode.MOVE

    @property
    def has_target(self) -> bool:
        return self.target is not None

    def select(self, window: WindowInfo) -> "WindowState":
        """Activate ``window``, resetting it to Move Mode at full opacity."""
        return replace(self, target=window, opacity=DEFAULT_OPACITY, mode=Mode.MOVE)

    def clear_target(self) -> "WindowState":
        """Forget the target after it was closed or released."""
        return replace(self, target=None, opacity=DEFAULT_OPACITY, mode=Mode.MOVE)

    def with_opacity(self, percent: int) -> "WindowState":
        if self.target is None:
            raise StateError("Select a target window before changing opacity.")
        return replace(self, opacity=clamp_opacity(percent))

    def in_move_mode(self) -> "WindowState":
        if self.target is None:
            raise StateError("Cannot change mode without a target window.")
        return replace(self, mode=Mode.MOVE)

    def in_interactive_mode(self) -> "WindowState":
        if self.target is None:
            raise StateError("Cannot enter Interactive Mode without a target window.")
        return replace(self, mode=Mode.INTERACTIVE)

    def in_click_through_mode(self) -> "WindowState":
        if self.target is None:
            raise StateError("Cannot enter Click-through Mode without a target window.")
        return replace(self, mode=Mode.CLICK_THROUGH)

    def restored(self) -> "WindowState":
        """Return to Move Mode at full opacity, keeping the target."""
        return replace(self, opacity=DEFAULT_OPACITY, mode=Mode.MOVE)


def clamp_opacity(percent: int | float) -> int:
    return max(MIN_OPACITY, min(MAX_OPACITY, int(round(percent))))
