"""Tkinter control panel (PRD section 5)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..app import OpacityApp
from ..models import WindowInfo
from ..state import Mode

_POLL_MS = 200

_ACCENT = "#2f6fed"
_INACTIVE = "#e8e8e8"
_DANGER = "#b3382c"
_WARNING = "#a15c00"

_MODE_LABELS = {
    Mode.MOVE: "Move",
    Mode.INTERACTIVE: "Interactive",
    Mode.CLICK_THROUGH: "Click-through",
}


class ControlPanel:
    def __init__(self, app: OpacityApp) -> None:
        self._app = app
        self._windows: list[WindowInfo] = []
        self._updating = False

        self._root = tk.Tk()
        self._root.title("Window Opacity")
        self._root.resizable(False, False)
        self._root.attributes("-topmost", True)

        self._target_var = tk.StringVar()
        self._percent_var = tk.StringVar(value="100%")
        self._status_var = tk.StringVar()
        self._hint_var = tk.StringVar()
        self._notice_var = tk.StringVar()

        self._build()
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        app.on_change = self._render
        self._refresh()
        self._root.after(_POLL_MS, self._tick)

    # -- construction ------------------------------------------------------
    def _build(self) -> None:
        frame = ttk.Frame(self._root, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="Window Opacity",
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Pick a window, choose an opacity, then choose a mode.",
            foreground="#555555",
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Target window").grid(row=2, column=0, sticky="w")

        picker = ttk.Frame(frame)
        picker.grid(row=3, column=0, sticky="ew", pady=(2, 10))
        picker.columnconfigure(0, weight=1)

        self._combo = ttk.Combobox(
            picker,
            textvariable=self._target_var,
            state="readonly",
            width=44,
        )
        self._combo.grid(row=0, column=0, sticky="ew")
        self._combo.bind("<<ComboboxSelected>>", self._on_select)

        self._refresh_button = ttk.Button(
            picker, text="Refresh", width=9, command=self._refresh
        )
        self._refresh_button.grid(row=0, column=1, padx=(8, 0))

        opacity_header = ttk.Frame(frame)
        opacity_header.grid(row=4, column=0, sticky="ew")
        opacity_header.columnconfigure(0, weight=1)
        ttk.Label(opacity_header, text="Opacity").grid(row=0, column=0, sticky="w")
        self._percent_label = ttk.Label(
            opacity_header,
            textvariable=self._percent_var,
            font=("Segoe UI Semibold", 10),
        )
        self._percent_label.grid(row=0, column=1, sticky="e")

        self._slider_var = tk.IntVar(value=100)
        self._slider = ttk.Scale(
            frame,
            from_=10,
            to=100,
            orient="horizontal",
            variable=self._slider_var,
            command=self._on_opacity,
        )
        self._slider.grid(row=5, column=0, sticky="ew", pady=(2, 10))

        mode_row = ttk.Frame(frame)
        mode_row.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(mode_row, text="Mode").grid(row=0, column=0, padx=(0, 10))

        self._move_button = self._mode_button(mode_row, Mode.MOVE, column=1)
        self._interactive_button = self._mode_button(
            mode_row, Mode.INTERACTIVE, column=2
        )
        self._click_through_button = self._mode_button(
            mode_row, Mode.CLICK_THROUGH, column=3
        )

        ttk.Label(
            frame,
            textvariable=self._status_var,
            wraplength=380,
            justify="left",
        ).grid(row=7, column=0, sticky="w", pady=(0, 2))

        self._hint_label = ttk.Label(
            frame,
            textvariable=self._hint_var,
            wraplength=380,
            justify="left",
            foreground="#555555",
        )
        self._hint_label.grid(row=8, column=0, sticky="w", pady=(0, 6))

        ttk.Label(
            frame,
            textvariable=self._notice_var,
            wraplength=380,
            justify="left",
            foreground=_DANGER,
        ).grid(row=9, column=0, sticky="w", pady=(0, 8))

        self._restore_button = tk.Button(
            frame,
            text="Restore && Exit Mode",
            bg=_DANGER,
            fg="white",
            activebackground="#8f2c22",
            activeforeground="white",
            relief="flat",
            padx=10,
            pady=6,
            command=self._app.deactivate,
        )
        self._restore_button.grid(row=10, column=0, sticky="ew", pady=(0, 10))

        footer = ttk.Frame(frame)
        footer.grid(row=11, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            text=f"Global exit: {self._app.shortcut}",
            foreground="#555555",
        ).grid(row=0, column=0, sticky="w")

        self._topmost_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            footer,
            text="Always on top",
            variable=self._topmost_var,
            command=self._apply_topmost,
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(
            frame,
            text=(
                "Transparency is not click-through by default: unless you pick "
                "Click-through, the target stays fully usable."
            ),
            foreground="#777777",
            wraplength=380,
            justify="left",
        ).grid(row=12, column=0, sticky="w", pady=(8, 0))

    def _mode_button(
        self, parent: tk.Widget, mode: Mode, column: int
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=_MODE_LABELS[mode],
            relief="flat",
            padx=6,
            pady=3,
            command=lambda: self._select_mode(mode),
        )
        button.grid(row=0, column=column, padx=(0 if column == 1 else 6, 0))
        return button

    # -- command handlers --------------------------------------------------
    def _refresh(self) -> None:
        selected = self._app.state.target
        self._windows = self._app.refresh_windows()
        labels = [window.label for window in self._windows]
        self._combo["values"] = labels

        if selected is not None:
            try:
                index = self._windows.index(selected)
            except ValueError:
                self._target_var.set("")
            else:
                self._target_var.set(labels[index])
        else:
            self._target_var.set("")
        self._render()

    def _on_select(self, _event: object = None) -> None:
        index = self._combo.current()
        if 0 <= index < len(self._windows):
            self._app.select_window(self._windows[index])

    def _on_opacity(self, raw_value: str) -> None:
        if self._updating:
            return
        percent = int(round(float(raw_value)))
        self._percent_var.set(f"{percent}%")
        self._app.set_opacity(percent)

    def _select_mode(self, mode: Mode) -> None:
        if mode is Mode.MOVE:
            self._app.enter_move_mode()
        elif mode is Mode.INTERACTIVE:
            self._app.enter_interactive_mode()
        else:
            self._app.enter_click_through_mode()

    def _apply_topmost(self) -> None:
        self._root.attributes("-topmost", bool(self._topmost_var.get()))

    def _close(self) -> None:
        self._app.shutdown()
        self._root.destroy()

    def _tick(self) -> None:
        self._app.process_events()
        self._app.check_target()
        self._render()
        self._root.after(_POLL_MS, self._tick)

    # -- rendering ---------------------------------------------------------
    def _render(self) -> None:
        state = self._app.state
        has_target = state.target is not None

        self._updating = True
        try:
            if not has_target:
                self._target_var.set("")
            elif state.target is not None:
                self._target_var.set(state.target.label)

            if self._slider_var.get() != state.opacity:
                self._slider_var.set(state.opacity)
            self._percent_var.set(f"{state.opacity}%")
        finally:
            self._updating = False

        self._slider.state(["!disabled"] if has_target else ["disabled"])
        self._combo.state(["!disabled"])

        for button, mode in (
            (self._move_button, Mode.MOVE),
            (self._interactive_button, Mode.INTERACTIVE),
            (self._click_through_button, Mode.CLICK_THROUGH),
        ):
            active = has_target and state.mode is mode
            label = _MODE_LABELS[mode]
            button.configure(
                text=f"● {label}" if active else label,
                bg=_ACCENT if active else _INACTIVE,
                fg="white" if active else "#222222",
                activebackground=_ACCENT if active else "#d6d6d6",
                activeforeground="white" if active else "#222222",
                state="normal" if has_target else "disabled",
            )

        self._restore_button.configure(
            state="normal" if has_target else "disabled",
            bg=_DANGER if has_target else "#c9c9c9",
        )

        if state.target is None:
            self._status_var.set(f"No target selected · {state.mode.label}")
        else:
            self._status_var.set(
                f"{state.mode.label} · {state.opacity}% · {state.target.title}"
            )

        self._hint_var.set(state.mode.hint)
        self._hint_label.configure(
            foreground=(
                _WARNING if state.mode is Mode.CLICK_THROUGH else "#555555"
            )
        )

        notice = self._app.notice
        if not notice and self._app.hotkey_error:
            notice = (
                f"Hotkey unavailable: {self._app.hotkey_error} "
                "Use Restore & Exit Mode instead."
            )
        self._notice_var.set(notice or "")

    # -- entry point -------------------------------------------------------
    def run(self) -> None:
        self._root.mainloop()
