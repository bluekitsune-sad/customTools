'use strict';

(() => {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.content : '';

  const state = {
    accounts: [],
    bookmarks: [],
    profiles: [],
    stats: {},
    categories: [],
    warnings: [],
    storage: {},
    last_scan_at: null,
  };

  let activeView = 'accounts';
  let warningsDismissed = false;
  let importState = { content: '', records: [] };
  let openModalId = null;

  const $ = (id) => document.getElementById(id);
  const els = {
    scanBtn: $('scanBtn'),
    addAccountBtn: $('addAccountBtn'),
    dataMenuBtn: $('dataMenuBtn'),
    dataMenu: $('dataMenu'),
    searchInput: $('searchInput'),
    profileFilter: $('profileFilter'),
    serviceFilter: $('serviceFilter'),
    categoryFilter: $('categoryFilter'),
    passwordFilter: $('passwordFilter'),
    sortSelect: $('sortSelect'),
    resetFilters: $('resetFilters'),
    warnings: $('warnings'),
    warningList: $('warningList'),
    dismissWarnings: $('dismissWarnings'),
    accountsPanel: $('accountsPanel'),
    bookmarksPanel: $('bookmarksPanel'),
    profilesPanel: $('profilesPanel'),
    searchPanel: $('searchPanel'),
    tabAccounts: $('tabAccounts'),
    tabBookmarks: $('tabBookmarks'),
    tabProfiles: $('tabProfiles'),
    statAccounts: $('statAccounts'),
    statServices: $('statServices'),
    statProfiles: $('statProfiles'),
    statBookmarks: $('statBookmarks'),
    statLastScan: $('statLastScan'),
    statScanHint: $('statScanHint'),
    dataLocation: $('dataLocation'),
    accountModal: $('accountModal'),
    accountModalTitle: $('accountModalTitle'),
    accountForm: $('accountForm'),
    accountId: $('accountId'),
    accountError: $('accountError'),
    duplicateWarning: $('duplicateWarning'),
    accountSaveBtn: $('accountSaveBtn'),
    fService: $('fService'),
    fWebsite: $('fWebsite'),
    fEmail: $('fEmail'),
    fUsername: $('fUsername'),
    fCategory: $('fCategory'),
    fPassword: $('fPassword'),
    fNotes: $('fNotes'),
    fClearPassword: $('fClearPassword'),
    clearPasswordRow: $('clearPasswordRow'),
    chromePasswordNote: $('chromePasswordNote'),
    toggleFormPassword: $('toggleFormPassword'),
    profileChecks: $('profileChecks'),
    importModal: $('importModal'),
    importFile: $('importFile'),
    importProfile: $('importProfile'),
    importError: $('importError'),
    importPreview: $('importPreview'),
    importSummary: $('importSummary'),
    importRows: $('importRows'),
    importCommitBtn: $('importCommitBtn'),
    selectAllImport: $('selectAllImport'),
    selectNoneImport: $('selectNoneImport'),
    exportModal: $('exportModal'),
    exportPasswords: $('exportPasswords'),
    exportBtn: $('exportBtn'),
    backupModal: $('backupModal'),
    createBackupBtn: $('createBackupBtn'),
    backupList: $('backupList'),
    backupError: $('backupError'),
    restoreFile: $('restoreFile'),
  };

  // ------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeHttpUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const parsed = new URL(value);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.href;
    } catch (error) {
      return null;
    }
    return null;
  }

  function hostOf(value) {
    try {
      const parsed = new URL(value);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return parsed.host.replace(/^www\./i, '');
      }
    } catch (error) {
      return value || '';
    }
    return value || '';
  }

  function profileLabel(profile) {
    return profile.label || profile.display_name || profile.dir || 'Profile';
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
  }

  function plural(count, singular, pluralForm) {
    return `${count.toLocaleString()} ${count === 1 ? singular : pluralForm || singular + 's'}`;
  }

  function show(element) {
    element.classList.remove('hidden');
  }

  function hide(element) {
    element.classList.add('hidden');
  }

  function toast(message, type = 'info', timeout = 4500) {
    const node = document.createElement('div');
    node.className = `toast ${type}`;
    node.textContent = message;
    $('toasts').appendChild(node);
    window.setTimeout(() => {
      node.classList.add('leaving');
      window.setTimeout(() => node.remove(), 240);
    }, timeout);
  }

  async function api(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {};
    let body;
    if (options.form) {
      body = options.form;
    } else if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.body);
    }
    if (method !== 'GET' && method !== 'HEAD') {
      headers['X-CSRF-Token'] = csrfToken;
    }
    let response;
    try {
      response = await fetch(path, { method, headers, body, credentials: 'same-origin' });
    } catch (error) {
      throw new Error('Could not reach the local server. Is main.py still running?');
    }
    const text = await response.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (error) {
        data = { error: text };
      }
    }
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status}).`);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const helper = document.createElement('textarea');
    helper.value = value;
    helper.setAttribute('readonly', '');
    helper.className = 'sr-only';
    document.body.appendChild(helper);
    helper.select();
    document.execCommand('copy');
    helper.remove();
  }

  function downloadText(filename, content) {
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  // ------------------------------------------------------------------
  // Data loading and rendering
  // ------------------------------------------------------------------

  async function loadState() {
    const data = await api('/api/state');
    state.accounts = Array.isArray(data.accounts) ? data.accounts : [];
    state.bookmarks = Array.isArray(data.bookmarks) ? data.bookmarks : [];
    state.profiles = Array.isArray(data.profiles) ? data.profiles : [];
    state.stats = data.stats || {};
    state.categories = Array.isArray(data.categories) ? data.categories : [];
    state.warnings = Array.isArray(data.warnings) ? data.warnings : [];
    state.storage = data.storage || {};
    state.last_scan_at = data.last_scan_at || null;
    renderAll();
  }

  function renderAll() {
    renderStats();
    renderFilters();
    renderImportProfiles();
    renderTabs();
    renderWarnings();
    renderView();
    els.dataLocation.textContent = state.storage.data_dir || '';
    els.dataLocation.title = state.storage.permission_note || '';
  }

  function renderStats() {
    els.statAccounts.textContent = state.stats.accounts != null ? state.stats.accounts.toLocaleString() : '0';
    els.statServices.textContent = plural(state.stats.services || 0, 'service');
    els.statProfiles.textContent = state.stats.profiles != null ? state.stats.profiles.toLocaleString() : '0';
    els.statBookmarks.textContent = state.stats.bookmarks != null ? state.stats.bookmarks.toLocaleString() : '0';
    els.statLastScan.textContent = state.last_scan_at ? formatDate(state.last_scan_at) : 'Never';
    els.statScanHint.textContent = state.last_scan_at
      ? `${plural(state.stats.profiles || 0, 'profile')} scanned`
      : 'Run a scan to begin';
  }

  function renderTabs() {
    els.tabAccounts.textContent = state.accounts.length.toLocaleString();
    els.tabBookmarks.textContent = state.bookmarks.length.toLocaleString();
    els.tabProfiles.textContent = state.profiles.length.toLocaleString();
    document.querySelectorAll('.tab').forEach((tab) => {
      const isActive = tab.dataset.view === activeView;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', String(isActive));
    });
  }

  function renderImportProfiles() {
    if (!els.importProfile) return;
    const current = els.importProfile.value;
    els.importProfile.innerHTML =
      '<option value="">No profile</option>' +
      state.profiles
        .slice()
        .sort((a, b) => profileLabel(a).localeCompare(profileLabel(b)))
        .map(
          (profile) =>
            `<option value="${escapeHtml(profile.id)}">${escapeHtml(profileLabel(profile))}</option>`
        )
        .join('');
    if (current && state.profiles.some((profile) => profile.id === current)) {
      els.importProfile.value = current;
    }
  }

  function renderFilters() {
    const currentProfile = els.profileFilter.value;
    els.profileFilter.innerHTML =
      '<option value="">All profiles</option>' +
      state.profiles
        .slice()
        .sort((a, b) => profileLabel(a).localeCompare(profileLabel(b)))
        .map(
          (profile) =>
            `<option value="${escapeHtml(profile.id)}">${escapeHtml(profileLabel(profile))}</option>`
        )
        .join('');
    if (currentProfile && state.profiles.some((profile) => profile.id === currentProfile)) {
      els.profileFilter.value = currentProfile;
    }

    const currentCategory = els.categoryFilter.value;
    els.categoryFilter.innerHTML =
      '<option value="">All categories</option>' +
      state.categories
        .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
        .join('');
    if (currentCategory && state.categories.includes(currentCategory)) {
      els.categoryFilter.value = currentCategory;
    }

    const currentService = els.serviceFilter.value;
    const services = Array.from(
      new Set(state.accounts.map((account) => account.service).filter(Boolean))
    ).sort((a, b) => String(a).localeCompare(String(b)));
    els.serviceFilter.innerHTML =
      '<option value="">All services</option>' +
      services
        .map((service) => `<option value="${escapeHtml(service)}">${escapeHtml(service)}</option>`)
        .join('');
    if (currentService && services.includes(currentService)) {
      els.serviceFilter.value = currentService;
    }
  }

  function renderWarnings() {
    const hasWarnings = state.warnings.length > 0 && !warningsDismissed;
    els.warnings.classList.toggle('hidden', !hasWarnings);
    if (!hasWarnings) {
      els.warningList.innerHTML = '';
      return;
    }
    els.warningList.innerHTML = state.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('');
  }

  function currentQuery() {
    return els.searchInput.value.trim().toLowerCase();
  }

  function filterAccounts(query, options = {}) {
    const profile = els.profileFilter.value;
    const service = els.serviceFilter.value;
    const category = els.categoryFilter.value;
    const recordState = options.ignorePasswordFilter ? '' : els.passwordFilter.value;
    let accounts = state.accounts.filter((account) => {
      if (profile && !account.chrome_profiles.includes(profile)) return false;
      if (service && String(account.service || '').toLowerCase() !== service.toLowerCase()) {
        return false;
      }
      if (category && account.category !== category) return false;
      if (recordState === 'with' && !account.has_password) return false;
      if (recordState === 'without' && account.has_password) return false;
      if (
        recordState === 'chrome-only' &&
        !(account.chrome_password_present && !account.has_password)
      ) {
        return false;
      }
      if (
        recordState === 'missing' &&
        (account.has_password || account.chrome_password_present)
      ) {
        return false;
      }
      if (recordState === 'email' && !account.email) return false;
      if (recordState === 'no-email' && account.email) return false;
      if (query) {
        const haystack = [
          account.service,
          account.email,
          account.username,
          account.website,
          account.category,
          account.notes,
          ...(account.profile_names || []),
        ]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
    return sortAccounts(accounts);
  }

  function filterBookmarks(query) {
    const profile = els.profileFilter.value;
    let bookmarks = state.bookmarks.filter((bookmark) => {
      if (profile && bookmark.profile_id !== profile) return false;
      if (query) {
        const haystack = [
          bookmark.title,
          bookmark.url,
          bookmark.folder,
          bookmark.profile_name,
        ]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
    return sortBookmarks(bookmarks);
  }

  function sortAccounts(accounts) {
    const mode = els.sortSelect.value;
    const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });
    const copy = accounts.slice();
    if (mode === 'updated') {
      copy.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
    } else if (mode === 'email') {
      copy.sort((a, b) => collator.compare(a.email || a.username || '', b.email || b.username || ''));
    } else if (mode === 'profile') {
      copy.sort((a, b) =>
        collator.compare((a.profile_names || [])[0] || '', (b.profile_names || [])[0] || '')
      );
    } else {
      copy.sort((a, b) => collator.compare(a.service || '', b.service || ''));
    }
    return copy;
  }

  function sortBookmarks(bookmarks) {
    const mode = els.sortSelect.value;
    const collator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });
    const copy = bookmarks.slice();
    if (mode === 'updated') {
      copy.sort((a, b) => String(b.date_added || '').localeCompare(String(a.date_added || '')));
    } else if (mode === 'email') {
      copy.sort((a, b) => collator.compare(a.folder || '', b.folder || ''));
    } else if (mode === 'profile') {
      copy.sort((a, b) => collator.compare(a.profile_name || '', b.profile_name || ''));
    } else {
      copy.sort((a, b) => collator.compare(a.title || a.url || '', b.title || b.url || ''));
    }
    return copy;
  }

  function setPanel(name) {
    els.accountsPanel.classList.toggle('hidden', name !== 'accounts');
    els.bookmarksPanel.classList.toggle('hidden', name !== 'bookmarks');
    els.profilesPanel.classList.toggle('hidden', name !== 'profiles');
    els.searchPanel.classList.toggle('hidden', name !== 'search');
  }

  function renderView() {
    renderTabs();
    const query = currentQuery();
    if (query) {
      setPanel('search');
      renderSearch(query);
      return;
    }
    setPanel(activeView);
    if (activeView === 'accounts') renderAccountsPanel();
    else if (activeView === 'bookmarks') renderBookmarksPanel();
    else renderProfilesPanel();
  }

  function emptyState(title, message, actions) {
    return `<div class="empty">
      <div class="empty-icon" aria-hidden="true">⌕</div>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(message)}</p>
      <div class="empty-actions">${actions}</div>
    </div>`;
  }

  function renderAccountsPanel() {
    const allEmpty = state.accounts.length === 0;
    const accounts = filterAccounts('');
    if (allEmpty) {
      els.accountsPanel.innerHTML = emptyState(
        'No accounts yet',
        "Add one manually, import Chrome's password CSV, or use Data → Import Chrome logins to pull emails and usernames from Chrome. Passwords stay encrypted in Chrome.",
        `<button type="button" class="btn btn-primary" data-action="open-add">+ Add account</button>
         <button type="button" class="btn" data-action="run-scan">Scan Chrome</button>`
      );
      return;
    }
    if (accounts.length === 0) {
      els.accountsPanel.innerHTML = emptyState(
        'No accounts match',
        'Try a different search term or clear the filters.',
        '<button type="button" class="btn" data-action="reset-filters">Reset filters</button>'
      );
      return;
    }
    els.accountsPanel.innerHTML =
      `<div class="table-scroll">${accountTable(accounts)}</div>` +
      (accounts.length > 400
        ? '<p class="empty-note">Showing all results. Use search to narrow them down.</p>'
        : '');
  }

  function renderBookmarksPanel() {
    const allEmpty = state.bookmarks.length === 0;
    const bookmarks = filterBookmarks('');
    if (allEmpty) {
      const hasProfiles = state.profiles.length > 0;
      els.bookmarksPanel.innerHTML = emptyState(
        'No bookmarks indexed',
        hasProfiles
          ? 'Run a scan to read the Bookmarks file of each Chrome profile. Bookmarks are stored locally and can be searched here.'
          : 'Scan Chrome to discover profiles first. Bookmark files are read from each profile.',
        '<button type="button" class="btn btn-primary" data-action="run-scan">Scan Chrome</button>'
      );
      return;
    }
    if (bookmarks.length === 0) {
      els.bookmarksPanel.innerHTML = emptyState(
        'No bookmarks match',
        'Try a different search term or clear the profile filter.',
        '<button type="button" class="btn" data-action="reset-filters">Reset filters</button>'
      );
      return;
    }
    const visible = bookmarks.slice(0, 400);
    els.bookmarksPanel.innerHTML =
      `<div class="section-title"><h3>Indexed bookmarks</h3><span class="count">${plural(
        bookmarks.length,
        'result'
      )}${bookmarks.length > visible.length ? ` · showing first ${visible.length}` : ''}</span></div>` +
      `<div class="table-scroll">${bookmarkTable(visible)}</div>` +
      '<p class="empty-note">Removing a bookmark only removes it from this local index. The next scan will index it again.</p>';
  }

  function renderProfilesPanel() {
    if (state.profiles.length === 0) {
      els.profilesPanel.innerHTML = emptyState(
        'No Chrome profiles discovered',
        'Run a scan to look for Chrome, Chrome Beta, Chrome Dev, Chrome Canary, and Chromium profiles in your Windows account.',
        '<button type="button" class="btn btn-primary" data-action="run-scan">Scan Chrome</button>'
      );
      return;
    }
    const cards = state.profiles
      .slice()
      .sort((a, b) => profileLabel(a).localeCompare(profileLabel(b)))
      .map((profile) => {
        const ok = profile.status !== 'bookmarks-unreadable';
        return `<article class="profile-card">
          <div class="profile-card-head">
            <div>
              <h3>${escapeHtml(profileLabel(profile))}</h3>
              <p class="profile-email">${escapeHtml(profile.google_email || 'Google account email not exposed')}</p>
            </div>
            <span class="badge ${ok ? 'badge-accent' : 'badge-warning'}">${escapeHtml(
          profile.channel || 'Chrome'
        )}</span>
          </div>
          <dl class="profile-meta">
            <div><dt>Directory</dt><dd>${escapeHtml(profile.dir || '—')}</dd></div>
            <div><dt>Path</dt><dd title="${escapeHtml(profile.path || '')}">${escapeHtml(
          profile.path || '—'
        )}</dd></div>
            <div><dt>Last scanned</dt><dd>${escapeHtml(formatDate(profile.last_scanned_at))}</dd></div>
          </dl>
          <div class="profile-counts">
            <span class="badge badge-success">${plural(profile.account_count || 0, 'account')}</span>
            <span class="badge">${plural(profile.bookmark_count || 0, 'bookmark')}</span>
            ${
              profile.chrome_password_count
                ? `<span class="badge badge-warning">${plural(
                    profile.chrome_password_count,
                    'Chrome password'
                  )} to import</span>`
                : ''
            }
            ${ok ? '' : '<span class="badge badge-warning">Bookmarks unreadable</span>'}
          </div>
        </article>`;
      })
      .join('');
    els.profilesPanel.innerHTML = `<div class="profile-grid">${cards}</div>`;
  }

  function renderSearch(query) {
    const displayQuery = els.searchInput.value.trim();
    const accounts = filterAccounts(query);
    const bookmarks = filterBookmarks(query);
    const accountLimit = 100;
    const bookmarkLimit = 150;
    const sections = [];

    sections.push(
      `<div class="section-title"><h3>Accounts</h3><span class="count">${plural(
        accounts.length,
        'match'
      )}</span></div>`
    );
    sections.push(
      accounts.length
        ? `<div class="table-scroll">${accountTable(accounts.slice(0, accountLimit))}</div>`
        : '<p class="empty-note">No matching accounts.</p>'
    );
    if (accounts.length > accountLimit) {
      sections.push(`<p class="empty-note">Showing the first ${accountLimit} account matches.</p>`);
    }

    sections.push(
      `<div class="section-title"><h3>Bookmarks</h3><span class="count">${plural(
        bookmarks.length,
        'match'
      )}</span></div>`
    );
    sections.push(
      bookmarks.length
        ? `<div class="table-scroll">${bookmarkTable(bookmarks.slice(0, bookmarkLimit))}</div>`
        : '<p class="empty-note">No matching bookmarks.</p>'
    );
    if (bookmarks.length > bookmarkLimit) {
      sections.push(`<p class="empty-note">Showing the first ${bookmarkLimit} bookmark matches.</p>`);
    }

    if (accounts.length === 0 && bookmarks.length === 0) {
      els.searchPanel.innerHTML = emptyState(
        `No results for “${displayQuery}”`,
        'Search covers service names, emails, usernames, URLs, folders, profiles, categories, and notes. Passwords are never searched.',
        '<button type="button" class="btn" data-action="reset-filters">Clear search</button>'
      );
      return;
    }

    els.searchPanel.innerHTML = sections.join('');
  }

  function profileBadges(account) {
    const names = account.profile_names || [];
    if (!names.length) return '<span class="badge">Unknown</span>';
    return `<div class="profile-tags">${names
      .map((name) => `<span class="badge badge-accent">${escapeHtml(name)}</span>`)
      .join('')}</div>`;
  }

  function accountTable(accounts) {
    return `<table class="data-table">
      <thead>
        <tr>
          <th>Service</th>
          <th class="hide-md">Email</th>
          <th class="hide-md">Username</th>
          <th>Chrome profile</th>
          <th class="hide-sm">Category</th>
          <th>Password</th>
          <th class="hide-sm">Updated</th>
          <th class="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>${accounts.map(accountRow).join('')}</tbody>
    </table>`;
  }

  function accountRow(account) {
    const website = safeHttpUrl(account.website);
    const categorySlug = String(account.category || 'Other')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-');
    const serviceCell = website
      ? `<a class="cell-title" href="${escapeHtml(website)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
          account.service
        )}</a>`
      : `<span class="cell-title">${escapeHtml(account.service)}</span>`;
    const websiteLine = account.website
      ? `<span class="cell-sub">${escapeHtml(hostOf(account.website))}</span>`
      : '';
    const passwordCell = account.has_password
      ? `<button type="button" class="link-btn" data-action="reveal-password" data-id="${escapeHtml(
          account.id
        )}">••••••</button>`
      : account.chrome_password_present
        ? `<span class="badge badge-warning" title="Chrome has an encrypted password for this account. Import Chrome's password CSV to use it here.">Chrome encrypted</span>`
        : '<span class="muted">—</span>';
    return `<tr>
      <td class="primary-cell">${serviceCell}${websiteLine}</td>
      <td class="hide-md">${account.email ? escapeHtml(account.email) : '<span class="muted">—</span>'}</td>
      <td class="hide-md">${account.username ? escapeHtml(account.username) : '<span class="muted">—</span>'}</td>
      <td>${profileBadges(account)}</td>
      <td class="hide-sm"><span class="badge category-badge category-${escapeHtml(
        categorySlug
      )}">${escapeHtml(account.category || 'Other')}</span></td>
      <td class="password-cell" data-password-cell="${escapeHtml(account.id)}">${passwordCell}</td>
      <td class="hide-sm muted">${escapeHtml(formatDate(account.updated_at))}</td>
      <td>
        <div class="row-actions">
          <button type="button" class="link-btn" data-action="edit-account" data-id="${escapeHtml(
            account.id
          )}">Edit</button>
          <button type="button" class="link-btn danger" data-action="delete-account" data-id="${escapeHtml(
            account.id
          )}">Delete</button>
        </div>
      </td>
    </tr>`;
  }

  function bookmarkTable(bookmarks) {
    return `<table class="data-table">
      <thead>
        <tr>
          <th>Bookmark</th>
          <th class="hide-md">Folder</th>
          <th>Profile</th>
          <th class="hide-sm">Added</th>
          <th class="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>${bookmarks.map(bookmarkRow).join('')}</tbody>
    </table>`;
  }

  function bookmarkRow(bookmark) {
    const url = safeHttpUrl(bookmark.url);
    const title = bookmark.title || bookmark.url || '(untitled)';
    const titleHtml = url
      ? `<a class="cell-title" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
          title
        )}</a>`
      : `<span class="cell-title">${escapeHtml(title)}</span>`;
    return `<tr>
      <td class="primary-cell">
        ${titleHtml}
        <span class="cell-sub">${escapeHtml(hostOf(bookmark.url || ''))}</span>
      </td>
      <td class="hide-md">${bookmark.folder ? escapeHtml(bookmark.folder) : '<span class="muted">—</span>'}</td>
      <td><span class="badge badge-accent">${escapeHtml(bookmark.profile_name || 'Unknown')}</span></td>
      <td class="hide-sm muted">${escapeHtml(formatDate(bookmark.date_added))}</td>
      <td>
        <div class="row-actions">
          <button type="button" class="link-btn" data-action="bookmark-to-account" data-id="${escapeHtml(
            bookmark.id
          )}">→ Account</button>
          <button type="button" class="link-btn" data-action="copy-bookmark" data-id="${escapeHtml(
            bookmark.id
          )}">Copy link</button>
          <button type="button" class="link-btn danger" data-action="delete-bookmark" data-id="${escapeHtml(
            bookmark.id
          )}">Remove</button>
        </div>
      </td>
    </tr>`;
  }

  // ------------------------------------------------------------------
  // Modal helpers
  // ------------------------------------------------------------------

  function openModal(id) {
    const modal = $(id);
    if (!modal) return;
    modal.classList.remove('hidden');
    openModalId = id;
    const focusable =
      modal.querySelector('input:not([type="hidden"]):not(.sr-only), select, textarea') ||
      modal.querySelector('button');
    if (focusable) {
      window.setTimeout(() => focusable.focus(), 30);
    }
  }

  function closeModal(id) {
    const modal = $(id);
    if (!modal) return;
    modal.classList.add('hidden');
    if (openModalId === id) openModalId = null;
    if (id === 'importModal') {
      importState = { content: '', records: [] };
      els.importPreview.classList.add('hidden');
      els.importFile.value = '';
      hide(els.importError);
    }
    if (id === 'backupModal') {
      els.restoreFile.value = '';
      hide(els.backupError);
    }
    if (id === 'accountModal') {
      els.accountForm.reset();
      els.fPassword.type = 'password';
      els.toggleFormPassword.textContent = 'Show';
      hide(els.accountError);
      hide(els.duplicateWarning);
    }
  }

  // ------------------------------------------------------------------
  // Account modal
  // ------------------------------------------------------------------

  function renderProfileChecks(selectedIds) {
    const selected = Array.isArray(selectedIds) ? selectedIds : [];
    const knownIds = new Set(state.profiles.map((profile) => profile.id));
    const unknown = selected.filter((id) => !knownIds.has(id));
    if (state.profiles.length === 0 && unknown.length === 0) {
      els.profileChecks.innerHTML =
        '<p class="muted">No Chrome profiles discovered yet. Run a scan to link accounts to profiles.</p>';
      return;
    }
    const knownHtml = state.profiles
      .slice()
      .sort((a, b) => profileLabel(a).localeCompare(profileLabel(b)))
      .map((profile) => {
        const checked = selected.includes(profile.id) ? ' checked' : '';
        const email = profile.google_email
          ? ` <span class="muted">(${escapeHtml(profile.google_email)})</span>`
          : '';
        return `<label class="checkbox"><input type="checkbox" value="${escapeHtml(
          profile.id
        )}"${checked}> ${escapeHtml(profileLabel(profile))}${email}</label>`;
      })
      .join('');
    const unknownHtml = unknown
      .map(
        (id) =>
          `<label class="checkbox"><input type="checkbox" value="${escapeHtml(
            id
          )}" checked> Unknown profile <span class="muted">(${escapeHtml(id)})</span></label>`
      )
      .join('');
    els.profileChecks.innerHTML = knownHtml + unknownHtml;
  }

  function openAccountModal(account = null, prefill = null) {
    els.accountForm.reset();
    els.accountId.value = account ? account.id : '';
    els.accountModalTitle.textContent = account ? 'Edit account' : 'Add account';
    els.accountSaveBtn.textContent = account ? 'Save changes' : 'Save account';
    hide(els.accountError);
    hide(els.duplicateWarning);
    els.duplicateWarning.innerHTML = '';
    els.fPassword.value = '';
    els.fPassword.type = 'password';
    els.toggleFormPassword.textContent = 'Show';
    els.fClearPassword.checked = false;
    els.clearPasswordRow.classList.toggle('hidden', !(account && account.has_password));
    els.fPassword.placeholder =
      account && account.has_password
        ? 'Leave blank to keep the saved password'
        : account && account.chrome_password_present
          ? 'Chrome has this encrypted; enter it or import the CSV'
          : account
            ? 'Optional password'
            : 'Optional';
    els.chromePasswordNote.classList.toggle(
      'hidden',
      !(account && account.chrome_password_present && !account.has_password)
    );

    els.fService.value = account ? account.service || '' : prefill ? prefill.service || '' : '';
    els.fWebsite.value = account ? account.website || '' : prefill ? prefill.website || '' : '';
    els.fEmail.value = account ? account.email || '' : '';
    els.fUsername.value = account ? account.username || '' : '';
    els.fNotes.value = account ? account.notes || '' : '';

    els.fCategory.innerHTML = state.categories
      .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
      .join('');
    els.fCategory.value = account && state.categories.includes(account.category) ? account.category : 'Personal';

    renderProfileChecks(account ? account.chrome_profiles || [] : []);
    openModal('accountModal');

    if (prefill) {
      window.setTimeout(() => els.fEmail.focus(), 60);
    } else if (account) {
      window.setTimeout(() => els.fService.focus(), 60);
    }
  }

  function showAccountError(message) {
    els.accountError.textContent = message;
    show(els.accountError);
  }

  function showDuplicates(duplicates) {
    const rows = duplicates
      .map(
        (duplicate) => `<li><strong>${escapeHtml(duplicate.service || 'Account')}</strong>
          ${duplicate.email ? `· ${escapeHtml(duplicate.email)}` : ''}
          ${duplicate.username ? `· ${escapeHtml(duplicate.username)}` : ''}
          <span class="muted">(${escapeHtml((duplicate.reasons || []).join(', '))})</span></li>`
      )
      .join('');
    els.duplicateWarning.innerHTML = `<strong>Possible duplicate${duplicates.length === 1 ? '' : 's'} found.</strong>
      <ul>${rows}</ul>
      <p>Nothing was merged. You can go back and edit, or keep this as a separate account.</p>
      <div class="dup-actions">
        <button type="button" class="btn btn-small btn-primary" data-action="save-anyway">Save anyway</button>
        <button type="button" class="btn btn-small btn-ghost" data-action="dismiss-duplicates">Go back</button>
      </div>`;
    show(els.duplicateWarning);
  }

  async function saveAccount(confirmDuplicate = false) {
    const accountId = els.accountId.value;
    const service = els.fService.value.trim();
    const email = els.fEmail.value.trim();
    const username = els.fUsername.value.trim();

    hide(els.accountError);
    if (!service) {
      showAccountError('Service name is required.');
      els.fService.focus();
      return;
    }
    if (!email && !username) {
      showAccountError('Provide at least one of email or username.');
      els.fEmail.focus();
      return;
    }
    if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      showAccountError('Enter a valid email address, or leave the email empty and use a username.');
      els.fEmail.focus();
      return;
    }

    const payload = {
      service,
      website: els.fWebsite.value.trim(),
      email,
      username,
      category: els.fCategory.value,
      notes: els.fNotes.value,
      chrome_profiles: Array.from(
        els.profileChecks.querySelectorAll('input[type="checkbox"]:checked')
      ).map((input) => input.value),
    };
    if (els.fPassword.value) payload.password = els.fPassword.value;
    if (accountId && els.fClearPassword.checked) payload.clear_password = true;
    if (confirmDuplicate) payload.confirm_duplicate = true;

    const originalLabel = els.accountSaveBtn.textContent;
    els.accountSaveBtn.disabled = true;
    els.accountSaveBtn.textContent = 'Saving…';
    try {
      await api(accountId ? `/api/accounts/${accountId}` : '/api/accounts', {
        method: accountId ? 'PUT' : 'POST',
        body: payload,
      });
      closeModal('accountModal');
      await loadState();
      toast(accountId ? 'Account updated.' : 'Account added.', 'success');
    } catch (error) {
      if (error.status === 409 && error.data && Array.isArray(error.data.duplicates)) {
        showDuplicates(error.data.duplicates);
      } else {
        showAccountError(error.message);
      }
    } finally {
      els.accountSaveBtn.disabled = false;
      els.accountSaveBtn.textContent = originalLabel;
    }
  }

  async function deleteAccount(accountId) {
    const account = state.accounts.find((item) => item.id === accountId);
    if (!account) return;
    const confirmed = window.confirm(
      `Delete "${account.service}" from the inventory?\n\nThis does not delete the account from the website or from Chrome. The saved password copy is also removed from this app.`
    );
    if (!confirmed) return;
    try {
      await api(`/api/accounts/${accountId}`, { method: 'DELETE' });
      await loadState();
      toast('Account deleted.', 'success');
    } catch (error) {
      toast(error.message, 'error', 6500);
    }
  }

  // ------------------------------------------------------------------
  // Password reveal
  // ------------------------------------------------------------------

  function passwordMaskHtml(accountId) {
    return `<button type="button" class="link-btn" data-action="reveal-password" data-id="${escapeHtml(
      accountId
    )}">••••••</button>`;
  }

  function resetPasswordCells(accountId) {
    document.querySelectorAll(`[data-password-cell="${accountId}"]`).forEach((cell) => {
      if (cell.dataset.revealed === '1') {
        cell.dataset.revealed = '0';
        cell.innerHTML = passwordMaskHtml(accountId);
      }
    });
  }

  async function revealPassword(accountId, button) {
    try {
      const data = await api(`/api/accounts/${accountId}/reveal`, { method: 'POST' });
      const cell = button.closest('td');
      if (!cell) return;
      cell.dataset.revealed = '1';
      cell.innerHTML = `<span class="secret">${escapeHtml(data.password)}</span>`;
      const controls = document.createElement('div');
      controls.className = 'row-actions password-actions';
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'link-btn';
      copy.dataset.action = 'copy-password';
      copy.dataset.id = accountId;
      copy.textContent = 'Copy';
      const hideButton = document.createElement('button');
      hideButton.type = 'button';
      hideButton.className = 'link-btn';
      hideButton.dataset.action = 'hide-password';
      hideButton.dataset.id = accountId;
      hideButton.textContent = 'Hide';
      controls.appendChild(copy);
      controls.appendChild(hideButton);
      cell.appendChild(controls);
      window.clearTimeout(cell._hideTimer);
      cell._hideTimer = window.setTimeout(() => resetPasswordCells(accountId), 30000);
    } catch (error) {
      toast(error.message, 'error', 6000);
    }
  }

  async function copyPassword(accountId) {
    try {
      const data = await api(`/api/accounts/${accountId}/reveal`, { method: 'POST' });
      await copyText(data.password);
      toast('Password copied to clipboard.', 'success');
    } catch (error) {
      toast(error.message, 'error', 6000);
    }
  }

  // ------------------------------------------------------------------
  // Bookmark actions
  // ------------------------------------------------------------------

  function findBookmark(id) {
    return state.bookmarks.find((bookmark) => bookmark.id === id);
  }

  async function copyBookmark(id) {
    const bookmark = findBookmark(id);
    if (!bookmark) return;
    try {
      await copyText(bookmark.url);
      toast('Bookmark link copied.', 'success');
    } catch (error) {
      toast('Could not copy the link.', 'error');
    }
  }

  async function deleteBookmark(id) {
    const bookmark = findBookmark(id);
    if (!bookmark) return;
    const confirmed = window.confirm(
      `Remove "${bookmark.title || bookmark.url}" from the local bookmark index?\n\nThe next Chrome scan will index it again.`
    );
    if (!confirmed) return;
    try {
      await api(`/api/bookmarks/${id}`, { method: 'DELETE' });
      await loadState();
      toast('Bookmark removed from the local index.', 'success');
    } catch (error) {
      toast(error.message, 'error', 6500);
    }
  }

  // ------------------------------------------------------------------
  // Scan
  // ------------------------------------------------------------------

  async function runScan() {
    const original = els.scanBtn.textContent;
    els.scanBtn.disabled = true;
    els.scanBtn.textContent = 'Scanning…';
    try {
      const result = await api('/api/scan', { method: 'POST' });
      warningsDismissed = false;
      await loadState();
      toast(
        `Scan complete: ${plural(result.profile_count, 'profile')}, ${plural(
          result.bookmark_count,
          'bookmark'
        )}.`,
        result.warnings && result.warnings.length ? 'warn' : 'success',
        6000
      );
      toast(
        result.accounts_note ||
          'Chrome scans index profiles and bookmarks only; accounts are added or imported manually.',
        'info',
        8000
      );
    } catch (error) {
      toast(error.message, 'error', 8000);
    } finally {
      els.scanBtn.disabled = false;
      els.scanBtn.textContent = original;
    }
  }

  // ------------------------------------------------------------------
  // Chrome Login Data metadata
  // ------------------------------------------------------------------

  async function importChromeLogins() {
    const confirmed = window.confirm(
      `Read account emails, usernames, and website URLs from Chrome's Login Data for this Windows user?

This does NOT decrypt or import passwords. Chrome stores them with App-Bound Encryption (v20), so passwords stay in Chrome. Use Data → Import accounts… with Chrome's password CSV to import passwords.

Accounts will be created and linked to their Chrome profiles.`
    );
    if (!confirmed) return;
    try {
      const result = await api('/api/chrome/logins/import', { method: 'POST' });
      await loadState();
      const parts = [];
      if (result.accounts_created) {
        parts.push(`${plural(result.accounts_created, 'account')} created`);
      }
      if (result.accounts_linked) {
        parts.push(`${plural(result.accounts_linked, 'profile link')} added`);
      }
      if (result.skipped) parts.push(`${result.skipped} skipped`);
      const summary = parts.length
        ? parts.join(' · ')
        : result.logins_found
          ? 'already up to date'
          : 'no saved logins found';
      const passwordNote = result.encrypted_passwords_skipped
        ? ` ${plural(result.encrypted_passwords_skipped, 'encrypted password')} stayed in Chrome.`
        : '';
      toast(
        `Chrome logins: ${summary}.${passwordNote}`,
        result.warnings && result.warnings.length ? 'warn' : 'success',
        9000
      );
      if (result.warnings && result.warnings.length) {
        toast(result.warnings.slice(0, 3).join(' '), 'warn', 9000);
      }
    } catch (error) {
      toast(error.message, 'error', 8000);
    }
  }

  // ------------------------------------------------------------------
  // Import
  // ------------------------------------------------------------------

  function showImportError(message) {
    els.importError.textContent = message;
    show(els.importError);
  }

  async function previewImport() {
    const file = els.importFile.files[0];
    if (!file) return;
    hide(els.importError);
    if (file.size > 5 * 1024 * 1024) {
      showImportError('The import file is too large (limit 5 MB).');
      return;
    }
    try {
      importState.content = await file.text();
      const result = await api('/api/import/preview', {
        method: 'POST',
        body: { content: importState.content },
      });
      importState.records = result.records || [];
      renderImportPreview();
    } catch (error) {
      showImportError(error.message);
      els.importPreview.classList.add('hidden');
      els.importCommitBtn.disabled = true;
    }
  }

  function renderImportPreview() {
    const records = importState.records;
    if (!records.length) {
      showImportError('No account records were found in the file.');
      els.importPreview.classList.add('hidden');
      els.importCommitBtn.disabled = true;
      return;
    }
    const validCount = records.filter((record) => record.valid).length;
    els.importSummary.textContent = `Preview · ${plural(records.length, 'record')} · ${plural(
      validCount,
      'valid record'
    )}`;

    els.importRows.innerHTML = records
      .map((record) => {
        const duplicate = record.duplicates && record.duplicates.length > 0;
        const checked = record.valid && !duplicate;
        let status;
        if (!record.valid) {
          status = `<span class="badge badge-warning">${escapeHtml(record.error || 'Invalid')}</span>`;
        } else if (duplicate) {
          status = `<span class="badge badge-warning" title="${escapeHtml(
            record.duplicates.map((item) => item.reasons.join(', ')).join(' | ')
          )}">Possible duplicate</span>`;
        } else {
          status = '<span class="badge badge-success">Ready</span>';
        }
        const identity = record.raw.email || record.raw.username || '—';
        return `<tr>
          <td class="check-col">
            <input type="checkbox" data-index="${record.index}" ${
          record.valid ? '' : 'disabled'
        } ${checked ? 'checked' : ''} aria-label="Import record ${record.index + 1}">
          </td>
          <td>
            <span class="cell-title">${escapeHtml(record.raw.service || '(missing service)')}</span>
            ${record.raw.has_password ? '<span class="cell-sub">Password included</span>' : ''}
          </td>
          <td>${escapeHtml(identity)}</td>
          <td>${status}</td>
        </tr>`;
      })
      .join('');

    els.importPreview.classList.remove('hidden');
    updateImportCommitState();
  }

  function updateImportCommitState() {
    const selected = els.importRows.querySelectorAll('input[type="checkbox"]:checked').length;
    els.importCommitBtn.disabled = selected === 0;
    els.importCommitBtn.textContent = selected
      ? `Import ${selected} selected`
      : 'Import selected';
  }

  async function commitImport() {
    const indexes = Array.from(
      els.importRows.querySelectorAll('input[type="checkbox"]:checked')
    ).map((input) => Number(input.dataset.index));
    if (!indexes.length) {
      showImportError('Select at least one record to import.');
      return;
    }
    els.importCommitBtn.disabled = true;
    try {
      const result = await api('/api/import/commit', {
        method: 'POST',
        body: {
          content: importState.content,
          indexes,
          chrome_profile_id: els.importProfile.value || null,
        },
      });
      closeModal('importModal');
      await loadState();
      const message = `Imported ${plural(result.imported, 'account')}${
        result.updated ? ` · updated ${plural(result.updated, 'account')}` : ''
      }${result.skipped ? ` · skipped ${result.skipped}` : ''}.`;
      toast(message, result.errors && result.errors.length ? 'warn' : 'success', 7000);
      if (result.errors && result.errors.length) {
        toast(result.errors.slice(0, 3).join(' '), 'error', 9000);
      }
    } catch (error) {
      showImportError(error.message);
      updateImportCommitState();
    }
  }

  // ------------------------------------------------------------------
  // Export
  // ------------------------------------------------------------------

  async function runExport() {
    const includePasswords = els.exportPasswords.checked;
    if (
      includePasswords &&
      !window.confirm(
        'This export will contain every saved password as plaintext. Continue only if you will store the file somewhere private.'
      )
    ) {
      return;
    }
    els.exportBtn.disabled = true;
    try {
      const result = await api('/api/export', {
        method: 'POST',
        body: { include_passwords: includePasswords },
      });
      downloadText(result.filename, result.content);
      closeModal('exportModal');
      toast(
        `Exported ${plural(result.count, 'account')}${
          result.includes_passwords ? ' with plaintext passwords' : ''
        }.`,
        result.includes_passwords ? 'warn' : 'success',
        6500
      );
    } catch (error) {
      toast(error.message, 'error', 7000);
    } finally {
      els.exportBtn.disabled = false;
    }
  }

  // ------------------------------------------------------------------
  // Backups
  // ------------------------------------------------------------------

  function showBackupError(message) {
    if (!message) {
      hide(els.backupError);
      return;
    }
    els.backupError.textContent = message;
    show(els.backupError);
  }

  async function refreshBackups() {
    try {
      const data = await api('/api/backups');
      const backups = Array.isArray(data.backups) ? data.backups : [];
      if (!backups.length) {
        els.backupList.innerHTML = '<p class="empty-note">No backups yet. Create one before making bulk changes.</p>';
        return;
      }
      els.backupList.innerHTML = backups
        .map(
          (backup) => `<div class="backup-row">
            <div>
              <div class="backup-name">${escapeHtml(backup.name)}</div>
              <div class="backup-meta">${escapeHtml(formatBytes(backup.bytes))} · ${escapeHtml(
            formatDate(backup.modified_at)
          )}</div>
            </div>
            <div class="backup-row-actions">
              <a class="link-btn" href="/api/backups/${encodeURIComponent(backup.name)}/download">Download</a>
              <button type="button" class="link-btn danger" data-action="restore-backup" data-name="${escapeHtml(
                backup.name
              )}">Restore</button>
            </div>
          </div>`
        )
        .join('');
    } catch (error) {
      showBackupError(error.message);
    }
  }

  async function openBackups() {
    showBackupError('');
    openModal('backupModal');
    els.backupList.innerHTML = '<p class="empty-note">Loading…</p>';
    await refreshBackups();
  }

  async function createBackup() {
    els.createBackupBtn.disabled = true;
    try {
      const result = await api('/api/backups', { method: 'POST' });
      await refreshBackups();
      toast(`Backup created: ${result.backup.name}`, 'success', 6500);
    } catch (error) {
      showBackupError(error.message);
    } finally {
      els.createBackupBtn.disabled = false;
    }
  }

  async function restoreBackup(name) {
    const confirmed = window.confirm(
      `Restore "${name}"?\n\nThis replaces the current accounts, profiles, bookmarks, and credentials. A safety backup of the current data will be created first.`
    );
    if (!confirmed) return;
    try {
      const result = await api('/api/backups/restore', {
        method: 'POST',
        body: { name, confirm_replace: true },
      });
      closeModal('backupModal');
      await loadState();
      toast(`Backup restored. Safety backup: ${result.safety_backup}`, 'success', 8000);
    } catch (error) {
      showBackupError(error.message);
    }
  }

  async function restoreFromUpload() {
    const file = els.restoreFile.files[0];
    if (!file) return;
    const confirmed = window.confirm(
      `Restore data from "${file.name}"?\n\nThis replaces the current accounts, profiles, bookmarks, and credentials. A safety backup will be created first.`
    );
    els.restoreFile.value = '';
    if (!confirmed) return;
    showBackupError('');
    const form = new FormData();
    form.append('file', file);
    form.append('confirm_replace', 'true');
    try {
      const result = await api('/api/backups/upload', { method: 'POST', form });
      closeModal('backupModal');
      await loadState();
      toast(`Backup restored. Safety backup: ${result.safety_backup}`, 'success', 8000);
    } catch (error) {
      showBackupError(error.message);
    }
  }

  // ------------------------------------------------------------------
  // Event wiring
  // ------------------------------------------------------------------

  function resetFilters() {
    els.searchInput.value = '';
    els.profileFilter.value = '';
    els.serviceFilter.value = '';
    els.categoryFilter.value = '';
    els.passwordFilter.value = '';
    els.sortSelect.value = 'name';
    renderView();
  }

  function bindEvents() {
    els.scanBtn.addEventListener('click', runScan);
    els.addAccountBtn.addEventListener('click', () => openAccountModal());

    els.dataMenuBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      const isHidden = els.dataMenu.classList.contains('hidden');
      els.dataMenu.classList.toggle('hidden', !isHidden);
      els.dataMenuBtn.setAttribute('aria-expanded', String(isHidden));
    });

    document.addEventListener('click', (event) => {
      if (!els.dataMenu.classList.contains('hidden') && !event.target.closest('.menu-wrap')) {
        els.dataMenu.classList.add('hidden');
        els.dataMenuBtn.setAttribute('aria-expanded', 'false');
      }
    });

    els.dataMenu.addEventListener('click', (event) => {
      const button = event.target.closest('[data-action]');
      if (!button) return;
      els.dataMenu.classList.add('hidden');
      els.dataMenuBtn.setAttribute('aria-expanded', 'false');
      if (button.dataset.action === 'open-import') {
        hide(els.importError);
        els.importPreview.classList.add('hidden');
        els.importFile.value = '';
        renderImportProfiles();
        els.importProfile.value = '';
        openModal('importModal');
      } else if (button.dataset.action === 'import-chrome-logins') {
        importChromeLogins();
      } else if (button.dataset.action === 'open-export') {
        els.exportPasswords.checked = false;
        openModal('exportModal');
      } else if (button.dataset.action === 'open-backup') {
        openBackups();
      }
    });

    document.querySelectorAll('.tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        activeView = tab.dataset.view;
        if (els.searchInput.value) els.searchInput.value = '';
        renderView();
      });
    });

    els.searchInput.addEventListener('input', renderView);
    [
      els.profileFilter,
      els.serviceFilter,
      els.categoryFilter,
      els.passwordFilter,
      els.sortSelect,
    ].forEach((control) => {
      control.addEventListener('change', renderView);
    });
    els.resetFilters.addEventListener('click', resetFilters);

    els.dismissWarnings.addEventListener('click', () => {
      warningsDismissed = true;
      renderWarnings();
    });

    els.accountsPanel.addEventListener('click', handleResultClick);
    els.bookmarksPanel.addEventListener('click', handleResultClick);
    els.profilesPanel.addEventListener('click', handleResultClick);
    els.searchPanel.addEventListener('click', handleResultClick);

    document.querySelectorAll('[data-close]').forEach((button) => {
      button.addEventListener('click', () => closeModal(button.dataset.close));
    });

    document.querySelectorAll('.modal').forEach((modal) => {
      modal.addEventListener('mousedown', (event) => {
        if (event.target === modal) closeModal(modal.id);
      });
    });

    els.accountForm.addEventListener('submit', (event) => {
      event.preventDefault();
      saveAccount(false);
    });

    els.toggleFormPassword.addEventListener('click', () => {
      const showing = els.fPassword.type === 'text';
      els.fPassword.type = showing ? 'password' : 'text';
      els.toggleFormPassword.textContent = showing ? 'Show' : 'Hide';
    });

    els.duplicateWarning.addEventListener('click', (event) => {
      const button = event.target.closest('[data-action]');
      if (!button) return;
      if (button.dataset.action === 'save-anyway') saveAccount(true);
      else if (button.dataset.action === 'dismiss-duplicates') hide(els.duplicateWarning);
    });

    els.importFile.addEventListener('change', previewImport);
    els.importRows.addEventListener('change', updateImportCommitState);
    els.importCommitBtn.addEventListener('click', commitImport);
    els.selectAllImport.addEventListener('click', () => {
      els.importRows.querySelectorAll('input[type="checkbox"]:not(:disabled)').forEach((input) => {
        input.checked = true;
      });
      updateImportCommitState();
    });
    els.selectNoneImport.addEventListener('click', () => {
      els.importRows.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = false;
      });
      updateImportCommitState();
    });

    els.exportBtn.addEventListener('click', runExport);

    els.createBackupBtn.addEventListener('click', createBackup);
    els.restoreFile.addEventListener('change', restoreFromUpload);
    els.backupList.addEventListener('click', (event) => {
      const button = event.target.closest('[data-action="restore-backup"]');
      if (button) restoreBackup(button.dataset.name);
    });

    document.addEventListener('keydown', (event) => {
      const target = event.target;
      const typing =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);
      if (event.key === '/' && !typing) {
        event.preventDefault();
        els.searchInput.focus();
        els.searchInput.select();
      } else if (event.key === 'Escape') {
        if (openModalId) closeModal(openModalId);
        els.dataMenu.classList.add('hidden');
        els.dataMenuBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  function handleResultClick(event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    const id = button.dataset.id;
    if (action === 'run-scan') runScan();
    else if (action === 'open-add') openAccountModal();
    else if (action === 'reset-filters') resetFilters();
    else if (action === 'edit-account') {
      const account = state.accounts.find((item) => item.id === id);
      if (account) openAccountModal(account);
    } else if (action === 'delete-account') deleteAccount(id);
    else if (action === 'reveal-password') revealPassword(id, button);
    else if (action === 'copy-password') copyPassword(id);
    else if (action === 'hide-password') resetPasswordCells(id);
    else if (action === 'copy-bookmark') copyBookmark(id);
    else if (action === 'delete-bookmark') deleteBookmark(id);
    else if (action === 'bookmark-to-account') {
      const bookmark = findBookmark(id);
      if (bookmark) {
        const title = (bookmark.title || hostOf(bookmark.url) || 'Bookmark').slice(0, 160);
        openAccountModal(null, { service: title, website: bookmark.url });
      }
    }
  }

  async function init() {
    bindEvents();
    try {
      await loadState();
    } catch (error) {
      toast(`Could not load data: ${error.message}`, 'error', 12000);
    }
  }

  init();
})();
