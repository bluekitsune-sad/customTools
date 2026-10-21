"""Controller tests driven through a fake platform backend.

These run on any OS and verify that UI actions produce the right side effects
without touching Win32.
"""

from __future__ import annotations

import unittest

from opacity_control.app import OpacityApp
from opacity_control.backend import Backend
from opacity_control.models import WindowInfo
from opacity_control.state import Mode


def make_window(handle: int = 1, title: str = "Notepad") -> WindowInfo:
    return WindowInfo(
        handle=handle,
        title=title,
        class_name="Notepad",
        process_name="notepad.exe",
        process_id=100 + handle,
    )


class FakeWindows:
    def __init__(self) -> None:
        self.windows = [make_window(1), make_window(2, "Calculator")]
        self.alive = {window.handle for window in self.windows}

    def list_windows(self) -> list[WindowInfo]:
        return [w for w in self.windows if w.handle in self.alive]

    def is_available(self, window: WindowInfo) -> bool:
        return window.handle in self.alive


class FakeOpacity:
    def __init__(self) -> None:
        self.applied: dict[int, int] = {}
        self.restored: list[int] = []
        self.restore_all_calls = 0

    def apply(self, window: WindowInfo, percent: int) -> None:
        self.applied[window.handle] = percent

    def restore(self, window: WindowInfo) -> None:
        self.applied.pop(window.handle, None)
        self.restored.append(window.handle)

    def restore_all(self) -> None:
        self.restore_all_calls += 1
        self.applied.clear()


class FakeMovement:
    def __init__(self) -> None:
        self.locked: int | None = None
        self.unlock_calls = 0
        self.fail = False

    @property
    def is_locked(self) -> bool:
        return self.locked is not None

    def lock(self, window: WindowInfo) -> None:
        if self.fail:
            raise RuntimeError("lock failed")
        self.locked = window.handle

    def unlock(self) -> None:
        self.unlock_calls += 1
        self.locked = None


class FakeHotkeys:
    def __init__(self) -> None:
        self.shortcut = "Ctrl+Alt+Esc"
        self.error: str | None = None
        self.callback = None
        self.registered = False

    def register(self, callback) -> None:
        self.callback = callback
        self.registered = True

    def unregister(self) -> None:
        self.registered = False


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = FakeWindows()
        self.opacity = FakeOpacity()
        self.movement = FakeMovement()
        self.hotkeys = FakeHotkeys()
        self.app = OpacityApp(
            Backend(
                windows=self.windows,
                opacity=self.opacity,
                movement=self.movement,
                hotkeys=self.hotkeys,
            )
        )
        self.window = self.windows.windows[0]

    # -- selection ---------------------------------------------------------
    def test_refresh_returns_available_windows(self) -> None:
        self.assertEqual(len(self.app.refresh_windows()), 2)

    def test_select_target_sets_defaults(self) -> None:
        self.app.select_window(self.window)
        self.assertEqual(self.app.state.target, self.window)
        self.assertEqual(self.app.state.opacity, 100)
        self.assertIs(self.app.state.mode, Mode.MOVE)

    def test_selecting_new_target_restores_previous(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(40)

        self.app.select_window(self.windows.windows[1])

        self.assertIn(self.window.handle, self.opacity.restored)
        self.assertNotIn(self.window.handle, self.opacity.applied)

    # -- opacity -----------------------------------------------------------
    def test_opacity_applied_to_target(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(55)
        self.assertEqual(self.opacity.applied[self.window.handle], 55)
        self.assertEqual(self.app.state.opacity, 55)

    def test_opacity_is_clamped(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(1)
        self.assertEqual(self.app.state.opacity, 10)
        self.app.set_opacity(999)
        self.assertEqual(self.app.state.opacity, 100)

    def test_opacity_without_target_is_reported_not_raised(self) -> None:
        self.app.set_opacity(50)
        self.assertIsNotNone(self.app.notice)
        self.assertEqual(self.opacity.applied, {})

    # -- modes -------------------------------------------------------------
    def test_interactive_mode_locks_movement(self) -> None:
        self.app.select_window(self.window)
        self.app.enter_interactive_mode()
        self.assertEqual(self.movement.locked, self.window.handle)
        self.assertIs(self.app.state.mode, Mode.INTERACTIVE)

    def test_move_mode_unlocks_movement(self) -> None:
        self.app.select_window(self.window)
        self.app.enter_interactive_mode()
        self.app.enter_move_mode()
        self.assertIsNone(self.movement.locked)
        self.assertIs(self.app.state.mode, Mode.MOVE)

    def test_interactive_mode_keeps_opacity(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(35)
        self.app.enter_interactive_mode()
        self.assertEqual(self.app.state.opacity, 35)
        self.assertEqual(self.opacity.applied[self.window.handle], 35)

    def test_lock_failure_keeps_move_mode(self) -> None:
        self.app.select_window(self.window)
        self.movement.fail = True
        self.app.enter_interactive_mode()
        self.assertIs(self.app.state.mode, Mode.MOVE)
        self.assertIn("lock failed", self.app.notice or "")

    # -- exit and recovery -------------------------------------------------
    def test_deactivate_restores_opacity_and_movement(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(20)
        self.app.enter_interactive_mode()

        self.app.deactivate()

        self.assertEqual(self.opacity.applied, {})
        self.assertIsNone(self.movement.locked)
        self.assertEqual(self.app.state.opacity, 100)
        self.assertIs(self.app.state.mode, Mode.MOVE)
        self.assertIsNotNone(self.app.state.target)

    def test_hotkey_event_deactivates(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(30)
        self.app.enter_interactive_mode()

        assert self.hotkeys.callback is not None
        self.hotkeys.callback()
        self.app.process_events()

        self.assertEqual(self.app.state.opacity, 100)
        self.assertIs(self.app.state.mode, Mode.MOVE)

    def test_closed_target_clears_state(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(50)
        self.app.enter_interactive_mode()

        self.windows.alive.remove(self.window.handle)
        self.app.check_target()

        self.assertIsNone(self.app.state.target)
        self.assertIsNone(self.movement.locked)
        self.assertIn("closed", (self.app.notice or "").lower())

    def test_shutdown_restores_everything(self) -> None:
        self.app.select_window(self.window)
        self.app.set_opacity(25)
        self.app.enter_interactive_mode()

        self.app.shutdown()

        self.assertFalse(self.hotkeys.registered)
        self.assertIsNone(self.movement.locked)
        self.assertEqual(self.opacity.restore_all_calls, 1)
        self.assertIsNone(self.app.state.target)

    def test_change_notification_fires(self) -> None:
        updates: list[int] = []
        self.app.on_change = lambda: updates.append(1)
        self.app.select_window(self.window)
        self.app.set_opacity(70)
        self.assertEqual(len(updates), 2)


if __name__ == "__main__":
    unittest.main()
