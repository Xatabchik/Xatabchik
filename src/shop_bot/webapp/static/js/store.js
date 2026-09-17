/* Mini App Store — Phase 3 (balance + keyNames + gifts/keysListHtml).
 *
 * Classic deferred script (not type=module), loaded before app.js.
 * Object + subscribers, без reducers / middleware / внешних библиотек.
 * Последующие PR расширяют state, не меняя этот контракт.
 */

const store = {
    state: { balance: null, keyNames: {}, gifts: null, keysListHtml: null },
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

const GIFTS_EMPTY_HTML = '<div class="text-center text-[11px] text-gray-500 py-3">Нет неактивированных подарков.<br>Купить подарок можно на странице покупки.</div>';

function _giftsWithoutCode(list, giftCode) {
    if (!Array.isArray(list)) return null;
    const want = String(giftCode || '');
    if (!want) return list.slice();
    return list.filter((g) => g && String(g.gift_code) !== want);
}

function _keyNamesFromUserStatus(payload) {
    if (!payload || payload.ok === false || !Array.isArray(payload.keys)) return null;
    const names = {};
    for (let i = 0; i < payload.keys.length; i++) {
        const key = payload.keys[i];
        if (!key || key.key_id == null || key.name == null) continue;
        const name = String(key.name).trim();
        if (name) names[String(key.key_id)] = name;
    }
    return names;
}

function _keysListHtmlFromPage(htmlStr) {
    if (!htmlStr || typeof DOMParser === 'undefined') return null;
    try {
        const doc = new DOMParser().parseFromString(String(htmlStr), 'text/html');
        const el = doc.getElementById('profile-keys-list-container');
        return el ? el.innerHTML : null;
    } catch (e) {
        return null;
    }
}

function _stripGiftActionsFrom(container) {
    if (!container || !container.querySelectorAll) return;
    const btns = container.querySelectorAll('[data-gift-action]');
    for (let i = 0; i < btns.length; i++) {
        const btn = btns[i];
        const block = btn.closest('.mt-3') || btn.parentElement;
        if (block && block.parentElement) block.parentElement.removeChild(block);
    }
}

function _fallbackKeysHtmlFromGiftCard(giftCode) {
    const container = document.getElementById('profile-keys-list-container');
    if (!container) return null;
    const list = (store.state && Array.isArray(store.state.gifts) && store.state.gifts)
        || (typeof window !== 'undefined' && window._giftsState && window._giftsState.gifts)
        || [];
    const want = String(giftCode || '');
    let gift = null;
    for (let i = 0; i < list.length; i++) {
        if (list[i] && String(list[i].gift_code) === want) { gift = list[i]; break; }
    }
    if (!gift || !gift.card_html) return null;
    const current = container.innerHTML || '';
    if (current.indexOf('data-key-id') < 0 && current.indexOf('Нет активных ключей') >= 0) {
        return gift.card_html;
    }
    return gift.card_html + current;
}

let _appliedGiftsRef = undefined;
let _appliedKeysListHtml = undefined;

function applyGiftsAndKeysToDom(state) {
    if (Array.isArray(state.gifts) && state.gifts !== _appliedGiftsRef) {
        _appliedGiftsRef = state.gifts;
        const prevPage = (typeof window !== 'undefined' && window._giftsState && window._giftsState.page) || 0;
        if (typeof window !== 'undefined') {
            window._giftsState = { gifts: state.gifts, page: prevPage };
        }
        const loading = document.getElementById('gifts-loading');
        const content = document.getElementById('gifts-content');
        if (loading) loading.style.display = 'none';
        if (content) {
            content.classList.remove('hidden');
            if (!state.gifts.length) {
                content.innerHTML = GIFTS_EMPTY_HTML;
                const paginationEl = document.getElementById('gifts-pagination');
                if (paginationEl) {
                    paginationEl.classList.add('hidden');
                    paginationEl.innerHTML = '';
                }
            } else if (typeof renderGiftsPage === 'function') {
                const pageSize = (typeof GIFTS_PAGE_SIZE === 'number') ? GIFTS_PAGE_SIZE : 5;
                const totalPages = Math.max(1, Math.ceil(state.gifts.length / pageSize));
                if (typeof window !== 'undefined') {
                    window._giftsState.page = Math.min(prevPage, totalPages - 1);
                }
                renderGiftsPage();
            }
        }
    }
    if (state.keysListHtml != null && state.keysListHtml !== _appliedKeysListHtml) {
        _appliedKeysListHtml = state.keysListHtml;
        const el = document.getElementById('profile-keys-list-container');
        if (el) {
            el.innerHTML = state.keysListHtml;
            _stripGiftActionsFrom(el);
            if (typeof initProfileKeysPagination === 'function') initProfileKeysPagination();
        }
        applyKeyNamesToDom(state);
    }
}

store.subscribe(applyGiftsAndKeysToDom);

async function refreshAfterGiftActivation(options) {
    const opts = options || {};
    const giftCode = opts.giftCode;
    const fetcher = (typeof apiFetch === 'function')
        ? apiFetch
        : (window.apiFetch || fetch);
    let gifts = null;
    let names = null;
    let keysHtml = null;
    try {
        const token = (typeof window !== 'undefined' && window.getAuthToken)
            ? window.getAuthToken()
            : '';
        const userId = (typeof window !== 'undefined' && window._currentUserId)
            || (typeof RENDERED_USER_ID !== 'undefined' ? RENDERED_USER_ID : null);
        const giftsReq = fetcher('/api/user/gifts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: token || '', user_id: userId }),
        });
        const statusReq = fetcher('/api/user-status');
        const pageReq = fetcher('/');
        const results = await Promise.all([giftsReq, statusReq, pageReq]);
        try {
            const giftsData = await results[0].json();
            if (giftsData && giftsData.ok && Array.isArray(giftsData.gifts)) {
                gifts = giftsData.gifts;
                if (typeof window !== 'undefined' && giftsData.share_text) {
                    window._giftShareText = giftsData.share_text;
                }
            }
        } catch (e) { gifts = null; }
        try {
            const statusData = await results[1].json();
            names = _keyNamesFromUserStatus(statusData);
        } catch (e) { names = null; }
        try {
            const pageHtml = await results[2].text();
            keysHtml = _keysListHtmlFromPage(pageHtml);
        } catch (e) { keysHtml = null; }
    } catch (e) {
        gifts = null;
        names = null;
        keysHtml = null;
    }
    if (gifts == null && giftCode) {
        const current = (store.state && store.state.gifts)
            || (typeof window !== 'undefined' && window._giftsState && window._giftsState.gifts);
        const filtered = _giftsWithoutCode(current, giftCode);
        if (filtered) gifts = filtered;
    }
    if (keysHtml == null && giftCode) {
        keysHtml = _fallbackKeysHtmlFromGiftCard(giftCode);
    }
    if (gifts == null && names == null && keysHtml == null) {
        if (!opts.silent && typeof showNotification === 'function') {
            showNotification('Не удалось обновить список ключей', 'error');
        }
        return false;
    }
    const patch = {};
    if (gifts != null) patch.gifts = gifts;
    if (names) {
        patch.keyNames = Object.assign({}, store.state.keyNames || {}, names);
    }
    if (keysHtml != null) patch.keysListHtml = keysHtml;
    store.setState(patch);
    return true;
}
