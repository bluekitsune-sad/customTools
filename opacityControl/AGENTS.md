# AGENTS.md — Opacity Control

Working notes for agents (and humans) changing this tool. Read this before
editing code.

## What this tool is

`opacityControl/` is a Windows desktop utility that makes a chosen application
window transparent while keeping it fully interactive, and can lock that
window's position. `PRD.md` is the source of truth for behaviour; this file is
the source of truth for how the code is organised.

The repository hosts several unrelated tools. Only touch the tool you were
asked about; `bgRemover/` is a separate Flask app with its own README.

## Hard rules

1. **Transparency is not click-through.** Never set `WS_EX_TRANSPARENT`, never
   disable input, never re-parent the target window. Losing interaction is a
   product failure, not a tradeoff.
2. **Always leave a way out.** Any new mode must be reversible from the panel
   *and* from the global exit shortcut (`Ctrl+Alt+Esc`).
3. **Restore what you changed.** Opacity and movement state must be undone on
   deactivate, target close, and application exit.
4. **Platform code stays behind `opacity_control/interfaces.py`.** Core state
   and UI must not import `win32`/ctypes directly.
5. **No new runtime dependencies without a reason.** The Windows backend uses
   `ctypes` and the standard library only (Tkinter for UI). Prefer keeping it
   that way so `python main.py` just works.
6. **No admin privileges.** The app must run as a normal user.

## Layout

```
opacityControl/
  main.py                      entry point (DPI setup, platform check)
  PRD.md                       product requirements
  README.md                    user-facing documentation
  TODO.md                      lifecycle checklist and known gaps
  opacity_control/
    state.py                   WindowState/Mode invariants (platform neutral)
    models.py                  WindowInfo value object
    interfaces.py              WindowProvider, Opacity/Movement/Hotkey protocols
    app.py                     OpacityApp controller (no widget code)
    ui/panel.py                Tkinter control panel
    windows/
      api.py                   ctypes bindings + Win32 helpers
      provider.py              window enumeration (FR-1)
      opacity.py               WS_EX_LAYERED alpha (FR-2)
      movement.py              position watcher / movement lock (FR-4)
      hotkey.py                RegisterHotKey exit shortcut (FR-5)
      __init__.py              Backend bundle + create_backend()
  tests/                       headless unit tests (no Win32 needed)
```

## Conventions

- Python 3.10+ syntax, `from __future__ import annotations`, type hints on
  public functions, dataclasses for value objects.
- UI text is English, sentence case, no exclamation marks.
- Keep `OpacityApp` free of Tkinter imports; keep widgets free of Win32 calls.
- Tkinter runs on the main thread. Background threads (hotkey, movement
  watcher) may only push events into `OpacityApp`'s queue.
- Any Win32 call that can fail must degrade gracefully: set a user-visible
  notice, never crash the panel.

## Commands

```powershell
# run the app (Windows)
python main.py

# tests (headless, no dependencies)
python -m unittest discover -s tests -v
```

## Definition of done for a change

- [ ] Behaviour matches the relevant `PRD.md` functional requirement.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `python main.py` starts, lists windows, and exits without leaving a
      window transparent or pinned.
- [ ] README/TODO updated if scope or limitations changed.
- [ ] No changes outside `opacityControl/` unless the task is repo-wide.
