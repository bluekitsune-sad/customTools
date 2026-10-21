# Opacity Control

A Windows utility that makes a specific application window transparent while
keeping it usable. Position it, lock it in place, and optionally let mouse
clicks pass through to the application behind it.

| Mode | Position | Mouse input | Use it when |
| --- | --- | --- | --- |
| **Move** | Unlocked | Goes to the target | Position and resize the window |
| **Interactive** | Locked | Goes to the target | Work inside the window normally |
| **Click-through** | Locked | Goes to the window behind | Use the target as a passive overlay |

![status](https://img.shields.io/badge/status-MVP-orange)

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer (with Tkinter, included in the standard Windows
  installer)
- No third-party packages, no administrator rights

## Run

```powershell
cd opacityControl
python main.py
```

## How to use

1. Launch the utility. The small control panel stays on top by default.
2. Pick the application window from **Target window** (use **Refresh** after
   opening or closing apps).
3. Drag the **Opacity** slider. Changes apply immediately, from 10% to 100%;
   the window stays usable the whole time.
4. Leave the window in **Move** while you position and resize it with its own
   title bar and window controls.
5. Choose **Interactive** to pin it at that position and keep using it.
6. Or choose **Click-through** to pin it and let mouse clicks reach the window
   behind it. Only use this while you do not need to click the target itself.
7. Exit at any time:
   - press `Ctrl + Alt + Esc` from anywhere, or
   - click **Restore & Exit Mode**.

   Both restore 100% opacity, normal mouse input, and free movement.

The **Always on top** checkbox controls whether the panel itself floats above
other windows.

If the target window is closed, the utility notices, releases the lock, and
asks you to choose another window. Closing the utility restores every window
it touched.

> **Click-through and recovery:** while Click-through is active the target
> ignores the mouse, so use the panel or `Ctrl+Alt+Esc` to leave the mode. If
> the utility is force-killed in that mode, the target keeps ignoring clicks
> until it is restarted.

## How it works

| Concern | Approach |
| --- | --- |
| Opacity | Adds `WS_EX_LAYERED` to the target and applies `SetLayeredWindowAttributes`. |
| Click-through | Adds `WS_EX_TRANSPARENT` (plus `WS_EX_LAYERED`, required for reliable hit testing) so mouse input skips the target. |
| Style ownership | One controller owns `WS_EX_LAYERED` and `WS_EX_TRANSPARENT` and recomputes them from the active features, so opacity and click-through can be toggled in any order and still restore the window's original style and alpha. |
| Movement lock | Subscribes to `EVENT_OBJECT_LOCATIONCHANGE` and moves the window back to its anchor position when it is dragged. Input is never blocked, disabled, or made click-through to lock movement. |
| Exit | `RegisterHotKey` for a system-wide `Ctrl+Alt+Esc`, plus an always-visible button. |
| Platform boundary | Core state and UI depend only on protocols in `opacity_control/interfaces.py`; all Win32 calls live in `opacity_control/windows/`. |

Everything is built on `ctypes` and the standard library, so there is nothing
to install and nothing to compile.

## Project layout

```
opacityControl/
├── main.py                  entry point
├── opacity_control/
│   ├── state.py             opacity/mode state machine
│   ├── models.py            WindowInfo
│   ├── interfaces.py        platform protocols
│   ├── backend.py           backend bundle
│   ├── app.py               controller (no widget code)
│   ├── ui/panel.py          Tkinter control panel
│   └── windows/             Win32 backend
├── tests/                   headless unit tests
├── PRD.md                   product requirements
├── AGENTS.md                contributor/agent conventions
└── TODO.md                  lifecycle checklist and known gaps
```

## Tests

```powershell
cd opacityControl
python -m unittest discover -s tests -v
```

38 tests run on any platform with a fake backend: opacity clamping, mode
transitions, click-through enable/disable on every path, target-close
recovery, deactivation, and shutdown cleanup.

## Limitations

- No tray icon yet. Persistent access is the always-on-top panel, the taskbar
  entry, and the global shortcut.
- The exit shortcut is fixed at `Ctrl+Alt+Esc`. If another application already
  owns it, the panel says so and the **Restore & Exit Mode** button still
  works.
- Only top-level windows of other processes are listed. Minimized, cloaked
  (other virtual desktop), tool, and shell windows are hidden.
- Windows that render through custom composition (some games, video players,
  apps with anti-cheat) may ignore layered alpha. The utility leaves such
  windows untouched rather than forcing anything.
- Click-through is mouse-only: the target can still receive keyboard input
  when focused.
- Abnormal termination in Click-through Mode leaves the target ignoring the
  mouse until it restarts. Normal exit paths always clear it.
- Movement is reverted by snapping the window back. Applications that animate
  or continually reposition themselves can fight the lock; standard Win32 and
  Chromium/Electron windows behave correctly in testing.
- One target window at a time, by design.

## Roadmap

Phase 2/3 work — tray icon, configurable shortcut, broader custom-frame
testing, Linux backend — is tracked in [`TODO.md`](TODO.md). Requirements live
in [`PRD.md`](PRD.md).

## License

MIT — see the repository [`LICENSE`](../LICENSE).
