"""Read account metadata from Chrome's Login Data without decrypting passwords.

Only ``origin_url``, ``signon_realm``, ``username_value``, and ``display_name``
are returned, plus a non-secret flag indicating whether a password blob exists.
The encrypted ``password_value`` content is never read or decrypted.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

from logging_setup import get_logger

log = get_logger("chrome_logins")


def read_chrome_logins(
    profile_dir: str | Path, profile_label: str = "profile"
) -> tuple[list[dict], list[str]]:
    """Return login metadata rows and warnings for one Chrome profile.

    The source database is opened read-only. If Chrome holds a lock that blocks
    the read, a temporary copy (including WAL/SHM files) is queried instead.
    """
    db_path = Path(profile_dir) / "Login Data"
    if not db_path.is_file():
        return [], []

    try:
        rows = _query_readonly(db_path)
    except sqlite3.Error as exc:
        log.warning(
            "Read-only Login Data query failed for %s (%s); trying a temporary copy",
            profile_label,
            type(exc).__name__,
        )
        rows = _query_copy(db_path, profile_label)
        if rows is None:
            return [], [
                f"Could not read Chrome login metadata for {profile_label}: "
                "the login database could not be read (often because Chrome is "
                "running). Close Chrome and try again."
            ]

    log.info(
        "Chrome login metadata read: profile=%s rows=%d encrypted_passwords=%d",
        profile_label,
        len(rows),
        sum(1 for row in rows if row["has_password_blob"]),
    )
    return rows, []


def _query_readonly(db_path: Path) -> list[dict]:
    connection = sqlite3.connect(
        f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=5
    )
    try:
        connection.row_factory = sqlite3.Row
        return _select_rows(connection)
    finally:
        connection.close()


def _query_copy(db_path: Path, profile_label: str) -> list[dict] | None:
    try:
        with tempfile.TemporaryDirectory(prefix="cam-login-") as temp_dir:
            copy_path = Path(temp_dir) / "Login Data"
            shutil.copy2(db_path, copy_path)
            for suffix in ("-wal", "-shm"):
                sidecar = db_path.with_name(db_path.name + suffix)
                if sidecar.exists():
                    shutil.copy2(
                        sidecar, copy_path.with_name(copy_path.name + suffix)
                    )
            connection = sqlite3.connect(copy_path, timeout=5)
            try:
                connection.row_factory = sqlite3.Row
                return _select_rows(connection)
            finally:
                connection.close()
    except (OSError, sqlite3.Error) as exc:
        log.warning(
            "Temporary Login Data copy failed for %s: %s",
            profile_label,
            type(exc).__name__,
        )
        return None


def _select_rows(connection: sqlite3.Connection) -> list[dict]:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(logins)").fetchall()
    }
    if "username_value" not in columns:
        return []

    def column(name: str, alias: str | None = None, fallback: str = "''") -> str:
        target = alias or name
        return f"{name} AS {target}" if name in columns else f"{fallback} AS {target}"

    has_password = (
        "CASE WHEN password_value IS NOT NULL AND length(password_value) > 0 "
        "THEN 1 ELSE 0 END AS has_password_blob"
        if "password_value" in columns
        else "0 AS has_password_blob"
    )
    select = ", ".join(
        [
            column("origin_url"),
            column("signon_realm"),
            column("username_value"),
            column("display_name"),
            has_password,
        ]
    )
    where = ["username_value IS NOT NULL", "TRIM(username_value) != ''"]
    if "blacklisted_by_user" in columns:
        where.append("COALESCE(blacklisted_by_user, 0) = 0")

    cursor = connection.execute(
        f"SELECT {select} FROM logins WHERE {' AND '.join(where)}"
    )

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in cursor.fetchall():
        username = str(row["username_value"] or "").strip()
        if not username:
            continue
        origin = str(row["origin_url"] or "").strip()
        realm = str(row["signon_realm"] or "").strip()
        key = ((origin or realm).lower(), username.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "origin_url": origin,
                "signon_realm": realm,
                "username": username,
                "display_name": str(row["display_name"] or "").strip(),
                "has_password_blob": bool(row["has_password_blob"]),
            }
        )
    return rows
