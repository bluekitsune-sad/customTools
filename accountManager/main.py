"""Entry point: python main.py

Starts a loopback-only Flask server and opens the dashboard in the default
browser. Press Ctrl+C in the terminal to stop it.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from account_manager import AccountManager
from json_store import (
    APP_VERSION,
    DATA_FILES,
    CorruptFileError,
    JsonStore,
    StoreError,
)
from logging_setup import configure_logging, get_logger
from scanner import ChromeScanner
from server import create_app

BASE_DIR = Path(__file__).resolve().parent
log = get_logger("main")


def find_free_port(preferred: int) -> int:
    for port in range(preferred, min(preferred + 50, 65536)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free local port was found in the {preferred}-{preferred + 49} range.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chrome Account Manager - local account and bookmark inventory."
    )
    parser.add_argument("--port", type=int, default=8765, help="Preferred local port (default: 8765).")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the dashboard in the default browser.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = configure_logging(BASE_DIR)
    log.info("=" * 72)
    log.info("Chrome Account Manager %s starting", APP_VERSION)
    log.info("Python %s on %s", sys.version.split()[0], sys.platform)
    log.info("Log file: %s", log_path or "console only (file logging unavailable)")

    store = JsonStore(BASE_DIR)
    try:
        store.ensure_dirs()
    except StoreError as exc:
        log.exception("Could not prepare the data directory")
        print(f"[error] Could not prepare the data directory: {exc}")
        return 1

    # Fail loudly on damaged data instead of starting with an empty inventory.
    for name in DATA_FILES:
        try:
            store.read(name)
        except CorruptFileError as exc:
            log.error("Refusing to start; unreadable data file: %s", name)
            print("[error] Refusing to start because a data file is unreadable.")
            print(f"        {exc}")
            print(f"        Data directory: {store.data_dir}")
            return 1
        except StoreError as exc:
            log.exception("Could not read %s during startup", name)
            print(f"[error] {exc}")
            return 1

    manager = AccountManager(store, ChromeScanner())
    app = create_app(manager)

    try:
        port = find_free_port(max(1, min(args.port, 65535)))
    except RuntimeError as exc:
        log.error("Port selection failed: %s", exc)
        print(f"[error] {exc}")
        return 1

    url = f"http://127.0.0.1:{port}/"
    log.info("Data directory: %s", store.data_dir)
    log.info("Backup directory: %s", store.backup_dir)
    log.info("Dashboard URL: %s", url)
    log.warning("Plaintext credential mode is enabled (Version 1.0)")
    print("")
    print(f"  Chrome Account Manager {APP_VERSION}")
    print(f"  Dashboard : {url}")
    print(f"  Data      : {store.data_dir}")
    print(f"  Backups   : {store.backup_dir}")
    if log_path:
        print(f"  Logs      : {log_path}")
    print("")
    print("  WARNING: Version 1.0 stores credentials as PLAINTEXT JSON.")
    print("           Anyone who can read this folder can read the passwords.")
    print("           The server only listens on 127.0.0.1.")
    print("")
    print("  Press Ctrl+C to stop.")
    print("")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        app.run(
            host="127.0.0.1",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        log.info("Shutdown requested with Ctrl+C")
    except OSError as exc:
        log.exception("Could not start the local server")
        print(f"[error] Could not start the local server: {exc}")
        return 1

    log.info("Chrome Account Manager stopped")
    print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
