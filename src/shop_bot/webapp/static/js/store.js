/* Mini App Store — Phase 2 (balance + keyNames).
 *
 * Classic deferred script (not type=module), loaded before app.js.
 * Object + subscribers, без reducers / middleware / внешних библиотек.
 * Последующие PR расширяют state, не меняя этот контракт.
 */

const store = {
    state: { balance: null, keyNames: {} },
    listeners: new Set(),
    subscribe(fn) {
        this.listeners.add(fn);
        return () => this.listeners.delete(fn);
    },
    setState(patch) {
        this.state = Object.assign({}, this.state, patch);
        this.listeners.forEach((fn) => fn(this.state));
    },
};

const BALANCE_ELEMENT_IDS = [
    'finance-balance',
    'home-balance',
    'topup-success-balance',
];

function formatBalanceRub(value) {
    return Number(value).toFixed(2) + ' ₽';
}

function applyBalanceToDom(state) {
    if (state.balance == null) return;
    const numeric = Number(state.balance);
    if (!Number.isFinite(numeric)) return;
    const text = formatBalanceRub(numeric);
    for (let i = 0; i < BALANCE_ELEMENT_IDS.length; i++) {
        const el = document.getElementById(BALANCE_ELEMENT_IDS[i]);
        if (el) el.textContent = text;
    }
    const extras = document.querySelectorAll('[data-balance-display]');
    for (let j = 0; j < extras.length; j++) {
        extras[j].textContent = text;
    }
}

store.subscribe(applyBalanceToDom);

function _numericBalance(value) {
    if (value == null) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

function _balanceFromUserStatus(payload) {
    if (!payload || payload.ok === false) return null;
    return _numericBalance(payload.balance);
}

async function refreshBalance(options) {
    const opts = options || {};
    const fallback = _numericBalance(opts.fallbackBalance);
    let next = null;
    try {
        const fetcher = (typeof apiFetch === 'function')
            ? apiFetch
            : (window.apiFetch || fetch);
        const resp = await fetcher('/api/user-status');
        const data = await resp.json();
        next = _balanceFromUserStatus(data);
    } catch (e) {
        next = null;
    }
    if (next == null) next = fallback;
    if (next == null) {
        if (!opts.silent && typeof showNotification === 'function') {
            showNotification('Не удалось обновить баланс', 'error');
        }
        return false;
    }
    store.setState({ balance: next });
    return true;
}

function applyKeyNamesToDom(state) {
    const names = state && state.keyNames;
    if (!names) return;
    const ids = Object.keys(names);
    for (let i = 0; i < ids.length; i++) {
        const keyId = ids[i];
        const name = names[keyId];
        if (name == null || String(name) === '') continue;
        _applyOneKeyNameToDom(keyId, String(name));
    }
}

function _applyOneKeyNameToDom(keyId, name) {
    const idStr = String(keyId);
    const cards = document.querySelectorAll('[data-key-id="' + idStr + '"]');
    for (let i = 0; i < cards.length; i++) {
        const card = cards[i];
        card.setAttribute('data-key-name', name);
        const title = card.querySelector('.key-toggle .text-xs.font-bold');
        if (title) title.textContent = name;
    }
    const options = document.querySelectorAll('.dropdown-option[data-key="#' + idStr + '"]');
    for (let j = 0; j < options.length; j++) {
        const opt = options[j];
        opt.setAttribute('data-name', name);
        const optTitle = opt.querySelector('.text-xs.font-bold');
        if (optTitle) optTitle.textContent = name;
    }
    const selectedId = String((typeof window !== 'undefined' && window.selectedKeyId) || '');
    if (selectedId !== idStr) return;
    const displayEl = document.getElementById('display-selected-key');
    if (!displayEl) return;
    const selectedOpt = document.querySelector('.dropdown-option[data-key="#' + idStr + '"]');
    const date = selectedOpt ? (selectedOpt.getAttribute('data-date') || '') : '';
    if (date) {
        displayEl.textContent = name + ' • До ' + date;
        return;
    }
    const txt = displayEl.textContent || '';
    const bullet = txt.indexOf(' • ');
    displayEl.textContent = bullet >= 0 ? (name + txt.slice(bullet)) : name;
}

store.subscribe(applyKeyNamesToDom);

function _nameFromUserStatus(payload, keyId) {
    if (!payload || payload.ok === false || !Array.isArray(payload.keys)) return null;
    const want = String(keyId);
    for (let i = 0; i < payload.keys.length; i++) {
        const key = payload.keys[i];
        if (!key || String(key.key_id) !== want) continue;
        if (key.name == null) return null;
        const name = String(key.name).trim();
        return name || null;
    }
    return null;
}

function _fallbackKeyDisplayName(keyId, fallbackName) {
    if (fallbackName === undefined || fallbackName === null) return null;
    const trimmed = String(fallbackName).trim();
    if (trimmed) return trimmed;
    return 'Ключ #' + String(keyId);
}

async function refreshKeyName(keyId, options) {
    const opts = options || {};
    const fallback = _fallbackKeyDisplayName(keyId, opts.fallbackName);
    let next = null;
    try {
        const fetcher = (typeof apiFetch === 'function')
            ? apiFetch
            : (window.apiFetch || fetch);
        const resp = await fetcher('/api/user-status');
        const data = await resp.json();
        next = _nameFromUserStatus(data, keyId);
    } catch (e) {
        next = null;
    }
    if (next == null) next = fallback;
    if (next == null) {
        if (!opts.silent && typeof showNotification === 'function') {
            showNotification('Не удалось обновить название ключа', 'error');
        }
        return false;
    }
    const nextNames = Object.assign({}, store.state.keyNames || {});
    nextNames[String(keyId)] = next;
    store.setState({ keyNames: nextNames });
    return true;
}
