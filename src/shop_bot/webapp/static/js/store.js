/* Mini App Store — Phase 1 (balance).
 *
 * Classic deferred script (not type=module), loaded before app.js.
 * Object + subscribers, без reducers / middleware / внешних библиотек.
 * Последующие PR расширяют state, не меняя этот контракт.
 */

const store = {
    state: { balance: null },
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
