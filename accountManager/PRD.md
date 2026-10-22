## Chrome Account Manager — Version 1.0

**Status:** Implemented specification\
**Platform:** Windows 10\
**Application type:** Local desktop utility with a web-based interface\
**Primary language:** Python\
**Data format:** JSON\
**Frontend:** HTML, CSS, JavaScript\
**Cloud dependency:** None

---

## 1\. Product Overview

Chrome Account Manager is a personal application that helps the user discover, organize, search, and manage accounts associated with multiple Google Chrome profiles.

It also indexes the bookmarks stored in each Chrome profile so that the user can search accounts and bookmarks from one local dashboard instead of switching between browser profiles.

The application will provide a local web dashboard that displays known email addresses, usernames, services, bookmarks, and associated Chrome profiles. It will use Python for local operations and JSON files for persistent storage.

The initial release will not require an application login, master password, or encryption. Credentials explicitly added or imported by the user will be stored as direct values in local JSON files.

Encryption, master-password authentication, and time-limited encrypted password tokens will be reserved for a future version and must not be implemented in Version 1.0.

## 2\. Problem Statement

Users who maintain multiple Chrome profiles may forget which email address or account they used for a particular website.

This can lead to:

- Repeated attempts to identify the correct account.
- Unnecessary creation of duplicate accounts.
- Difficulty remembering which Chrome profile contains an account.
- Time wasted switching between browser profiles.
- Difficulty maintaining a consolidated inventory of personal and work accounts.

The application will provide a single local interface for organizing known account information and associating it with Chrome profiles.

## 3\. Product Goals

1. Discover Chrome profiles available on the local Windows machine.
2. Maintain an inventory of known website accounts.
3. Index bookmarks from every discovered Chrome profile and make them searchable from the dashboard.
4. Associate accounts with their corresponding Chrome profiles when the relationship is known.
5. Store account and bookmark information locally in JSON files.
6. Support searching, filtering, sorting, adding, editing, and deleting account records.
7. Provide a manual scan button in the web interface.
8. Allow the application to be started manually using Python.
9. Avoid cloud databases, external account synchronization, and mandatory internet access for core functionality.
10. Keep the architecture modular so Firefox, Microsoft Edge, encryption, password tokens, and authentication can be added later.

## 4\. Target User

The initial target user is a single person using Windows 10 who maintains multiple Chrome profiles and wants a consolidated account inventory on their own computer.

The initial release is designed for individual use, not multiple users or an organization.

## 5\. Scope

### 5.1 Included in Version 1.0

- Chrome profile discovery.
- Profile metadata display.
- Bookmark discovery and local indexing from every discovered profile.
- Combined account and bookmark search in the dashboard.
- Creating a pre-filled account from an indexed bookmark.
- Local JSON persistence.
- Account inventory management.
- Search and filtering.
- Manual scanning of profiles and bookmarks.
- Password fields for explicitly entered or imported credentials.
- Password reveal and hide controls.
- Service and account categorization.
- Duplicate detection.
- Local application startup through Python.
- Basic backup and restore.
- Local operational logging with secret redaction.
- Local-only operation.
- Clear warnings regarding plaintext credential storage.

### 5.2 Excluded from Version 1.0

- Firefox support.
- Microsoft Edge support.
- Cloud synchronization.
- Mobile applications.
- Multi-user access.
- Automatic website login.
- Automatic creation of website accounts.
- Browser automation for logging into every website.
- Automatic deletion of passwords from Chrome.
- Bypassing Chrome or Windows credential protections.
- Automatic extraction or decryption of every saved Chrome password.
- Modifying, deleting, or syncing Chrome bookmarks. Bookmarks are indexed read-only.
- Encryption of stored credentials.
- Application login or master-password authentication.
- Time-limited encrypted password tokens for pasting into websites (see FE-06).
- Browser extensions.
- Third-party password-manager integration beyond explicit file import.

## 6\. Technical Architecture

### 6.1 Technology Stack

| Component | Technology |
| --- | --- |
| Operating system | Windows 10 |
| Backend | Python |
| Local web server | Flask |
| Frontend | HTML, CSS, JavaScript |
| Display font | Micro 5 by Sarah Cadigan-Fried, self-hosted under the SIL Open Font License |
| Persistent storage | JSON files |
| Browser discovery | Python filesystem and metadata inspection |
| Account search | JavaScript and Python filtering |
| Application startup | Manual Python command |

The application must run on the local machine. The Flask server must bind to the loopback interface (`127.0.0.1`) rather than expose the dashboard to the local network.

### 6.2 Project Structure

```
ChromeAccountManager/
├── main.py
├── scanner.py
├── account_manager.py
├── json_store.py
├── server.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   └── app.js
├── data/
│   ├── accounts.json
│   ├── profiles.json
│   ├── bookmarks.json
│   └── vault.json
├── backups/
└── README.md
```

The `vault.json` file is a plaintext credential store in Version 1.0 despite its filename. It must be clearly documented as such. A later security upgrade may change its format.

`bookmarks.json` stores a read-only local index of bookmarks read from Chrome. Deleting an entry from this file must never delete the bookmark from Chrome.

The `data` and `backups` directories must be excluded from source-control commits by default.

## 7\. Functional Requirements

### FR-01: Manual Application Startup

The user must be able to start the application by opening a terminal in the project directory and executing:

```
python main.py
```

The application must start its local backend and make the dashboard available in the default browser.

The program must print a clear local URL and useful error messages if startup fails.

The user must be able to stop the application with Ctrl+C.

### FR-02: Chrome Profile Discovery

The scanner must identify Chrome profile directories using known Windows Chrome installation locations and available Chrome profile metadata.

For each discovered profile, the application should collect the following fields when available:

- Profile directory identifier.
- Display name.
- Local profile path.
- Associated Google account email, if exposed through accessible metadata.
- Discovery status.
- Last scan timestamp.

The scanner must not assume that a directory name such as `Profile 2` represents a particular person or email address.

Profile discovery must not modify Chrome profile files or interrupt an active Chrome session.

If Chrome is running, the scanner should avoid reading mutable files where this could cause inconsistent results. It may ask the user to close Chrome and rescan if required.

The same read-only scan must also index Chrome bookmarks as described in FR-16. Bookmark indexing must not modify the `Bookmarks` file.

### FR-03: Manual Scan Button

The dashboard must include a prominent **Scan Chrome Profiles** button.

When clicked, it must:

1. Send a request to the local Python backend.
2. Start a Chrome profile discovery and bookmark indexing operation.
3. Display a scanning indicator.
4. Report the number of profiles and bookmarks discovered.
5. Update the profile inventory, bookmark index, and dashboard statistics.
6. Display warnings or errors if discovery is incomplete.
7. Record the last successful scan timestamp.
8. Clearly report that a scan does not create account records or read saved Chrome passwords.

Scanning must be an explicit user action. The application must not run continuous background scans.

A scan must not silently overwrite user-entered account information. Accounts are created manually or through an explicit import; profile and bookmark scans never create accounts.

### FR-04: Account Inventory

The dashboard must display a list or table of known accounts.

Each account record may contain:

- Unique account ID.
- Service name.
- Website URL.
- Email address.
- Username.
- Password.
- Chrome profile association.
- Account category.
- Notes.
- Record creation timestamp.
- Last modified timestamp.
- Last verified timestamp, if applicable.

Email, username, password, and profile association may be empty when unknown.

Account information must be obtained from user input, explicit imports, or supported and authorized discovery methods. The application must distinguish verified information from information that is merely inferred.

### FR-05: Add Account

The user must be able to add an account manually.

The form must provide fields for service name, website, email, username, password, Chrome profile, category, and notes.

Required fields:

- Service name.
- At least one of email or username.

The password field must be optional.

When the user saves a record, the backend must validate the input and write the account to the appropriate JSON file.

### FR-06: Edit and Delete Accounts

The user must be able to edit an existing account.

The user must also be able to delete an account after receiving a confirmation prompt.

Deleting an inventory record must not automatically delete the associated password from Chrome or affect the corresponding website account.

### FR-07: Search

The dashboard must include a search field that searches the available account inventory and the indexed bookmarks.

Account searchable fields:

- Service name.
- Email address.
- Username.
- Website URL.
- Chrome profile name.
- Category.
- Notes.

Bookmark searchable fields:

- Bookmark title.
- Bookmark URL.
- Bookmark folder path.
- Chrome profile name.

Search must be case-insensitive and should update results without requiring a page reload. When the search field is used, the dashboard should show matching accounts and matching bookmarks together, grouped by record type.

Passwords must not be included in search indexing or search result text.

### FR-08: Filtering and Sorting

The dashboard must support filtering accounts by:

- Chrome profile.
- Account category.
- Service.
- Records with or without an email address.
- Records with or without a saved password.
- Verification status, when available.

The dashboard must support filtering bookmarks by Chrome profile.

Sorting options should include service name, email, profile, last modified date, bookmark title, and bookmark date added.

### FR-09: Password Display

Version 1.0 will store manually entered or explicitly imported passwords as direct string values in the local JSON credential store.

The interface must provide a reveal/hide control for password fields. Passwords should be hidden by default in the account list and revealed only when the user explicitly requests it.

Password values must not appear in application logs, error messages, URLs, or browser console output.

The application must not claim that plaintext JSON storage is secure.

### FR-10: Chrome Profile Association

An account can be associated with one or more Chrome profiles if the user knows that the account is used in those profiles.

The interface must allow the user to assign or correct the profile association manually.

The application must not claim that an account is currently signed in to a website merely because it appears in the inventory or has a saved password.

Where the scanner cannot establish an association reliably, it must show the account as unassigned or unknown.

### FR-11: Duplicate Detection

Before saving a new account, the application should check for likely duplicates using service name, normalized website URL, email address, and username.

The application must warn the user about likely matches without automatically merging records.

The user must be able to keep separate accounts on the same service.

### FR-12: JSON Storage

The application will use separate JSON files for account metadata, profile metadata, and credentials.

Suggested storage responsibilities:

- `accounts.json`: Account IDs, service names, usernames, emails, categories, profile associations, and credential references.
- `profiles.json`: Discovered Chrome profile metadata and scan status.
- `vault.json`: Credential IDs and their associated plaintext password values in Version 1.0.

The account records should refer to credentials by ID rather than duplicating passwords across files.

The application must:

- Validate JSON before using it.
- Create missing data files when starting for the first time.
- Preserve valid records when updating the inventory.
- Write updates safely using temporary files and atomic replacement where supported.
- Create backups before potentially destructive bulk changes.
- Handle malformed JSON without silently erasing the user's data.

### FR-13: Import and Export

The application must support importing an explicitly selected, user-provided account file using a documented schema.

The application must support importing Chrome's official password export CSV (`name,url,username,password,note`) through the explicit import workflow. The user must create that export through Chrome's own password manager, including Chrome's Windows-account confirmation. The application must not decrypt Chrome's `Login Data` database or bypass DPAPI.

The import workflow must let the user tag imported accounts with a Chrome profile, because Chrome's CSV does not include a profile identifier. A Gmail-style username may be auto-linked when it matches exactly one profile's Google email.

The user must preview the records before importing and resolve or skip duplicates. When a selected import record matches an existing account, the import must update that account and preserve its profile links instead of creating a second copy.

Exports containing passwords must display a clear warning that the exported file will contain plaintext credentials.

Imports and exports must not occur silently.

### FR-14: Backup and Restore

The application should allow the user to create a local backup of its JSON data.

The backup process must include the account index, profile metadata, and credential file so that records remain linked.

The restore workflow must validate files before replacing the current inventory and create a backup of the existing data first.

Because Version 1.0 stores plaintext passwords, backup files must be treated as sensitive.

### FR-15: Local-Only Operation

The application must not upload account data or credentials to a remote service.

The Flask server must bind to `127.0.0.1` and validate requests originating from the dashboard.

State-changing routes must use appropriate request validation and CSRF protections. Sensitive values must not be placed in URLs.

The dashboard must not load third-party scripts, fonts, analytics, or other external resources at runtime.

### FR-16: Bookmark Discovery

Each profile scan must also index the bookmarks stored in that profile, without requiring a separate button or a second confirmation.

The scanner must:

- Read the profile's `Bookmarks` file as JSON in read-only mode.
- Recursively traverse the Bookmarks Bar, Other Bookmarks, and Mobile Bookmarks trees.
- Index both bookmarks and their containing folder path.
- Skip entries that are not valid URL bookmarks, without failing the whole scan.
- Handle a missing `Bookmarks` file as an empty collection rather than an error.
- Preserve the previously indexed bookmarks for a profile when its `Bookmarks` file cannot be read, and add a scan warning.
- Avoid creating duplicate entries when the same profile is scanned repeatedly, using a stable bookmark identifier derived from the profile, URL, title, and folder.

Each indexed bookmark record must contain:

- Unique bookmark ID.
- Chrome profile ID and display name.
- Title.
- URL.
- Folder path.
- Date added, when Chrome exposes a valid timestamp.
- Scan timestamp.

The scanner must never modify, delete, move, or sync Chrome bookmarks. Removing a bookmark from the dashboard must only remove the local index entry, and a later scan may index it again.

### FR-17: Bookmark Dashboard and Search

The dashboard must display indexed bookmarks in a dedicated view and include them in the main search experience.

Requirements:

- Show the total number of indexed bookmarks in the dashboard summary.
- Provide a Bookmarks view with title, URL, folder, profile, date added, and actions.
- Include bookmark matches in the main search field alongside account matches.
- Allow opening a bookmark only when its URL uses `http` or `https`; other schemes must be displayed as text and must not become clickable links.
- Allow copying a bookmark URL.
- Allow removing a bookmark from the local index after confirmation.
- Allow creating a new account pre-filled with the bookmark's title and URL. The user must still supply the required email or username before saving.
- Show per-profile bookmark counts on the Profiles view.
- Report bookmark read failures through the same scan warnings used for profile discovery.

Bookmarks must not be uploaded anywhere and must not be treated as credentials.

### FR-18: Local Operational Logging

The application must write local, step-by-step operational logs for startup, scans, data changes, imports, exports, backups, and errors.

Requirements:

- Write logs to a local `logs/app.log` file and to the terminal.
- Rotate the log file so it cannot grow without bound.
- Log scan stages, discovered profile identifiers, per-profile bookmark counts, merge results, and warnings.
- Log account create, update, and delete operations by account ID and service name.
- Log password reveal requests by account ID, but never the password value.
- Log import, export, backup, restore, and rejected-request events.
- Include timestamps, severity, logger name, and thread name.
- Never log passwords, CSRF tokens, vault contents, notes, bookmark titles, bookmark URLs, or full request bodies.
- Keep logs local and exclude the log directory from Git.
- Logging failures must not prevent the application from starting or from completing data operations.

### FR-19: Chrome Login Metadata Import

The application must provide an explicit action to import account metadata from Chrome's `Login Data` database without decrypting passwords.

Requirements:

- Keep this separate from the profile/bookmark scan because it creates account records.
- Open each profile's `Login Data` read-only and select only `origin_url`, `signon_realm`, `username_value`, `display_name`, and non-secret flags.
- Never retrieve, log, export, or decrypt `password_value` content.
- Skip rows marked as never-save/blacklisted.
- Create missing accounts with the email or username and website, and link them to the source Chrome profile.
- Merge with an existing account when the normalized service or website host matches and the email/username matches; preserve any password already stored.
- Do not create a credential for metadata-only imports.
- Report locked or unreadable databases as warnings and continue with other profiles.
- Log only counts and profile identifiers, never imported emails, usernames, or URLs.
- Tell the user that encrypted passwords remain in Chrome and that passwords require Chrome's official CSV export.

## 8\. User Interface Requirements

### 8.1 Dashboard

The main dashboard must display:

- Total number of known accounts.
- Number of discovered Chrome profiles.
- Total number of indexed bookmarks.
- Number of known services.
- Last scan timestamp.
- Combined search field for accounts and bookmarks.
- Profile, service, category, record-state (password/email), and sort controls.
- Scan Chrome Profiles button (which also scans bookmarks). The scan result must state that accounts are not imported.
- Add Account button.
- Accounts, Bookmarks, and Profiles views.
- Import, export, and backup actions.

### 8.2 Account Table

Suggested columns:

| Column | Description |
| --- | --- |
| Service | Website or application name |
| Email | Known email address |
| Username | Known username |
| Chrome profile | Associated profile or Unknown |
| Category | Personal, Work, Social, Finance, Other |
| Password | Hidden by default, with a reveal action |
| Actions | View, Edit, Delete |

The table should be responsive and easy to use on a typical Windows desktop display.

### 8.3 Bookmark Table

Suggested columns:

| Column | Description |
| --- | --- |
| Bookmark | Title and hostname; opens in a new tab for HTTP/HTTPS URLs |
| Folder | Bookmark folder path, when known |
| Profile | Chrome profile that contains the bookmark |
| Added | Date the bookmark was added, when exposed by Chrome |
| Actions | Open, copy link, create account, remove from index |

Bookmarks with non-HTTP(S) schemes must not render as clickable links. The view must state that removing an entry only affects the local index.

### 8.4 Add/Edit Form

The form should support creating or modifying all account fields.

It must validate required fields and provide understandable error messages.

The password field must not be prefilled into unrelated browser form fields or unintentionally exposed in the page source.

### 8.5 Empty State

When no accounts exist, the dashboard must explain how to add an account and offer the user the option to run a Chrome profile scan.

When no bookmarks are indexed, the dashboard must explain that a scan reads each profile's Bookmarks file and offer the scan action. Bookmark removal must not be presented as deleting the bookmark from Chrome.

The application must not create fake account or bookmark records.

## 9\. Data Models

### 9.1 Account Metadata Example

```
{
  "version": 1,
  "accounts": [
    {
      "id": "acc_001",
      "service": "Example Service",
      "website": "https://example.com",
      "email": "user@example.com",
      "username": "example_user",
      "credential_id": "cred_001",
      "chrome_profiles": ["Default"],
      "category": "Social",
      "notes": "",
      "created_at": "2026-10-22T12:00:00",
      "updated_at": "2026-10-22T12:00:00",
      "verified_at": null
    }
  ]
}
```

### 9.2 Credential Store Example — Version 1.0 Only

```
{
  "version": 1,
  "credentials": [
    {
      "id": "cred_001",
      "password": "example-password"
    }
  ]
}
```

The example password is fictitious. Actual credentials must be supplied by the user through the application's supported input or import workflows.

### 9.3 Chrome Profile Example

```
{
  "version": 1,
  "last_scan_at": "2026-10-22T12:00:00",
  "warnings": [],
  "chrome_running": false,
  "profiles": [
    {
      "id": "prof_1a2b3c4d5e6f",
      "dir": "Default",
      "display_name": "Personal",
      "path": "<local Chrome profile path>",
      "google_email": null,
      "channel": "Chrome",
      "user_data_dir": "<local Chrome User Data path>",
      "last_scanned_at": "2026-10-22T12:00:00",
      "bookmark_count": 42,
      "status": "ok"
    }
  ]
}
```

Account `chrome_profiles` values must reference the profile `id` values in this file.

### 9.4 Bookmark Index Example

```
{
  "version": 1,
  "last_scan_at": "2026-10-22T12:00:00",
  "bookmarks": [
    {
      "id": "bm_1a2b3c4d5e6f78",
      "profile_id": "prof_1a2b3c4d5e6f",
      "profile_name": "Personal",
      "title": "Example Documentation",
      "url": "https://example.com/docs",
      "folder": "Bookmarks Bar/Work",
      "date_added": "2026-10-20T09:30:00",
      "scanned_at": "2026-10-22T12:00:00"
    }
  ]
}
```

Bookmark IDs must be stable across scans so re-scanning replaces entries instead of duplicating them. `date_added` may be `null` when Chrome does not expose a valid timestamp.

All timestamps and example values must be replaced with actual application data when records are created.

## 10\. Security and Privacy Requirements for Version 1.0

Version 1.0 intentionally has no application login, master password, or encryption.

This decision must be documented explicitly.

The following protections are still required:

- Keep application data in a dedicated local directory.
- Restrict access to data and backup files using Windows file permissions where possible.
- Bind the server to loopback only.
- Hide passwords in the interface by default.
- Do not expose credentials in URLs or browser console output.
- Require explicit confirmation before bulk deletion or replacement.
- Warn the user before creating or exporting plaintext credential files.
- Provide backup and restore functionality.
- Treat `bookmarks.json` as sensitive: bookmark titles, folders, and URLs can reveal personal or work interests and accounts.
- Keep operational logs free of passwords, CSRF tokens, notes, bookmark titles, and bookmark URLs.
- When reading Chrome `Login Data` metadata, open the database read-only and never retrieve `password_value` content.
- Render only `http` and `https` bookmarks as clickable links. Other schemes must remain inert text.
- Make clear that removing a bookmark from the dashboard affects only the local index, never Chrome.

## 11\. Future Enhancements — Not Included in Version 1.0

These features must be documented and deferred until the user explicitly requests their implementation.

### FE-01: Encrypted Credential Storage

Replace the plaintext credential store with a well-reviewed encryption implementation.

Requirements:

- Use a maintained cryptographic library.
- Derive encryption keys from a user-provided master password using an appropriate password-based key derivation function.
- Use authenticated encryption.
- Generate and store unique salts and nonces as required by the selected cryptographic scheme.
- Never store the master password in the JSON files or application configuration.
- Provide a migration utility that converts existing plaintext credentials into encrypted storage.
- Verify that migrated credentials can be decrypted before retiring the plaintext source.
- Back up the original data before migration and warn the user about any remaining plaintext copies.

### FE-02: Master-Password Authentication

Add an application unlock screen that requires a master password before credentials can be viewed.

Requirements:

- Require the master password when the application is opened.
- Keep the unlocked state only for the current application session.
- Provide a manual lock action.
- Clear sensitive values from the interface when the vault is locked.
- Never persist the master password in plaintext.
- Do not enable access to credentials when authentication fails.

Encryption and authentication should be implemented together so that the login screen actually protects the underlying credential data.

### FE-03: Additional Browsers

Add profile discovery for:

- Mozilla Firefox.
- Microsoft Edge.

### FE-04: Improved Account Discovery

Investigate supported methods for identifying additional account metadata, including user-assisted browser exports and explicit account imports.

Maintain a clear distinction between a saved credential, an account record, and an actively authenticated website session.

### FE-05: Optional Desktop Packaging

Package the application as a Windows executable or add a desktop launcher without requiring the user to run the Python command manually.

### FE-06: Time-Limited Encrypted Password Tokens

Provide a way to use an account without ever displaying or copying its real password. The user requests a token for one account, the application returns an encrypted, short-lived token, and the user pastes that token into the website or into the companion helper. When the token expires, it becomes useless.

This is a future feature and must not be implemented in Version 1.0.

**Important feasibility constraint.** A normal website accepts only a plaintext password in its login form. It cannot decrypt an application-specific token. Therefore this feature can only work with a companion browser extension (or an equivalent local helper) that:

- Recognizes the token format.
- Checks that the current page origin matches the origin the token was issued for.
- Decrypts the token in memory.
- Fills the real password into the page and optionally submits it.

Without that companion, pasting an encrypted token into a website would simply submit an invalid password. The PRD must not claim otherwise.

Requirements:

- This feature depends on FE-01 (encrypted storage) and FE-02 (master-password unlock) and must be built after them.
- The real password must never be rendered in the dashboard, placed on the clipboard, written to logs, or embedded in the token as readable text.
- The token must be bound to:
  - One account ID.
  - One exact target origin (scheme, host, and port).
  - An expiry timestamp.
  - A unique nonce.
  - A single-use flag, when the helper can record consumption.
- Tokens must use authenticated encryption so tampering or truncation is rejected.
- The encryption key must derive from the unlocked vault session and must not be stored next to the token.
- The token display must be one-time; closing the dialog or the TTL expiring must discard it from the interface.
- The TTL must be short and capped (for example, 30-120 seconds), and expiry must be enforced at decryption/use time, not only by hiding the token in the UI.
- Reuse of an expired, already-used, or origin-mismatched token must be refused.
- The application must provide a manual revoke action for outstanding tokens.
- Tokens must never appear in URLs, browser history, application logs, backups, exports, or analytics. Backups must contain encrypted credentials only, never live tokens.
- The helper must refuse to autofill on a different origin, an iframe it does not trust, or a page that did not receive an explicit user action.
- Issuance and use should be recorded in a local audit log containing account ID, origin, timestamps, and outcome, but never the password or token value.
- The feature must ship with a written threat model. It protects against shoulder surfing, screen sharing, and long-lived exposure of the real password. It does not protect against a compromised operating system, a compromised browser, a malicious extension, or a website that captures the resolved password at submit time.
- If no companion extension is installed, the application must not pretend that pasting a token works. A weaker fallback may be offered as a clearly labelled "clipboard lease" that puts the real password on the clipboard and clears it after a few seconds, but that fallback is not equivalent to encryption.
- A migration step must confirm that the plaintext vault, old backups, and old exports have been handled before token features are enabled.

The companion extension must be treated as a separate, security-sensitive deliverable with its own permissions and review.

## 12\. Acceptance Criteria

Version 1.0 is considered ready when all of the following are true:

1. The application starts using `python main.py` on the target Windows 10 environment.
2. The local dashboard opens successfully.
3. The scanner discovers available Chrome profile directories without modifying Chrome's stored credentials.
4. A scan indexes bookmarks from every readable profile without modifying the Chrome `Bookmarks` file.
5. Repeated scans update the bookmark index without creating duplicate entries.
6. The user can add, view, edit, and delete account records.
7. Account data persists across application restarts.
8. Search returns matching accounts and matching bookmarks from one search field.
9. Filters and sorting return the expected records.
10. Passwords can be explicitly entered or imported and are hidden by default in the dashboard.
11. Profile associations can be assigned manually and remain saved.
12. Duplicate warnings work without automatically merging records.
13. The Bookmarks view opens only HTTP/HTTPS links, copies URLs, removes entries from the local index only, and can pre-fill a new account.
14. Per-profile account and bookmark counts are displayed correctly.
15. Invalid or corrupted JSON does not silently overwrite existing data.
16. Backups can be created and restored.
17. No account or bookmark information is uploaded to a cloud service.
18. The application does not require an application login or master password.
19. Credential storage is plaintext JSON in Version 1.0, and this limitation is clearly documented.
20. Encryption, master-password authentication, and time-limited encrypted password tokens remain deferred until explicitly requested.
21. Startup, scans, account changes, imports, exports, backups, and errors are written to a rotated local log without passwords, CSRF tokens, notes, or bookmark contents.
22. Chrome's official password export CSV can be previewed and imported without reading or decrypting Chrome's credential database.
23. Imported accounts can be tagged with the source Chrome profile, and Gmail usernames auto-link when exactly one profile matches.
24. Chrome login metadata import creates or links accounts from emails/usernames and URLs without reading password content or decrypting `password_value`.

## 13\. Development Plan

### Phase 1 — Project Foundation

- Set up the Python project.
- Create the Flask server.
- Establish the JSON storage format.
- Implement initial configuration and startup.
- Add local operational logging with secret redaction.

### Phase 2 — Chrome Scanner and Bookmark Index

- Discover Chrome installation and profile directories.
- Read supported profile metadata.
- Read each profile's bookmarks in read-only mode, including folders.
- Store bookmarks with stable identifiers and per-profile counts.
- Display discovered profiles and bookmark statistics.
- Implement scan status, bookmark read warnings, and error handling.
- Log scan stages, per-profile counts, merge results, and warnings.

### Phase 3 — Account Management

- Add, edit, and delete accounts.
- Implement credential references.
- Add duplicate detection.
- Persist changes to JSON.

### Phase 4 — Dashboard

- Build the HTML/CSS/JavaScript interface.
- Implement combined account and bookmark search.
- Implement filters and sorting.
- Add password reveal controls.
- Add the Accounts, Bookmarks, and Profiles views.
- Add the manual scan button.
- Add bookmark actions, including pre-filling an account from a bookmark.

### Phase 5 — Import, Backup, and Testing

- Implement explicit import and export workflows, including Chrome's official password CSV export.
- Implement read-only Chrome login metadata import for emails, usernames, URLs, and profile links.
- Add backup and restore.
- Test malformed files, missing profiles, unreadable bookmark files, duplicate records, repeated scans, and application restarts.
- Document setup and usage.

### Phase 6 — Release

- Verify all acceptance criteria.
- Provide a README with installation and usage instructions.
- Document the plaintext credential limitation.
- Document that bookmark indexing is read-only and that bookmark removal only affects the local index.
- Keep future encryption, login, and password-token features out of the initial implementation.

## 14\. Definition of Done

The first release is complete when the user can start the application manually, scan Chrome profiles and bookmarks, maintain an account inventory, search and filter accounts and indexed bookmarks from one dashboard, reveal manually entered or imported passwords, and preserve their data across restarts without relying on cloud storage.

The project must remain modular enough to add encrypted credential storage, master-password authentication, and time-limited encrypted password tokens later without rebuilding the entire interface or data model.

## Final implementation decisions

- Version 1.0: No login, no encryption, plaintext credentials in local JSON.
- Scanner: Chrome profile discovery, accessible metadata, and read-only bookmark indexing; no bypassing Chrome's credential protections.
- Bookmarks: indexed during the same manual scan, searchable in the dashboard, never modified in Chrome.
- Launch: `python main.py`.
- Storage: Separate JSON files for account metadata, profile metadata, bookmarks, and credentials.
- Future version: Encryption, master-password login, a safe migration path, and time-limited encrypted password tokens will be added only when you explicitly ask for them.
- Password tokens: an encrypted token is only usable by a companion extension or helper that decrypts it for a matching origin before it expires. A plain website cannot consume an encrypted token by itself.

One particularly important requirement in this PRD is that upgrading later must account for plaintext copies in backups and exports, too. Encrypting the main JSON file alone would not make those copies safe.