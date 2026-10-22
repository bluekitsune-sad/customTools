# Chrome Account Manager

A local-only Windows utility that keeps an inventory of the accounts you use across
multiple Chrome profiles. It also indexes each profile's bookmarks so you can search
them from one dashboard.

Version 1.0 deliberately has **no login, no master password, and no encryption**.
Passwords you enter or import are stored as plaintext JSON on your own computer.
The application never uploads data anywhere.

## Features

- **Chrome profile discovery** — finds Chrome, Chrome Beta, Chrome Dev, Chrome Canary,
  and Chromium profiles under `%LOCALAPPDATA%`.
- **Bookmark indexing** — every scan reads each profile's `Bookmarks` file and stores
  the title, URL, folder, profile, and add date locally.
- **Search everything** — one search box covers account service names, emails,
  usernames, websites, categories, notes, profile names, and bookmark titles, URLs,
  folders, and profile names. Passwords are never searched or indexed.
- **Account inventory** — add, edit, delete, assign Chrome profiles, categorize,
  and keep notes.
- **Password controls** — passwords are hidden behind a reveal action and auto-hide
  after 30 seconds. Saved passwords are fetched only when you explicitly reveal or
  copy them.
- **Duplicate warnings** — likely duplicates (same service, website, email, or
  username) are flagged on save. Nothing is merged automatically, and you can save
  anyway.
- **Bookmark → account** — turn any indexed bookmark into a pre-filled account form.
- **Import / export** — JSON import and Chrome password CSV import with preview and
  per-record selection; JSON export with an explicit plaintext-password warning.
- **Backups** — create, download, restore, and upload backup archives. Restoring
  creates a safety backup of the current data first.
- **Step-by-step local logs** — startup, scans, account changes, imports, exports,
  backups, and errors are written to a rotated log file. Passwords, CSRF tokens,
  notes, and bookmark contents are never logged.
- **Local only** — server binds to `127.0.0.1`, requires a CSRF token for writes,
  rejects non-loopback Host headers, and loads no third-party scripts or remote fonts
  at runtime.

### Typography

The dashboard uses **Micro 5**, designed by **Sarah Cadigan-Fried**, for the brand,
statistic values, and section headings. It is self-hosted from `static/fonts/` under
the SIL Open Font License (see `static/fonts/OFL.txt`), so no request is made to
Google Fonts at runtime. Body text uses the system UI font for readability.

## Requirements

- Windows 10 or later
- Python 3.9+ (tested with Python 3.14)
- Flask 3.x (`pip install -r requirements.txt`)

## Setup and run

```powershell
cd accountManager
python -m pip install -r requirements.txt
python main.py
```

The terminal prints the dashboard URL (default `http://127.0.0.1:8765/`) and opens it
in your default browser. Stop the application with `Ctrl+C`.

Options:

```powershell
python main.py --port 8800      # preferred port; nearby free ports are used if busy
python main.py --no-browser     # do not open a browser automatically
```

## Using the dashboard

1. Click **Scan Chrome** to discover profiles and index bookmarks. The scan does
   **not** read saved Chrome passwords or create account records; accounts are added
   manually or imported.
2. Use **+ Add account** to create an account manually, or **Data → Import** to bring
   in accounts from JSON or Chrome's password CSV.
3. Type in the search box to search accounts **and** bookmarks at once.
4. Switch to the **Bookmarks** tab to browse them; use **→ Account** to create an
   account seeded with that bookmark's title and URL.
5. Use the **Data** menu for import, export, and backups.

Close Chrome before scanning if profiles or bookmarks appear incomplete. When Chrome
is running, the dashboard shows a warning instead of failing the scan.

### Why does the scanner not read saved Chrome passwords?

Version 1.0 only reads metadata and bookmark files. It does not decrypt Chrome's
`Login Data` database or bypass Windows DPAPI protection. Account passwords only
enter the inventory through explicit user input or an explicit import.

Current Chrome versions store many password values as `v20` blobs protected by
**App-Bound Encryption**, in addition to Windows DPAPI. This app does not bypass
App-Bound Encryption. Chrome's own password manager can export the logins after
confirming your Windows account. Import that CSV with **Data → Import**. This keeps
Chrome's security boundary intact: the app never decrypts the browser database
behind Chrome's back.

### Importing saved Chrome passwords

1. In Chrome, open `chrome://password-manager/settings`.
2. Choose **Export passwords**, confirm with your Windows account, and save the CSV.
3. In this app, open **Data → Import accounts…**, select the CSV, review the preview,
   and import the records you want.
4. If the CSV came from one specific Chrome profile, choose that profile under
   **Tag imported accounts with a Chrome profile** before importing. This is how
   imported accounts keep their source profile.

Chrome's CSV does not contain a profile ID. Gmail logins are also auto-linked when
the username matches a profile's Google email and exactly one profile has that email.
For other services, tag the import manually. Imported passwords are stored as
plaintext in `vault.json`, like manually entered passwords. Delete the exported CSV
after importing it if you do not need it.

### Removing bookmarks

Removing a bookmark from the dashboard only deletes the local index entry. It does
not touch Chrome, and the next scan will index the bookmark again.

## Data and files

```
accountManager/
├── main.py               # startup, port selection, browser launch
├── scanner.py            # read-only Chrome profile + bookmark discovery
├── account_manager.py    # accounts, credentials, bookmarks, import/export
├── json_store.py         # atomic JSON reads/writes, backups, corruption handling
├── server.py             # Flask API, loopback/CSRF/security headers
├── logging_setup.py      # rotating local logs (no secrets)
├── templates/index.html  # dashboard markup
├── static/styles.css     # styling
├── static/app.js         # dashboard behaviour
├── requirements.txt
├── data/                 # created on first run; local and sensitive
│   ├── accounts.json     # account metadata (no passwords)
│   ├── profiles.json     # discovered profile metadata and scan warnings
│   ├── bookmarks.json    # indexed bookmarks
│   └── vault.json        # PLAINTEXT passwords in Version 1.0
├── backups/              # local .zip backups (also plaintext)
└── logs/                 # rotated app.log files; no passwords or bookmark contents
```

`data/`, `backups/`, and `logs/` are ignored by Git. Back up the whole folder only
to storage you trust.

### Storage behaviour

- Writes use a temporary file plus atomic replacement.
- Missing files are created on first run.
- Malformed JSON is preserved as `*.corrupt-<hash>.json` and reported; it is never
  silently replaced. Startup refuses to continue until the file is fixed or restored.
- Data and backup folders are restricted to the current Windows user on a best-effort
  basis using `icacls`.

### Logging

The app writes step-by-step operation logs to `logs/app.log` and to the terminal.
The file rotates at 5 MB and keeps five older copies. Logged events include startup,
scan stages, per-profile bookmark counts, account create/update/delete, password
reveal requests, import/export, backups, request results, and errors.

Logs intentionally exclude passwords, CSRF tokens, notes, bookmark titles, and
bookmark URLs. `logs/` is excluded from Git.

## Import format

```json
{
  "version": 1,
  "accounts": [
    {
      "service": "Example Service",
      "website": "https://example.com",
      "email": "user@example.com",
      "username": "example_user",
      "password": "optional",
      "category": "Personal",
      "notes": "",
      "chrome_profile_ids": ["prof_0123456789ab"]
    }
  ]
}
```

A bare JSON array of the same account objects is also accepted. Each record is
validated in the preview; invalid records cannot be selected, and likely duplicates
are unchecked by default. Imported passwords go into `vault.json` in plaintext.

Chrome's password CSV exports are also accepted. The expected columns are
`name,url,username,password,note`; a username that looks like an email is stored as
the account email. Use the import dialog's profile selector to tag accounts with the
Chrome profile they came from. See **Importing saved Chrome passwords** above for the
export steps.

`chrome_profile_ids` is optional. Exports include it so profile links survive a
round trip; `chrome_profiles` containing profile display names is also accepted.

## Export and backup safety

Exports that include passwords, and every backup archive, contain plaintext
credentials. They are not encrypted. The UI warns before creating them. Delete old
copies when they are no longer needed. A future encryption upgrade must handle these
copies too, not just `vault.json`.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| No profiles found | Make sure Chrome has been launched at least once under this Windows user, then rescan. |
| Scan found profiles/bookmarks but no accounts | Expected: scans never read saved Chrome passwords or create account records. Use **+ Add account**, import JSON, or import Chrome's password CSV. |
| Bookmarks missing | Close Chrome and rescan. Check the scan warnings panel. |
| Port already in use | The app automatically picks the next free port; read the URL printed in the terminal. |
| `accounts.json is not valid JSON` | Restore a backup or fix the file. The app preserves a copy as `accounts.corrupt-<hash>.json`. |
| Dashboard will not load | Confirm the terminal still shows the server running, and that you opened the exact `127.0.0.1` URL. |
| Wrong profile names | Chrome's stored names may not match what you expect. The directory, channel, and exposed Google email are shown on the Profiles tab. |

## Security and privacy limits in Version 1.0

- No application login or master password.
- Passwords in `vault.json`, exports, and backups are plaintext.
- The dashboard is protected against network exposure through loopback binding,
  but any process running as your Windows user can read the data files.
- Operational logs are local and never include passwords, CSRF tokens, notes, or
  bookmark contents, but they do reveal that the app and its features were used.
- The scanner is read-only and does not bypass Chrome or Windows credential
  protections.

## Deferred to a future version

- Encrypted credential storage and a master-password unlock screen.
- Time-limited, encrypted password tokens for pasting into websites (requires a
  browser extension or companion helper; see the PRD).
- Firefox and Edge profile discovery.
- Optional desktop packaging.
