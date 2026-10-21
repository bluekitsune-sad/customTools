"""Platform-neutral data model for a selectable application window."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    """A top-level window that the utility is allowed to control."""

    handle: int
    title: str
    class_name: str
    process_name: str
    process_id: int

    @property
    def label(self) -> str:
        """Human-readable identifier shown in the window picker."""
        process = self.process_name or "unknown process"
        return f"{self.title} — {process} (pid {self.process_id})"
