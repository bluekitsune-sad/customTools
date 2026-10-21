"""Tests for the platform-neutral state machine."""

from __future__ import annotations

import unittest

from opacity_control.models import WindowInfo
from opacity_control.state import (
    DEFAULT_OPACITY,
    MAX_OPACITY,
    MIN_OPACITY,
    Mode,
    StateError,
    WindowState,
    clamp_opacity,
)


def make_window(handle: int = 1, title: str = "Notepad") -> WindowInfo:
    return WindowInfo(
        handle=handle,
        title=title,
        class_name="Notepad",
        process_name="notepad.exe",
        process_id=100 + handle,
    )


class ClampTests(unittest.TestCase):
    def test_clamps_below_minimum(self) -> None:
        self.assertEqual(clamp_opacity(0), MIN_OPACITY)
        self.assertEqual(clamp_opacity(-20), MIN_OPACITY)

    def test_clamps_above_maximum(self) -> None:
        self.assertEqual(clamp_opacity(400), MAX_OPACITY)

    def test_rounds_to_nearest(self) -> None:
        self.assertEqual(clamp_opacity(42.6), 43)


class SelectionTests(unittest.TestCase):
    def test_initial_state(self) -> None:
        state = WindowState()
        self.assertIsNone(state.target)
        self.assertFalse(state.has_target)
        self.assertEqual(state.opacity, DEFAULT_OPACITY)
        self.assertIs(state.mode, Mode.MOVE)

    def test_select_starts_at_full_opacity_and_move_mode(self) -> None:
        window = make_window()
        state = WindowState().select(window).with_opacity(40)
        state = state.in_interactive_mode()

        reselected = state.select(make_window(2, "Calculator"))

        self.assertEqual(reselected.target.title, "Calculator")
        self.assertEqual(reselected.opacity, DEFAULT_OPACITY)
        self.assertIs(reselected.mode, Mode.MOVE)

    def test_clear_target_resets_defaults(self) -> None:
        state = (
            WindowState()
            .select(make_window())
            .with_opacity(25)
            .in_interactive_mode()
            .clear_target()
        )
        self.assertIsNone(state.target)
        self.assertEqual(state.opacity, DEFAULT_OPACITY)
        self.assertIs(state.mode, Mode.MOVE)


class ModeTests(unittest.TestCase):
    def test_opacity_requires_target(self) -> None:
        with self.assertRaises(StateError):
            WindowState().with_opacity(50)

    def test_interactive_mode_requires_target(self) -> None:
        with self.assertRaises(StateError):
            WindowState().in_interactive_mode()

    def test_entering_interactive_mode_keeps_opacity(self) -> None:
        state = WindowState().select(make_window()).with_opacity(60)
        self.assertEqual(state.in_interactive_mode().opacity, 60)

    def test_move_mode_requires_target(self) -> None:
        with self.assertRaises(StateError):
            WindowState().in_move_mode()

    def test_restored_keeps_target(self) -> None:
        state = (
            WindowState()
            .select(make_window())
            .with_opacity(10)
            .in_interactive_mode()
            .restored()
        )
        self.assertIsNotNone(state.target)
        self.assertEqual(state.opacity, DEFAULT_OPACITY)
        self.assertIs(state.mode, Mode.MOVE)

    def test_state_is_immutable(self) -> None:
        state = WindowState().select(make_window())
        new_state = state.with_opacity(30)
        self.assertEqual(state.opacity, DEFAULT_OPACITY)
        self.assertEqual(new_state.opacity, 30)


if __name__ == "__main__":
    unittest.main()
