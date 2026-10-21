"""Program entry point."""

from __future__ import annotations

import ctypes
import sys


def _enable_dpi_awareness() -> None:
    """Keep the panel crisp on high-DPI displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def main() -> int:
    if sys.platform != "win32":
        print(
            "Opacity Control currently supports Windows only. "
            "See PRD.md section 6.2 for the planned Linux backend.",
            file=sys.stderr,
        )
        return 1

    _enable_dpi_awareness()

    from opacity_control.app import OpacityApp
    from opacity_control.ui import ControlPanel
    from opacity_control.windows import create_backend

    app = OpacityApp(create_backend())
    ControlPanel(app).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
