"""Read-only Chrome profile and bookmark discovery for Windows.

The scanner never modifies Chrome files. It reads ``Local State``,
``Preferences``, and ``Bookmarks`` when they are accessible, and reports
warnings instead of guessing when they are not.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from logging_setup import get_logger

CHROME_EPOCH = datetime(1601, 1, 1)
log = get_logger("scanner")

# Channel label and expected "User Data" directory.
CHROME_CHANNELS = (
    ("Chrome", ("Google", "Chrome", "User Data")),
    ("Chrome Beta", ("Google", "Chrome Beta", "User Data")),
    ("Chrome Dev", ("Google", "Chrome Dev", "User Data")),
    ("Chrome Canary", ("Google", "Chrome SxS", "User Data")),
    ("Chromium", ("Chromium", "User Data")),
)

# Chrome bookkeeping directories that are never user profiles.
NON_PROFILE_DIRS = {
    "system profile",
    "guest profile",
    "snapshots",
    "crashpad",
    "shadercache",
    "grshadercache",
    "component crx cache",
    "default cache",
    "browsermetrics",
    "safe browsing",
    "optimizationhints",
    "origin tri bounds",
}

BOOKMARK_ROOT_NAMES = {
    "bookmark_bar": "Bookmarks Bar",
    "other": "Other Bookmarks",
    "synced": "Mobile Bookmarks",
}

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.debug("Could not read Chrome JSON file %s: %s", path, exc)
        return None


def _chrome_user_data_dirs() -> list[dict]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return []
    base = Path(local_app_data)
    found = []
    for channel, parts in CHROME_CHANNELS:
        candidate = base.joinpath(*parts)
        if candidate.is_dir():
            found.append({"channel": channel, "path": candidate})
    return found


def is_chrome_running() -> bool:
    """Best-effort check used only to warn about inconsistent reads."""
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=_CREATE_NO_WINDOW,
        )
        output = (completed.stdout or "").lower()
        running = "chrome.exe" in output
        log.debug("Chrome process check: running=%s", running)
        return running
    except Exception as exc:
        log.debug("Chrome process check failed: %s", exc)
        return False


def _profile_id(user_data_dir: Path, directory_name: str) -> str:
    digest = hashlib.sha1(
        f"{str(user_data_dir).lower()}|{directory_name}".encode("utf-8")
    ).hexdigest()
    return "prof_" + digest[:12]


def _profile_dirs(user_data_dir: Path, info_cache: dict) -> list[str]:
    names = set()
    try:
        entries = list(user_data_dir.iterdir())
    except OSError as exc:
        log.warning("Could not list Chrome user data directory %s: %s", user_data_dir, exc)
        return []
    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        lowered = entry.name.lower()
        if lowered in NON_PROFILE_DIRS:
            continue
        if (entry / "Preferences").is_file() or entry.name in info_cache:
            names.add(entry.name)
    result = sorted(names, key=lambda value: (value != "Default", value.lower()))
    log.debug("Found %d profile directories in %s", len(result), user_data_dir)
    return result


def _google_email_from_preferences(preferences: dict) -> str | None:
    account_info = preferences.get("account_info")
    if isinstance(account_info, list):
        for entry in account_info:
            if not isinstance(entry, dict):
                continue
            email = entry.get("email")
            if isinstance(email, str) and "@" in email:
                return email
    return None


def _bookmark_date_added(value) -> str | None:
    try:
        microseconds = int(value)
    except (TypeError, ValueError):
        return None
    if microseconds <= 0:
        return None
    try:
        return (CHROME_EPOCH + timedelta(microseconds=microseconds)).replace(
            microsecond=0
        ).isoformat()
    except (OverflowError, ValueError):
        return None


def _iter_bookmark_nodes(node, folder_path: str):
    """Yield URL bookmarks from a Chrome bookmark tree node."""
    if not isinstance(node, dict):
        return
    node_type = node.get("type")
    if node_type == "url":
        url = node.get("url")
        if not isinstance(url, str) or not url:
            return
        title = node.get("name")
        if not isinstance(title, str) or not title.strip():
            title = url
        yield {
            "title": title.strip(),
            "url": url.strip(),
            "folder": folder_path,
            "date_added": _bookmark_date_added(node.get("date_added")),
        }
        return
    children = node.get("children")
    if not isinstance(children, list):
        return
    name = node.get("name")
    next_folder = folder_path
    if node_type == "folder" and isinstance(name, str) and name.strip():
        next_folder = f"{folder_path}/{name.strip()}" if folder_path else name.strip()
    for child in children:
        yield from _iter_bookmark_nodes(child, next_folder)


def _read_profile_bookmarks(
    profile_dir: Path, profile_id: str, profile_name: str, scanned_at: str
) -> tuple[list[dict], bool, str | None]:
    """Return (bookmarks, read_ok, warning)."""
    path = profile_dir / "Bookmarks"
    if not path.exists():
        # No bookmark file is a valid state (fresh profile), not an error.
        log.debug("No Bookmarks file for profile %s", profile_name)
        return [], True, None

    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("Could not read bookmarks for %s: %s", profile_name, exc)
        return [], False, f"Could not read bookmarks for {profile_name}: {exc}"

    roots = data.get("roots") if isinstance(data, dict) else None
    if not isinstance(roots, dict):
        log.warning("Unexpected Bookmarks format for %s", profile_name)
        return [], False, f"The Bookmarks file for {profile_name} has an unexpected format."

    seen: set[str] = set()
    bookmarks: list[dict] = []
    for root_key, root_label in BOOKMARK_ROOT_NAMES.items():
        root_node = roots.get(root_key)
        if not isinstance(root_node, dict):
            continue
        # The root node itself is a folder (for example "Bookmarks bar").
        # Start at its children so the stored folder path is not duplicated.
        children = root_node.get("children")
        nodes = children if isinstance(children, list) else [root_node]
        for child in nodes:
            for item in _iter_bookmark_nodes(child, root_label):
                fingerprint = "\x1f".join(
                    [profile_id, item["url"], item["title"], item["folder"]]
                )
                bookmark_id = "bm_" + hashlib.sha1(
                    fingerprint.encode("utf-8")
                ).hexdigest()[:14]
                if bookmark_id in seen:
                    continue
                seen.add(bookmark_id)
                bookmarks.append(
                    {
                        "id": bookmark_id,
                        "profile_id": profile_id,
                        "profile_name": profile_name,
                        "title": item["title"],
                        "url": item["url"],
                        "folder": item["folder"],
                        "date_added": item["date_added"],
                        "scanned_at": scanned_at,
                    }
                )
    log.info("Read %d bookmark(s) from profile %s", len(bookmarks), profile_name)
    return bookmarks, True, None


class ChromeScanner:
    """Discovers Chrome profiles and bookmarks without modifying anything."""

    def scan(self) -> dict:
        scanned_at = _now_iso()
        log.info("Chrome scan started")
        chrome_running = is_chrome_running()
        warnings: list[str] = []
        if chrome_running:
            warnings.append(
                "Chrome appears to be running. Results may be incomplete; close Chrome "
                "and scan again if profiles or bookmarks are missing."
            )

        user_data_dirs = _chrome_user_data_dirs()
        if not user_data_dirs:
            warnings.append(
                "No Chrome or Chromium profile directory was found in LOCALAPPDATA."
            )
        log.info("Found %d Chrome data directories", len(user_data_dirs))
        for source in user_data_dirs:
            log.info("Chrome channel available: %s at %s", source["channel"], source["path"])

        profiles: list[dict] = []
        bookmarks: list[dict] = []
        read_ok_profile_ids: set[str] = set()

        for source in user_data_dirs:
            user_data_dir: Path = source["path"]
            channel: str = source["channel"]
            log.info("Scanning %s profile directory: %s", channel, user_data_dir)
            local_state = _read_json(user_data_dir / "Local State") or {}
            profile_section = local_state.get("profile")
            info_cache = {}
            if isinstance(profile_section, dict) and isinstance(
                profile_section.get("info_cache"), dict
            ):
                info_cache = profile_section["info_cache"]
            elif profile_section is not None and not isinstance(profile_section, dict):
                warnings.append(
                    f"{channel}: Local State has an unexpected profile section."
                )

            directories = _profile_dirs(user_data_dir, info_cache)
            if not directories:
                warnings.append(f"{channel}: no profile directories with Preferences were found.")

            for directory_name in directories:
                profile_dir = user_data_dir / directory_name
                info = info_cache.get(directory_name)
                if not isinstance(info, dict):
                    info = {}
                preferences = _read_json(profile_dir / "Preferences") or {}

                display_name = None
                pref_profile = preferences.get("profile")
                if isinstance(pref_profile, dict):
                    value = pref_profile.get("name")
                    if isinstance(value, str) and value.strip():
                        display_name = value.strip()
                if display_name is None:
                    value = info.get("name")
                    if isinstance(value, str) and value.strip():
                        display_name = value.strip()
                if display_name is None:
                    display_name = directory_name

                email = None
                for candidate in (info.get("user_name"), info.get("gaia_name")):
                    if isinstance(candidate, str) and "@" in candidate:
                        email = candidate
                        break
                if email is None:
                    email = _google_email_from_preferences(preferences)

                pid = _profile_id(user_data_dir, directory_name)
                profile_name = display_name
                log.info(
                    "Profile discovered: id=%s channel=%s dir=%s name=%r email_present=%s",
                    pid,
                    channel,
                    directory_name,
                    profile_name,
                    bool(email),
                )
                profile_bookmarks, read_ok, warning = _read_profile_bookmarks(
                    profile_dir, pid, profile_name, scanned_at
                )
                if read_ok:
                    read_ok_profile_ids.add(pid)
                elif warning:
                    warnings.append(warning)

                log.info(
                    "Profile scan finished: %s (%s) bookmarks=%d status=%s",
                    profile_name,
                    directory_name,
                    len(profile_bookmarks),
                    "ok" if read_ok else "bookmarks-unreadable",
                )
                bookmarks.extend(profile_bookmarks)
                profiles.append(
                    {
                        "id": pid,
                        "dir": directory_name,
                        "display_name": display_name,
                        "path": str(profile_dir),
                        "google_email": email,
                        "channel": channel,
                        "user_data_dir": str(user_data_dir),
                        "last_scanned_at": scanned_at,
                        "bookmark_count": len(profile_bookmarks),
                        "status": "ok" if read_ok else "bookmarks-unreadable",
                    }
                )

        for warning in warnings:
            log.warning("Scan warning: %s", warning)
        log.info(
            "Chrome scan finished: profiles=%d bookmarks=%d warnings=%d",
            len(profiles),
            len(bookmarks),
            len(warnings),
        )
        return {
            "scanned_at": scanned_at,
            "chrome_running": chrome_running,
            "warnings": warnings,
            "profiles": profiles,
            "bookmarks": bookmarks,
            "read_ok_profile_ids": read_ok_profile_ids,
            "user_data_dirs": [str(item["path"]) for item in user_data_dirs],
        }
