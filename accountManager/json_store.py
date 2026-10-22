"""Safe JSON persistence, backups, and restore for Chrome Account Manager.

Version 1.0 stores credentials as plaintext JSON. This module never pretends
otherwise: files are written atomically, corrupt files are preserved, and
backups carry an explicit plaintext marker in their manifest.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from logging_setup import get_logger

APP_ID = "chrome-account-manager"
APP_VERSION = "1.0.0"

log = get_logger("store")

DEFAULT_FILES = {
    "accounts.json": {"version": 1, "accounts": []},
    "profiles.json": {
        "version": 1,
        "profiles": [],
        "last_scan_at": None,
        "warnings": [],
    },
    "vault.json": {"version": 1, "credentials": []},
    "bookmarks.json": {"version": 1, "bookmarks": [], "last_scan_at": None},
}

DATA_FILES = tuple(DEFAULT_FILES.keys())


class StoreError(Exception):
    """Base error for storage problems."""


class CorruptFileError(StoreError):
    """Raised when a data file exists but cannot be used safely."""

    def __init__(self, name: str, detail: str, preserved_as: str | None = None):
        self.name = name
        self.detail = detail
        self.preserved_as = preserved_as
        message = f"{name} is not valid JSON data: {detail}."
        if preserved_as:
            message += f" The original file was preserved as {preserved_as}."
        message += " Fix or restore the file before continuing; it was not overwritten."
        super().__init__(message)


class BackupError(StoreError):
    """Raised when a backup cannot be created or restored safely."""


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class JsonStore:
    """Owns the data and backup directories and all file writes."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir).resolve()
        self.data_dir = self.base_dir / "data"
        self.backup_dir = self.base_dir / "backups"

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        log.info("Preparing data directory: %s", self.data_dir)
        log.info("Preparing backup directory: %s", self.backup_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._restrict_directory(self.data_dir)
        self._restrict_directory(self.backup_dir)
        for name, default in DEFAULT_FILES.items():
            self.ensure(name, default)
        log.info("Storage ready: %d data files checked", len(DEFAULT_FILES))

    def path(self, name: str) -> Path:
        if name not in DEFAULT_FILES:
            raise StoreError(f"Unknown data file: {name}")
        return self.data_dir / name

    def ensure(self, name: str, default: dict | None = None) -> bool:
        """Create a data file with defaults if it does not exist.

        Returns True when a new file was created. Existing files are never
        modified or truncated.
        """
        target = self.path(name)
        if target.exists():
            log.debug("Data file already exists: %s", target)
            return False
        payload = default if default is not None else DEFAULT_FILES[name]
        log.info("Creating missing data file: %s", target.name)
        self.write(name, payload)
        return True

    # ------------------------------------------------------------------
    # Reads and writes
    # ------------------------------------------------------------------

    def read(self, name: str) -> dict:
        target = self.path(name)
        log.debug("Reading data file: %s", target.name)
        if not target.exists():
            self.ensure(name)
        try:
            raw = target.read_bytes()
        except OSError as exc:
            log.error("Could not read %s: %s", name, exc)
            raise StoreError(f"Could not read {name}: {exc}") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            preserved = self._preserve_corrupt(name, raw)
            detail = getattr(exc, "msg", str(exc))
            line = getattr(exc, "lineno", None)
            if line:
                detail = f"{detail} (line {line})"
            log.error(
                "Unreadable JSON in %s; original preserved as %s",
                name,
                preserved or "(copy failed)",
            )
            raise CorruptFileError(name, detail, preserved) from exc

        if not isinstance(data, dict):
            preserved = self._preserve_corrupt(name, raw)
            log.error(
                "Invalid top-level structure in %s; original preserved as %s",
                name,
                preserved or "(copy failed)",
            )
            raise CorruptFileError(name, "the top-level value must be an object", preserved)
        return data

    def write(self, name: str, data: dict) -> None:
        target = self.path(name)
        log.info("Saving data file: %s", name)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{name}.", suffix=".tmp", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        except Exception:
            log.exception("Failed to write data file: %s", name)
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
            raise

    def _preserve_corrupt(self, name: str, raw: bytes) -> str:
        """Keep a byte-for-byte copy of an unreadable file before raising."""
        digest = _sha256_bytes(raw)[:8]
        stem = Path(name).stem
        preserved = self.data_dir / f"{stem}.corrupt-{digest}.json"
        if not preserved.exists():
            try:
                preserved.write_bytes(raw)
                log.warning("Preserved unreadable file as %s", preserved.name)
            except OSError as exc:
                log.error("Could not preserve unreadable file %s: %s", name, exc)
                return ""
        return preserved.name

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------

    def create_backup(self, label: str = "manual") -> dict:
        log.info("Creating backup: label=%s", label)
        safe_label = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-") or "manual"
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        candidate = self.backup_dir / f"backup_{stamp}_{safe_label}.zip"
        counter = 2
        while candidate.exists():
            candidate = self.backup_dir / f"backup_{stamp}_{safe_label}-{counter}.zip"
            counter += 1

        files: dict[str, dict] = {}
        payloads: dict[str, bytes] = {}
        for name in DATA_FILES:
            target = self.path(name)
            if not target.exists():
                self.ensure(name)
            raw = target.read_bytes()
            try:
                json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BackupError(
                    f"Refusing to back up because {name} is not valid JSON: {exc}. "
                    "Fix the file first."
                ) from exc
            payloads[name] = raw
            files[name] = {"sha256": _sha256_bytes(raw), "bytes": len(raw)}

        manifest = {
            "app": APP_ID,
            "app_version": APP_VERSION,
            "created_at": _now_iso(),
            "label": safe_label,
            "plaintext": True,
            "warning": (
                "This backup contains plaintext credentials. Store it somewhere "
                "private and delete it when it is no longer needed."
            ),
            "files": files,
        }

        tmp = candidate.with_suffix(".zip.tmp")
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))
                for name, raw in payloads.items():
                    archive.writestr(name, raw)
            os.replace(tmp, candidate)
        except Exception as exc:
            log.exception("Backup creation failed: label=%s", safe_label)
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise BackupError(f"Could not create backup: {exc}") from exc

        log.info("Backup created: %s (%d bytes)", candidate.name, candidate.stat().st_size)
        return {"name": candidate.name, "created_at": manifest["created_at"], "bytes": candidate.stat().st_size}

    def list_backups(self) -> list[dict]:
        items = []
        for entry in sorted(self.backup_dir.glob("backup_*.zip"), reverse=True):
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime)
                    .replace(microsecond=0)
                    .isoformat(),
                }
            )
        log.debug("Found %d backup archive(s)", len(items))
        return items

    def backup_path(self, name: str) -> Path:
        safe_name = Path(name).name
        if safe_name != name or not re.fullmatch(r"backup_[A-Za-z0-9_.-]+\.zip", name):
            raise BackupError("Invalid backup file name.")
        target = self.backup_dir / safe_name
        if not target.exists():
            raise BackupError("Backup not found.")
        return target

    def read_backup(self, path: str | os.PathLike[str]) -> dict[str, dict]:
        """Validate a backup archive and return parsed data files."""
        source = Path(path)
        try:
            with zipfile.ZipFile(source) as archive:
                names = set(archive.namelist())
                if "manifest.json" not in names:
                    raise BackupError("The archive has no manifest.json and is not a valid backup.")
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                if not isinstance(manifest, dict) or manifest.get("app") != APP_ID:
                    raise BackupError("The archive does not belong to Chrome Account Manager.")
                file_info = manifest.get("files")
                if not isinstance(file_info, dict):
                    raise BackupError("The backup manifest is missing its file list.")
                missing = [name for name in DATA_FILES if name not in names]
                if missing:
                    raise BackupError(
                        "The backup is incomplete; missing " + ", ".join(missing) + "."
                    )
                payloads: dict[str, dict] = {}
                for name in DATA_FILES:
                    info = archive.getinfo(name)
                    if info.file_size > 100 * 1024 * 1024:
                        raise BackupError(f"{name} inside the backup is too large.")
                    raw = archive.read(name)
                    expected = (file_info.get(name) or {}).get("sha256")
                    if expected and _sha256_bytes(raw) != expected:
                        raise BackupError(f"Checksum mismatch for {name}; the backup is damaged.")
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise BackupError(f"{name} inside the backup is not valid JSON.") from exc
                    if not isinstance(parsed, dict):
                        raise BackupError(f"{name} inside the backup has an invalid structure.")
                    payloads[name] = parsed
        except zipfile.BadZipFile as exc:
            raise BackupError("The selected file is not a valid backup archive.") from exc
        except OSError as exc:
            raise BackupError(f"Could not read the backup: {exc}") from exc
        return payloads

    def restore_backup(self, path: str | os.PathLike[str]) -> dict:
        log.info("Restoring backup: %s", Path(path).name)
        payloads = self.read_backup(path)
        # Never destroy the current state without a fresh safety copy.
        safety = self.create_backup(label="pre-restore")
        for name, data in payloads.items():
            self.write(name, data)
        log.info(
            "Backup restored: %s (safety copy: %s)",
            Path(path).name,
            safety["name"],
        )
        return {"restored_files": list(payloads.keys()), "safety_backup": safety["name"]}

    def import_backup_file(self, uploaded_path: str | os.PathLike[str]) -> dict:
        return self.restore_backup(uploaded_path)

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def _restrict_directory(self, directory: Path) -> None:
        """Best-effort restriction so only the current user can read data."""
        if os.name == "nt":
            try:
                user = getpass.getuser()
                subprocess.run(
                    [
                        "icacls",
                        str(directory),
                        "/inheritance:r",
                        "/grant:r",
                        f"{user}:(OI)(CI)F",
                    ],
                    check=False,
                    capture_output=True,
                    timeout=10,
                )
            except Exception as exc:
                # File permissions are defense in depth, not a hard dependency.
                log.warning("Could not restrict permissions on %s: %s", directory, exc)
            return
        try:
            os.chmod(directory, 0o700)
        except OSError as exc:
            log.warning("Could not restrict permissions on %s: %s", directory, exc)


def copy_stream_to_temp(stream, suffix: str = ".zip") -> Path:
    """Persist an uploaded stream to a temp file for validation.

    The caller is responsible for deleting the returned path.
    """
    fd, name = tempfile.mkstemp(prefix="cam-upload-", suffix=suffix)
    log.debug("Staging uploaded backup to %s", name)
    with os.fdopen(fd, "wb") as handle:
        shutil.copyfileobj(stream, handle)
    return Path(name)
