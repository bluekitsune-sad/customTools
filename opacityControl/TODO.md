# TODO — Opacity Control

Tracking the MVP defined in `PRD.md` section 11. Work proceeds through the
factory stages below; a phase is done only when its checks pass.

## Phase 0 — Requirements (done)

- [x] PRD written (`PRD.md`)
- [x] Hard rules captured: transparency ≠ click-through, always reversible
- [x] Architecture boundary agreed: platform-neutral core + Windows backend

## Phase 1 — Design (done)

- [x] `WindowInfo` value object (`models.py`)
- [x] Platform protocols: `WindowProvider`, `WindowOpacityController`,
      `WindowMovementController`, `HotkeyManager` (`interfaces.py`)
- [x] State machine with invariants (`state.py`): 10–100% clamp, Interactive
      Mode requires a target, new target starts at 100% / Move Mode
- [x] Backend bundle + factory (`windows/__init__.py`)
- [x] Controller/UI split so no Tk call happens on a worker thread

## Phase 2 — Implementation (done)

- [x] FR-1 window enumeration: visible, titled, non-minimized, non-cloaked,
      excludes tool windows, shell surfaces and the app itself
- [x] FR-1 refresh/rescan and closed-target detection
- [x] FR-2 opacity 10–100% via `WS_EX_LAYERED` + `SetLayeredWindowAttributes`
- [x] FR-2 restore original extended style (only remove `WS_EX_LAYERED` if the
      app added it)
- [x] FR-3 Move Mode / FR-4 Interactive Mode toggle
- [x] FR-4 movement lock via `EVENT_OBJECT_LOCATIONCHANGE` snap-back, input
      stays live
- [x] FR-5 global exit shortcut `Ctrl+Alt+Esc` + `Restore & Exit Mode` button
- [x] FR-5 restore on window close and on app exit
- [x] FR-6 status line, percentage, mode indicator, disabled states
- [x] DPI awareness and always-on-top toggle

## Phase 3 — Quality (done)

- [x] Unit tests for state invariants (12 cases)
- [x] Unit tests for controller side effects with a fake backend (15 cases)
- [x] Manual pass on Notepad: opacity, movement lock, unlock, restore
- [x] Manual pass on Chrome: opacity round-trip restores the exact
      extended style
- [x] Closing the target while Interactive Mode is active (integration check:
      unlock returns in well under a second, no hang)
- [x] Hotkey conflict path (a second registration fails and is reported)
- [x] Hotkey fires from a real `Ctrl+Alt+Esc` keypress
- [x] Window that was already layered before selection (Chrome keeps its
      layered style after restore)
- [ ] Manual test pass on windows with custom frames (VS Code, Spotify,
      Discord)
- [ ] Long-run check: opacity changes do not accumulate handles/styles
- [ ] Screenshot/GIF of the panel

## Phase 4 — Release (in progress)

- [x] Tool README with run instructions and limitations
- [x] Repository homepage README listing all tools
- [x] CI workflow running the unit tests on Windows and Linux
- [x] Version 0.1.0 declared in `opacity_control/__init__.py`
- [ ] Tagged release (`v0.1.0`)

## Verification log

| Check | Command / method | Result |
| --- | --- | --- |
| Unit tests | `python -m unittest discover -s tests -v` | 27 passed |
| GUI startup | `python main.py` for 4 s | Starts, no stderr |
| Opacity + style round-trip | Notepad and Chrome integration script | Alpha 128 at 50%, style restored |
| Movement lock | Drag simulation via `SetWindowPos` | Snaps back while locked, moves freely after unlock |
| Target destroyed while locked | Kill Notepad during lock | `is_available` false, unlock fast, no hang |
| Hotkey | Simulated `Ctrl+Alt+Esc`, then conflict attempt | Callback fires; conflict reported |


## Known gaps / Phase 2 scope from the PRD

- [ ] Tray icon for persistent access (currently: always-on-top panel +
      taskbar entry + global shortcut)
- [ ] Configurable shortcut (currently fixed at `Ctrl+Alt+Esc`)
- [ ] Movement lock on targets that ignore repositioning (rare; snap-back is
      best effort by design)
- [ ] Linux backend (`X11`/`Wayland`) — out of MVP scope
- [ ] Optional: remember last opacity/shortcut between runs

## Non-goals (do not add without a PRD change)

- Click-through mode
- Per-app profiles or automatic opacity rules
- Window tiling/snapping/pinning
- Multi-window transparency at once
