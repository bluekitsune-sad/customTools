# Opacity Control

A Windows utility that makes a specific application window transparent while
keeping it **fully interactive** — you can still click, type, and scroll in it.
Position the window, then lock it in place so it stays put.

Transparency is not click-through: input always goes to the transparent
window, never to whatever is behind it.

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
4. Leave the window in **Move Mode** while you position and resize it with its
   own title bar and window controls.
5. Click **Interactive Mode** to pin it at that position. You can keep working
   inside it normally.
6. Exit at any time:
   - press `Ctrl + Alt + Esc` from anywhere, or
   - click **Restore & Exit Mode**.

   Both restore 100% opacity and allow the window to move again.

The **Always on top** checkbox controls whether the panel itself floats above
other windows.

If the target window is closed, the utility notices, releases the lock, and
asks you to choose another window. Closing the utility restores every window
it touched.

## How it works

| Concern | Approach |
| --- | --- |
| Opacity | Adds `WS_EX_LAYERED` to the target and applies `SetLayeredWindowAttributes`. The original extended style is restored on exit, including windows that were already layered. |
| Movement lock | Subscribes to `EVENT_OBJECT_LOCATIONCHANGE` and moves the window back to its anchor position when it is dragged. Input is never blocked, disabled, or made click-through. |
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

The suite is platform neutral (fake backend) and covers opacity clamping, mode
transitions, target-close recovery, deactivation, and shutdown cleanup.

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
