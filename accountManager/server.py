"""Flask application for the local Chrome Account Manager dashboard."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from account_manager import (
    CATEGORIES,
    AccountManager,
    DuplicateAccounts,
    ValidationError,
)
from json_store import (
    APP_VERSION,
    BackupError,
    CorruptFileError,
    StoreError,
    copy_stream_to_temp,
)
from logging_setup import get_logger

BASE_DIR = Path(__file__).resolve().parent
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
log = get_logger("server")


def _request_hostname() -> str:
    host = request.host or ""
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else host
    return host.rsplit(":", 1)[0]


def create_app(manager: AccountManager, csrf_token: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.update(
        CSRF_TOKEN=csrf_token or secrets.token_urlsafe(32),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    app.json.sort_keys = False
    store = manager.store

    # ------------------------------------------------------------------
    # Request guards and headers
    # ------------------------------------------------------------------

    @app.before_request
    def guard_requests():
        request.environ["cam.started_at"] = time.perf_counter()
        if _request_hostname() not in LOOPBACK_HOSTS:
            log.warning(
                "Rejected non-loopback request: %s %s host=%r",
                request.method,
                request.path,
                request.host,
            )
            return jsonify({"error": "This application only accepts loopback requests."}), 403
        if request.method not in SAFE_METHODS:
            supplied = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(supplied, app.config["CSRF_TOKEN"]):
                log.warning(
                    "Rejected write request with invalid CSRF token: %s %s",
                    request.method,
                    request.path,
                )
                return jsonify({"error": "Invalid or missing CSRF token. Reload the page."}), 403
            host_header = request.host or ""
            if host_header and _request_hostname() not in LOOPBACK_HOSTS:
                log.warning(
                    "Rejected cross-origin request: %s %s", request.method, request.path
                )
                return jsonify({"error": "Cross-origin request rejected."}), 403
        return None

    @app.after_request
    def add_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"

        started = request.environ.get("cam.started_at")
        if started is not None:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if request.path.startswith("/static/"):
                log.debug(
                    "%s %s -> %d (%.1f ms)",
                    request.method,
                    request.path,
                    response.status_code,
                    elapsed_ms,
                )
            else:
                log.info(
                    "%s %s -> %d (%.1f ms)",
                    request.method,
                    request.path,
                    response.status_code,
                    elapsed_ms,
                )
        return response

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def profile_label_map() -> dict[str, str]:
        """Profile labels that stay unambiguous when Chrome reuses names."""
        rows = manager.list_profiles()
        base_names = {
            profile.get("id"): (
                profile.get("display_name")
                or profile.get("dir")
                or "Profile"
            )
            for profile in rows
        }
        counts = Counter(base_names.values())
        labels = {}
        for profile in rows:
            profile_id = profile.get("id")
            if not profile_id:
                continue
            name = base_names[profile_id]
            if counts[name] > 1:
                labels[profile_id] = f"{name} · {profile.get('dir') or 'unknown'}"
            else:
                labels[profile_id] = name
        return labels

    def serialize_accounts(accounts: list[dict], labels: dict | None = None) -> list[dict]:
        labels = labels or profile_label_map()
        with_password = manager.credential_ids_with_password()
        output = []
        for account in accounts:
            profile_ids = [
                pid for pid in account.get("chrome_profiles", []) if isinstance(pid, str)
            ]
            output.append(
                {
                    "id": account.get("id"),
                    "service": account.get("service", ""),
                    "website": account.get("website", ""),
                    "email": account.get("email", ""),
                    "username": account.get("username", ""),
                    "chrome_profiles": profile_ids,
                    "profile_names": [
                        labels.get(pid, "Unknown profile") for pid in profile_ids
                    ],
                    "category": account.get("category", "Other"),
                    "notes": account.get("notes", ""),
                    "created_at": account.get("created_at"),
                    "updated_at": account.get("updated_at"),
                    "verified_at": account.get("verified_at"),
                    "has_password": account.get("credential_id") in with_password,
                }
            )
        return output

    def serialize_bookmarks(
        bookmarks: list[dict], labels: dict | None = None
    ) -> list[dict]:
        labels = labels or profile_label_map()
        output = []
        for bookmark in bookmarks:
            profile_id = bookmark.get("profile_id")
            output.append(
                {
                    "id": bookmark.get("id"),
                    "title": bookmark.get("title", ""),
                    "url": bookmark.get("url", ""),
                    "folder": bookmark.get("folder", ""),
                    "profile_id": profile_id,
                    "profile_name": labels.get(
                        profile_id, bookmark.get("profile_name", "Unknown profile")
                    ),
                    "date_added": bookmark.get("date_added"),
                    "scanned_at": bookmark.get("scanned_at"),
                }
            )
        return output

    def serialize_profiles(
        labels: dict | None = None,
    ) -> tuple[list[dict], dict]:
        accounts = manager.list_accounts()
        bookmarks = manager.list_bookmarks()
        profile_doc = manager.profile_document()
        labels = labels or profile_label_map()
        counts: dict[str, int] = {}
        for account in accounts:
            for pid in account.get("chrome_profiles", []):
                counts[pid] = counts.get(pid, 0) + 1
        bookmark_counts: dict[str, int] = {}
        for bookmark in bookmarks:
            pid = bookmark.get("profile_id")
            bookmark_counts[pid] = bookmark_counts.get(pid, 0) + 1
        output = []
        for profile in profile_doc["profiles"]:
            item = dict(profile)
            item["account_count"] = counts.get(profile.get("id"), 0)
            item["bookmark_count"] = bookmark_counts.get(profile.get("id"), 0)
            item["label"] = labels.get(profile.get("id"), profile.get("display_name"))
            output.append(item)
        return output, profile_doc

    def state_payload() -> dict:
        labels = profile_label_map()
        profiles, profile_doc = serialize_profiles(labels)
        return {
            "version": APP_VERSION,
            "accounts": serialize_accounts(manager.list_accounts(), labels),
            "bookmarks": serialize_bookmarks(manager.list_bookmarks(), labels),
            "profiles": profiles,
            "stats": manager.stats(),
            "categories": list(CATEGORIES),
            "warnings": profile_doc.get("warnings") or [],
            "chrome_running": bool(profile_doc.get("chrome_running")),
            "last_scan_at": profile_doc.get("last_scan_at"),
            "storage": {
                "plaintext_credentials": True,
                "data_dir": str(store.data_dir),
                "backup_dir": str(store.backup_dir),
                "permission_note": (
                    "Data and backup folders are restricted to the current Windows "
                    "user on a best-effort basis."
                ),
            },
        }

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            csrf_token=app.config["CSRF_TOKEN"],
            app_version=APP_VERSION,
        )

    @app.get("/api/state")
    def api_state():
        return jsonify(state_payload())

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    @app.post("/api/accounts")
    def api_create_account():
        body = request.get_json(silent=True) or {}
        log.info("Create account request received")
        try:
            account = manager.create_account(
                body, allow_duplicates=bool(body.get("confirm_duplicate"))
            )
        except DuplicateAccounts as exc:
            log.warning("Create account rejected as duplicate: matches=%d", len(exc.duplicates))
            return (
                jsonify(
                    {
                        "error": "Possible duplicate account found.",
                        "duplicates": exc.duplicates,
                    }
                ),
                409,
            )
        return jsonify({"account": serialize_accounts([account])[0]}), 201

    @app.put("/api/accounts/<account_id>")
    def api_update_account(account_id: str):
        body = request.get_json(silent=True) or {}
        log.info("Update account request received: id=%s", account_id)
        try:
            account = manager.update_account(
                account_id, body, allow_duplicates=bool(body.get("confirm_duplicate"))
            )
        except KeyError:
            log.warning("Update account failed; not found: id=%s", account_id)
            return jsonify({"error": "Account not found."}), 404
        except DuplicateAccounts as exc:
            log.warning(
                "Update account rejected as duplicate: id=%s matches=%d",
                account_id,
                len(exc.duplicates),
            )
            return (
                jsonify(
                    {
                        "error": "Possible duplicate account found.",
                        "duplicates": exc.duplicates,
                    }
                ),
                409,
            )
        return jsonify({"account": serialize_accounts([account])[0]})

    @app.delete("/api/accounts/<account_id>")
    def api_delete_account(account_id: str):
        log.info("Delete account request received: id=%s", account_id)
        if not manager.delete_account(account_id):
            log.warning("Delete account failed; not found: id=%s", account_id)
            return jsonify({"error": "Account not found."}), 404
        return jsonify({"ok": True})

    @app.post("/api/accounts/<account_id>/reveal")
    def api_reveal_password(account_id: str):
        log.info("Password reveal requested: id=%s", account_id)
        if manager.get_account(account_id) is None:
            log.warning("Password reveal failed; account not found: id=%s", account_id)
            return jsonify({"error": "Account not found."}), 404
        password = manager.get_password(account_id)
        if not password:
            log.warning("Password reveal failed; no password saved: id=%s", account_id)
            return jsonify({"error": "No password is saved for this account."}), 404
        return jsonify({"password": password})

    @app.post("/api/accounts/duplicates")
    def api_check_duplicates():
        body = request.get_json(silent=True) or {}
        candidate = body.get("account") if isinstance(body.get("account"), dict) else body
        fields = {
            "service": candidate.get("service", ""),
            "website": candidate.get("website", ""),
            "email": candidate.get("email", ""),
            "username": candidate.get("username", ""),
        }
        duplicates = manager.find_duplicates(
            fields, exclude_id=body.get("exclude_id") or candidate.get("id")
        )
        log.debug("Duplicate check finished: matches=%d", len(duplicates))
        return jsonify({"duplicates": duplicates})

    # ------------------------------------------------------------------
    # Scan, profiles, bookmarks
    # ------------------------------------------------------------------

    @app.post("/api/scan")
    def api_scan():
        log.info("Chrome scan request received")
        result = manager.scan_and_store()
        log.info(
            "Chrome scan response ready: profiles=%d bookmarks=%d warnings=%d "
            "accounts_created=%d",
            result["profile_count"],
            result["bookmark_count"],
            len(result["warnings"]),
            result.get("accounts_created", 0),
        )
        return jsonify(
            {
                "scanned_at": result["scanned_at"],
                "profile_count": result["profile_count"],
                "bookmark_count": result["bookmark_count"],
                "warnings": result["warnings"],
                "chrome_running": result["chrome_running"],
                "accounts_created": result.get("accounts_created", 0),
                "accounts_note": result.get("accounts_note"),
            }
        )

    @app.get("/api/profiles")
    def api_profiles():
        profiles, _doc = serialize_profiles()
        return jsonify({"profiles": profiles})

    @app.get("/api/bookmarks")
    def api_bookmarks():
        query = (request.args.get("q") or "").strip().lower()
        profile_id = request.args.get("profile") or ""
        bookmarks = serialize_bookmarks(manager.list_bookmarks())
        if profile_id:
            bookmarks = [item for item in bookmarks if item["profile_id"] == profile_id]
        if query:
            bookmarks = [
                item
                for item in bookmarks
                if query
                in " ".join(
                    [
                        item["title"],
                        item["url"],
                        item["folder"],
                        item["profile_name"],
                    ]
                ).lower()
            ]
        return jsonify({"bookmarks": bookmarks})

    @app.delete("/api/bookmarks/<bookmark_id>")
    def api_delete_bookmark(bookmark_id: str):
        log.info("Remove bookmark from local index requested: id=%s", bookmark_id)
        if not manager.delete_bookmark(bookmark_id):
            log.warning("Bookmark removal failed; not found: id=%s", bookmark_id)
            return jsonify({"error": "Bookmark not found."}), 404
        return jsonify({"ok": True})

    # ------------------------------------------------------------------
    # Import / export
    # ------------------------------------------------------------------

    @app.post("/api/import/preview")
    def api_import_preview():
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        log.info("Import preview request received")
        result = manager.preview_import(content)
        return jsonify(result)

    @app.post("/api/import/commit")
    def api_import_commit():
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        indexes = body.get("indexes")
        if not isinstance(indexes, list):
            raise ValidationError("Select the records you want to import.")
        log.info("Import commit request received: selected=%d", len(indexes))
        result = manager.commit_import(content, indexes)
        return jsonify(result)

    @app.post("/api/export")
    def api_export():
        body = request.get_json(silent=True) or {}
        include_passwords = bool(body.get("include_passwords"))
        log.info("Export request received: include_passwords=%s", include_passwords)
        return jsonify(manager.export_accounts(include_passwords=include_passwords))

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------

    @app.get("/api/backups")
    def api_backups():
        backups = store.list_backups()
        log.debug("Backup list requested: count=%d", len(backups))
        return jsonify(
            {
                "backups": backups,
                "note": "Backups contain plaintext credentials in Version 1.0.",
            }
        )

    @app.post("/api/backups")
    def api_create_backup():
        log.info("Manual backup requested")
        backup = store.create_backup(label="manual")
        return jsonify({"backup": backup}), 201

    @app.post("/api/backups/restore")
    def api_restore_backup():
        body = request.get_json(silent=True) or {}
        name = body.get("name")
        if not isinstance(name, str) or not name:
            raise ValidationError("Choose a backup to restore.")
        path = store.backup_path(name)
        if not body.get("confirm_replace"):
            log.warning("Backup restore refused without confirmation: %s", name)
            return jsonify({"error": "Confirm that the current data may be replaced."}), 409
        log.info("Backup restore confirmed: %s", name)
        result = store.restore_backup(path)
        return jsonify(result)

    @app.post("/api/backups/upload")
    def api_upload_backup():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            raise ValidationError("Choose a backup .zip file to restore.")
        if not body_confirmed(request.form.get("confirm_replace")):
            log.warning("Uploaded backup restore refused without confirmation")
            return jsonify({"error": "Confirm that the current data may be replaced."}), 409
        log.info("Uploaded backup restore started: filename=%r", upload.filename)
        temp_path = copy_stream_to_temp(upload.stream)
        try:
            result = store.restore_backup(temp_path)
        finally:
            try:
                temp_path.unlink()
            except OSError:
                log.warning("Could not remove temporary upload: %s", temp_path)
        return jsonify(result)

    @app.get("/api/backups/<name>/download")
    def api_download_backup(name: str):
        log.info("Backup download requested: %s", name)
        path = store.backup_path(name)
        return send_file(
            path,
            as_attachment=True,
            download_name=path.name,
            mimetype="application/zip",
        )

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------

    @app.errorhandler(ValidationError)
    def handle_validation(exc: ValidationError):
        log.warning(
            "Validation error on %s: %s (field=%s)",
            request.path,
            exc.message,
            exc.field or "-",
        )
        response = {"error": exc.message}
        if exc.field:
            response["field"] = exc.field
        return jsonify(response), 400

    @app.errorhandler(CorruptFileError)
    def handle_corrupt(exc: CorruptFileError):
        log.error(
            "Corrupt data file on %s: %s (preserved=%s)",
            request.path,
            exc.name,
            exc.preserved_as or "-",
        )
        return (
            jsonify(
                {
                    "error": str(exc),
                    "file": exc.name,
                    "preserved_as": exc.preserved_as,
                }
            ),
            500,
        )

    @app.errorhandler(BackupError)
    def handle_backup(exc: BackupError):
        log.warning("Backup error on %s: %s", request.path, exc)
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(StoreError)
    def handle_store(exc: StoreError):
        log.error("Storage error on %s: %s", request.path, exc)
        return jsonify({"error": str(exc)}), 500

    @app.errorhandler(404)
    def handle_404(exc):
        log.debug("Not found: %s %s", request.method, request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found."}), 404
        return render_template("index.html", csrf_token=app.config["CSRF_TOKEN"], app_version=APP_VERSION), 404

    @app.errorhandler(405)
    def handle_405(exc):
        log.warning("Method not allowed: %s %s", request.method, request.path)
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def handle_413(exc):
        log.warning("Upload too large: %s %s", request.method, request.path)
        return jsonify({"error": "The uploaded file is too large."}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        if isinstance(exc, HTTPException):
            return exc.get_response()
        log.error(
            "Unhandled exception on %s %s",
            request.method,
            request.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unexpected server error. Check logs/app.log."}), 500
        return (
            render_template(
                "index.html",
                csrf_token=app.config["CSRF_TOKEN"],
                app_version=APP_VERSION,
            ),
            500,
        )

    log.info("Flask application initialized; data directory=%s", store.data_dir)
    return app


def body_confirmed(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}
