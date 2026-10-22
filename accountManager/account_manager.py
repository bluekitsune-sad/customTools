"""Account, credential, profile, and bookmark business logic."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime
from urllib.parse import urlsplit

from json_store import CorruptFileError, JsonStore
from logging_setup import get_logger
from scanner import ChromeScanner

CATEGORIES = ("Personal", "Work", "Social", "Finance", "Other")
log = get_logger("manager")
MAX_TEXT = {
    "service": 160,
    "website": 2048,
    "email": 320,
    "username": 160,
    "password": 1024,
    "notes": 5000,
    "category": 40,
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROFILE_ID_RE = re.compile(r"^prof_[a-f0-9]{12}$")


class ValidationError(Exception):
    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_service(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def normalize_url_for_match(value: str) -> str:
    if not value:
        return ""
    candidate = value.strip().lower()
    candidate = re.sub(r"^[a-z][a-z0-9+.-]*://", "", candidate)
    candidate = candidate.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    if candidate.startswith("www."):
        candidate = candidate[4:]
    return candidate


def normalize_website_input(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*://", value, re.IGNORECASE):
        return value
    if value.startswith(("mailto:", "tel:")):
        return value
    return "https://" + value


class AccountManager:
    def __init__(self, store: JsonStore, scanner: ChromeScanner | None = None):
        self.store = store
        self.scanner = scanner or ChromeScanner()

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _accounts_data(self) -> dict:
        data = self.store.read("accounts.json")
        if not isinstance(data.get("accounts"), list):
            raise CorruptFileError(
                "accounts.json", "the 'accounts' value must be a list"
            )
        return data

    def _vault_data(self) -> dict:
        data = self.store.read("vault.json")
        if not isinstance(data.get("credentials"), list):
            raise CorruptFileError(
                "vault.json", "the 'credentials' value must be a list"
            )
        return data

    def _profiles_data(self) -> dict:
        data = self.store.read("profiles.json")
        if not isinstance(data.get("profiles"), list):
            raise CorruptFileError(
                "profiles.json", "the 'profiles' value must be a list"
            )
        return data

    def _bookmarks_data(self) -> dict:
        data = self.store.read("bookmarks.json")
        if not isinstance(data.get("bookmarks"), list):
            raise CorruptFileError(
                "bookmarks.json", "the 'bookmarks' value must be a list"
            )
        return data

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[dict]:
        return list(self._accounts_data()["accounts"])

    def get_account(self, account_id: str) -> dict | None:
        for account in self.list_accounts():
            if account.get("id") == account_id:
                return account
        return None

    def create_account(self, payload: dict, allow_duplicates: bool = False) -> dict:
        data = self._accounts_data()
        cleaned, password = self._clean_payload(payload)
        duplicates = self.find_duplicates(cleaned)
        if duplicates and not allow_duplicates:
            log.warning(
                "Duplicate warning while creating account: service=%r matches=%d",
                cleaned["service"],
                len(duplicates),
            )
            raise DuplicateAccounts(duplicates)

        account = {
            "id": "acc_" + uuid.uuid4().hex[:12],
            "service": cleaned["service"],
            "website": cleaned["website"],
            "email": cleaned["email"],
            "username": cleaned["username"],
            "credential_id": None,
            "chrome_profiles": cleaned["chrome_profiles"],
            "category": cleaned["category"],
            "notes": cleaned["notes"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "verified_at": None,
        }
        if password is not None:
            credential = self._create_credential(password)
            account["credential_id"] = credential["id"]

        data["accounts"].append(account)
        self.store.write("accounts.json", data)
        log.info(
            "Account created: id=%s service=%r profiles=%d has_password=%s",
            account["id"],
            account["service"],
            len(account["chrome_profiles"]),
            bool(account["credential_id"]),
        )
        return account

    def update_account(
        self, account_id: str, payload: dict, allow_duplicates: bool = False
    ) -> dict:
        data = self._accounts_data()
        account = next(
            (item for item in data["accounts"] if item.get("id") == account_id), None
        )
        if account is None:
            log.warning("Update requested for missing account: id=%s", account_id)
            raise KeyError(account_id)

        cleaned, password = self._clean_payload(payload)
        duplicates = self.find_duplicates(cleaned, exclude_id=account_id)
        if duplicates and not allow_duplicates:
            log.warning(
                "Duplicate warning while updating account: id=%s service=%r matches=%d",
                account_id,
                cleaned["service"],
                len(duplicates),
            )
            raise DuplicateAccounts(duplicates)

        account.update(
            {
                "service": cleaned["service"],
                "website": cleaned["website"],
                "email": cleaned["email"],
                "username": cleaned["username"],
                "chrome_profiles": cleaned["chrome_profiles"],
                "category": cleaned["category"],
                "notes": cleaned["notes"],
                "updated_at": now_iso(),
            }
        )

        if payload.get("clear_password"):
            self._delete_credential(account.get("credential_id"))
            account["credential_id"] = None
            log.info("Password cleared for account: id=%s", account_id)
        elif password is not None:
            account["credential_id"] = self._set_credential(
                account.get("credential_id"), password
            )
            log.info("Password saved for account: id=%s", account_id)

        self.store.write("accounts.json", data)
        log.info(
            "Account updated: id=%s service=%r profiles=%d has_password=%s",
            account["id"],
            account["service"],
            len(account["chrome_profiles"]),
            bool(account["credential_id"]),
        )
        return account

    def delete_account(self, account_id: str) -> bool:
        data = self._accounts_data()
        target = next(
            (item for item in data["accounts"] if item.get("id") == account_id), None
        )
        if target is None:
            log.warning("Delete requested for missing account: id=%s", account_id)
            return False
        data["accounts"] = [item for item in data["accounts"] if item.get("id") != account_id]
        self.store.write("accounts.json", data)
        credential_id = target.get("credential_id")
        if credential_id and not any(
            item.get("credential_id") == credential_id for item in data["accounts"]
        ):
            self._delete_credential(credential_id)
        log.info("Account deleted: id=%s service=%r", account_id, target.get("service"))
        return True

    def find_duplicates(
        self, candidate: dict, exclude_id: str | None = None
    ) -> list[dict]:
        service = normalize_service(candidate.get("service", ""))
        website = normalize_url_for_match(candidate.get("website", ""))
        email = (candidate.get("email") or "").strip().lower()
        username = (candidate.get("username") or "").strip().lower()

        matches: list[dict] = []
        for account in self.list_accounts():
            if account.get("id") == exclude_id:
                continue
            reasons = []
            if service and service == normalize_service(account.get("service", "")):
                reasons.append("Same service name")
            if website and website == normalize_url_for_match(account.get("website", "")):
                reasons.append("Same website")
            if email and email == (account.get("email") or "").strip().lower():
                reasons.append("Same email")
            if username and username == (account.get("username") or "").strip().lower():
                reasons.append("Same username")
            if reasons:
                matches.append(
                    {
                        "id": account.get("id"),
                        "service": account.get("service", ""),
                        "email": account.get("email", ""),
                        "username": account.get("username", ""),
                        "website": account.get("website", ""),
                        "reasons": reasons,
                    }
                )
        return matches

    def _clean_payload(self, payload: dict) -> tuple[dict, str | None]:
        if not isinstance(payload, dict):
            raise ValidationError("The request body must be an object.")

        service = self._text(payload.get("service"), "service", required=True)
        email = self._text(payload.get("email"), "email")
        username = self._text(payload.get("username"), "username")
        website = normalize_website_input(self._text(payload.get("website"), "website"))
        notes = self._text(payload.get("notes"), "notes")

        if not email and not username:
            raise ValidationError(
                "Provide at least one of email or username.", field="email"
            )
        if email and not EMAIL_RE.match(email):
            raise ValidationError("Enter a valid email address.", field="email")
        if len(website) > MAX_TEXT["website"]:
            raise ValidationError("Website is too long.", field="website")

        category = self._text(payload.get("category"), "category") or "Other"
        category = next(
            (item for item in CATEGORIES if item.lower() == category.lower()), "Other"
        )

        raw_profiles = payload.get("chrome_profiles", [])
        raw_ids = payload.get("chrome_profile_ids", [])
        profiles: list[str] = []
        profile_rows = self.list_profiles()
        by_id = {
            profile.get("id"): profile
            for profile in profile_rows
            if isinstance(profile.get("id"), str)
        }
        by_name = {}
        for profile in profile_rows:
            for key in (profile.get("display_name"), profile.get("dir")):
                if isinstance(key, str) and key.strip():
                    by_name.setdefault(key.strip().lower(), profile.get("id"))

        def add_profile(value) -> None:
            if not isinstance(value, str):
                return
            value = value.strip()
            if not value:
                return
            if PROFILE_ID_RE.match(value):
                if value not in profiles:
                    profiles.append(value)
                return
            resolved = by_name.get(value.lower())
            if resolved and resolved not in profiles:
                profiles.append(resolved)

        if isinstance(raw_ids, list):
            for value in raw_ids:
                add_profile(value)
        if isinstance(raw_profiles, list):
            for value in raw_profiles:
                add_profile(value)
        elif raw_profiles is not None:
            raise ValidationError("Chrome profiles must be a list.", field="chrome_profiles")

        password = payload.get("password")
        if password is not None:
            if not isinstance(password, str):
                raise ValidationError("Password must be text.", field="password")
            if len(password) > MAX_TEXT["password"]:
                raise ValidationError("Password is too long.", field="password")
            if password == "":
                password = None

        cleaned = {
            "service": service,
            "website": website,
            "email": email,
            "username": username,
            "chrome_profiles": profiles,
            "category": category,
            "notes": notes,
        }
        return cleaned, password

    @staticmethod
    def _text(value, field: str, required: bool = False) -> str:
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValidationError(f"{field.capitalize()} must be text.", field=field)
        value = value.strip()
        if required and not value:
            raise ValidationError("Service name is required.", field=field)
        if len(value) > MAX_TEXT[field]:
            raise ValidationError(f"{field.capitalize()} is too long.", field=field)
        if "\x00" in value:
            raise ValidationError(f"{field.capitalize()} contains invalid characters.", field=field)
        return value

    # ------------------------------------------------------------------
    # Credentials (plaintext in Version 1.0 by design)
    # ------------------------------------------------------------------

    def credential_ids_with_password(self) -> set[str]:
        return {
            credential.get("id")
            for credential in self._vault_data()["credentials"]
            if credential.get("id") and credential.get("password")
        }

    def has_password(self, account: dict) -> bool:
        credential_id = account.get("credential_id")
        if not credential_id:
            return False
        return credential_id in self.credential_ids_with_password()

    def get_password(self, account_id: str) -> str | None:
        log.debug("Password lookup requested: account=%s", account_id)
        account = self.get_account(account_id)
        if not account or not account.get("credential_id"):
            return None
        for credential in self._vault_data()["credentials"]:
            if credential.get("id") == account["credential_id"]:
                value = credential.get("password")
                return value if isinstance(value, str) else None
        return None

    def _create_credential(self, password: str) -> dict:
        data = self._vault_data()
        credential = {"id": "cred_" + uuid.uuid4().hex[:12], "password": password}
        data["credentials"].append(credential)
        self.store.write("vault.json", data)
        log.info("Credential created: id=%s", credential["id"])
        return credential

    def _set_credential(self, credential_id: str | None, password: str) -> str:
        data = self._vault_data()
        if credential_id:
            for credential in data["credentials"]:
                if credential.get("id") == credential_id:
                    credential["password"] = password
                    self.store.write("vault.json", data)
                    log.info("Credential updated: id=%s", credential_id)
                    return credential_id
        credential = {"id": "cred_" + uuid.uuid4().hex[:12], "password": password}
        data["credentials"].append(credential)
        self.store.write("vault.json", data)
        log.info("Credential created: id=%s", credential["id"])
        return credential["id"]

    def _delete_credential(self, credential_id: str | None) -> None:
        if not credential_id:
            return
        data = self._vault_data()
        filtered = [
            item for item in data["credentials"] if item.get("id") != credential_id
        ]
        if len(filtered) != len(data["credentials"]):
            data["credentials"] = filtered
            self.store.write("vault.json", data)
            log.info("Credential deleted: id=%s", credential_id)
        else:
            log.debug("Credential delete skipped; id not found: %s", credential_id)

    # ------------------------------------------------------------------
    # Profiles and bookmarks
    # ------------------------------------------------------------------

    def list_profiles(self) -> list[dict]:
        return list(self._profiles_data()["profiles"])

    def profile_document(self) -> dict:
        return self._profiles_data()

    def profile_map(self) -> dict[str, dict]:
        return {
            profile.get("id"): profile
            for profile in self.list_profiles()
            if profile.get("id")
        }

    def list_bookmarks(self) -> list[dict]:
        return list(self._bookmarks_data()["bookmarks"])

    def delete_bookmark(self, bookmark_id: str) -> bool:
        data = self._bookmarks_data()
        filtered = [item for item in data["bookmarks"] if item.get("id") != bookmark_id]
        if len(filtered) == len(data["bookmarks"]):
            log.warning("Delete requested for missing bookmark: id=%s", bookmark_id)
            return False
        data["bookmarks"] = filtered
        self.store.write("bookmarks.json", data)
        log.info("Bookmark removed from local index: id=%s", bookmark_id)
        return True

    def scan_and_store(self) -> dict:
        """Run a full scan and merge profiles/bookmarks without touching accounts."""
        log.info("Scan merge started; accounts are not read or modified by scans")
        result = self.scanner.scan()
        result["accounts_created"] = 0
        result["accounts_note"] = (
            "Chrome scans index profiles and bookmarks only. They never read saved "
            "Chrome passwords or create account records."
        )
        log.info(
            "Scan result received: profiles=%d bookmarks=%d warnings=%d",
            len(result["profiles"]),
            len(result["bookmarks"]),
            len(result["warnings"]),
        )

        profiles_doc = self._profiles_data()
        bookmarks_doc = self._bookmarks_data()

        # Never erase a working index just because a scan found nothing. This
        # can happen if Chrome's data directory is temporarily unavailable.
        if not result["profiles"] and (
            profiles_doc.get("profiles") or bookmarks_doc.get("bookmarks")
        ):
            message = (
                "No Chrome profiles were discovered during this scan; the existing "
                "profile and bookmark index was kept. Check that Chrome is installed "
                "for this Windows user, then scan again."
            )
            result["warnings"].append(message)
            profiles_doc["warnings"] = result["warnings"]
            profiles_doc["chrome_running"] = result["chrome_running"]
            profiles_doc["user_data_dirs"] = result["user_data_dirs"]
            self.store.write("profiles.json", profiles_doc)
            result["profile_count"] = len(profiles_doc.get("profiles") or [])
            result["bookmark_count"] = len(bookmarks_doc.get("bookmarks") or [])
            log.warning(
                "Empty scan result; kept existing index (profiles=%d bookmarks=%d)",
                result["profile_count"],
                result["bookmark_count"],
            )
            log.info(
                "Scan finished without account changes: accounts_created=0 "
                "profiles=%d bookmarks=%d",
                result["profile_count"],
                result["bookmark_count"],
            )
            return result

        profiles_doc["profiles"] = result["profiles"]
        profiles_doc["last_scan_at"] = result["scanned_at"]
        profiles_doc["warnings"] = result["warnings"]
        profiles_doc["chrome_running"] = result["chrome_running"]
        profiles_doc["user_data_dirs"] = result["user_data_dirs"]
        self.store.write("profiles.json", profiles_doc)
        log.info("Profile index saved: profiles=%d", len(result["profiles"]))

        existing_by_profile: dict[str, list[dict]] = {}
        for bookmark in bookmarks_doc["bookmarks"]:
            existing_by_profile.setdefault(bookmark.get("profile_id"), []).append(bookmark)
        scanned_by_profile: dict[str, list[dict]] = {}
        for bookmark in result["bookmarks"]:
            scanned_by_profile.setdefault(bookmark.get("profile_id"), []).append(bookmark)

        merged: list[dict] = []
        seen_ids: set[str] = set()
        for profile in result["profiles"]:
            profile_id = profile["id"]
            if profile_id in result["read_ok_profile_ids"]:
                source = scanned_by_profile.get(profile_id, [])
            else:
                # Preserve prior bookmarks when the file could not be read.
                source = existing_by_profile.get(profile_id, [])
            for bookmark in source:
                if bookmark.get("id") in seen_ids:
                    continue
                bookmark = dict(bookmark)
                bookmark["profile_name"] = profile["display_name"]
                seen_ids.add(bookmark.get("id"))
                merged.append(bookmark)
        bookmarks_doc["bookmarks"] = merged
        bookmarks_doc["last_scan_at"] = result["scanned_at"]
        self.store.write("bookmarks.json", bookmarks_doc)

        result["bookmark_count"] = len(merged)
        result["profile_count"] = len(result["profiles"])
        log.info(
            "Bookmark index saved: bookmarks=%d (readable profiles=%d, "
            "profiles preserving previous bookmarks=%d)",
            len(merged),
            len(result["read_ok_profile_ids"]),
            sum(
                1
                for profile in result["profiles"]
                if profile["id"] not in result["read_ok_profile_ids"]
            ),
        )
        log.info(
            "Scan finished without account changes: accounts_created=0 "
            "profiles=%d bookmarks=%d",
            result["profile_count"],
            result["bookmark_count"],
        )
        return result

    # ------------------------------------------------------------------
    # Import and export
    # ------------------------------------------------------------------

    def preview_import(self, content: str) -> dict:
        records = self._parse_import_content(content)
        log.info("Import preview started: records=%d", len(records))
        preview = []
        for index, raw in enumerate(records):
            safe_raw = {}
            if isinstance(raw, dict):
                for field in ("service", "website", "email", "username", "category", "notes"):
                    value = raw.get(field)
                    safe_raw[field] = value if isinstance(value, str) else ""
                safe_raw["has_password"] = bool(
                    isinstance(raw.get("password"), str) and raw.get("password")
                )
            item = {
                "index": index,
                "raw": safe_raw,
                "valid": True,
                "error": None,
                "duplicates": [],
            }
            if not isinstance(raw, dict):
                item.update(valid=False, error="Record is not an object.")
                preview.append(item)
                continue
            try:
                cleaned, _password = self._clean_payload(raw)
                item["duplicates"] = self.find_duplicates(cleaned)
            except ValidationError as exc:
                item.update(valid=False, error=exc.message)
            preview.append(item)
        valid = sum(1 for item in preview if item["valid"])
        log.info(
            "Import preview finished: records=%d valid=%d invalid=%d",
            len(preview),
            valid,
            len(preview) - valid,
        )
        return {"records": preview, "total": len(preview)}

    def commit_import(self, content: str, indexes: list[int]) -> dict:
        records = self._parse_import_content(content)
        log.info("Import commit started: selected=%d", len(indexes))
        imported = 0
        skipped = 0
        errors = []
        for index in indexes:
            if not isinstance(index, int) or index < 0 or index >= len(records):
                continue
            raw = records[index]
            if not isinstance(raw, dict):
                skipped += 1
                errors.append(f"Record {index + 1} is not an object.")
                continue
            try:
                self.create_account(raw, allow_duplicates=True)
                imported += 1
            except ValidationError as exc:
                skipped += 1
                errors.append(f"Record {index + 1}: {exc.message}")
        log.info(
            "Import commit finished: imported=%d skipped=%d errors=%d",
            imported,
            skipped,
            len(errors),
        )
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def _parse_import_content(self, content: str) -> list:
        if not isinstance(content, str) or not content.strip():
            raise ValidationError("The import file is empty.")
        if len(content) > 5 * 1024 * 1024:
            raise ValidationError("The import file is too large (limit 5 MB).")

        stripped = content.lstrip("\ufeff \t\r\n")
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"The import file is not valid JSON: {exc.msg}."
                ) from exc
            if isinstance(parsed, dict):
                records = parsed.get("accounts")
                if not isinstance(records, list):
                    raise ValidationError(
                        "The import file must contain an 'accounts' list."
                    )
                return records
            if isinstance(parsed, list):
                return parsed
            raise ValidationError("The import file must be a JSON object or list.")

        return self._parse_chrome_csv(stripped)

    def _parse_chrome_csv(self, content: str) -> list:
        """Parse Chrome's official password export (CSV) into account records."""
        reader = csv.DictReader(io.StringIO(content))
        headers = {
            (name or "").strip().lower(): name for name in (reader.fieldnames or [])
        }
        missing = {"name", "url", "username", "password"} - set(headers)
        if missing:
            raise ValidationError(
                "The import file must be JSON or Chrome's password CSV "
                "(name, url, username, password, note)."
            )

        records: list[dict] = []
        for row in reader:
            normalized = {
                key: (row.get(original) or "") for key, original in headers.items()
            }
            name = normalized.get("name", "").strip()
            url = normalized.get("url", "").strip()
            username = normalized.get("username", "").strip()
            password = normalized.get("password", "")
            note = normalized.get("note", "")
            if not any((name, url, username, password, note)):
                continue
            if not name:
                name = urlsplit(url).hostname or "Imported account"
            email = username if EMAIL_RE.match(username) else ""
            records.append(
                {
                    "service": name,
                    "website": url,
                    "email": email,
                    "username": "" if email else username,
                    "password": password or None,
                    "notes": note,
                    "category": "Other",
                    "chrome_profiles": [],
                }
            )
        if not records:
            raise ValidationError("No account records were found in the CSV file.")
        log.info("Parsed Chrome CSV export: records=%d", len(records))
        return records

    def export_accounts(self, include_passwords: bool = False) -> dict:
        profiles = self.profile_map()
        accounts = []
        for account in self.list_accounts():
            profile_ids = [
                pid for pid in account.get("chrome_profiles", []) if isinstance(pid, str)
            ]
            item = {
                "service": account.get("service", ""),
                "website": account.get("website", ""),
                "email": account.get("email", ""),
                "username": account.get("username", ""),
                "category": account.get("category", "Other"),
                "notes": account.get("notes", ""),
                "chrome_profiles": [
                    (profiles.get(pid) or {}).get("display_name", pid)
                    for pid in profile_ids
                ],
                "chrome_profile_ids": profile_ids,
            }
            if include_passwords:
                item["password"] = self.get_password(account.get("id")) or ""
            accounts.append(item)

        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        payload = {
            "version": 1,
            "exported_at": now_iso(),
            "includes_passwords": bool(include_passwords),
            "accounts": accounts,
        }
        if include_passwords:
            log.warning("Export prepared WITH plaintext passwords: accounts=%d", len(accounts))
        else:
            log.info("Export prepared without passwords: accounts=%d", len(accounts))
        return {
            "filename": f"chrome-account-manager-export-{stamp}.json",
            "content": json.dumps(payload, indent=2, ensure_ascii=False),
            "count": len(accounts),
            "includes_passwords": bool(include_passwords),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        profiles_doc = self._profiles_data()
        bookmarks_doc = self._bookmarks_data()
        accounts = self.list_accounts()
        services = {
            normalize_service(account.get("service", ""))
            for account in accounts
            if account.get("service")
        }
        return {
            "accounts": len(accounts),
            "profiles": len(profiles_doc["profiles"]),
            "services": len(services),
            "bookmarks": len(bookmarks_doc["bookmarks"]),
            "last_scan_at": profiles_doc.get("last_scan_at"),
            "last_bookmark_scan_at": bookmarks_doc.get("last_scan_at"),
        }


class DuplicateAccounts(ValidationError):
    """Raised when a save would create a likely duplicate."""

    def __init__(self, duplicates: list[dict]):
        self.duplicates = duplicates
        super().__init__("Possible duplicate account found.", field=None)
