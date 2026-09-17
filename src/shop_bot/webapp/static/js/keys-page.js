/* Mini App keys page — поиск, табы «Личные»/«Подарки», пагинация, подарки.
 *
 * Classic deferred script (not type=module), loaded after transactions.js
 * and before app.js. Accordion карточек (.key-toggle) и data-*-page
 * обработчики живут здесь целиком. URL/payload API не менялись.
 */

// Раскрытие/сворачивание карточки ключа. Раньше высота разворота была
// зафиксирована в CSS (max-height: 350px), из-за чего у карточек с большим
// содержимым (например, у подарков — с обеими ссылками активации и кнопками)
// часть контента обрезалась и была не видна. Теперь высота считается динамически
// по фактическому содержимому карточки.
function toggleKeyCard(button) {
    const content = button.nextElementSibling;
    const icon = button.querySelector('.rotate-icon');
    if (!content) return;
    const isExpanded = content.classList.contains('expanded');
    if (isExpanded) {
        content.classList.remove('expanded');
        content.style.maxHeight = '0px';
    } else {
        content.classList.add('expanded');
        content.style.maxHeight = '';
        const height = content.scrollHeight;
        content.style.maxHeight = (height || 2000) + 'px';
    }
    if (icon) icon.classList.toggle('expanded');
}
// ===== Keys Page: Tabs (Личные / Подарочные) =====
let _activeKeysTab = 'personal';
function switchKeysTab(tab) {
    _activeKeysTab = tab;
    const personalBtn = document.getElementById('keys-tab-btn-personal');
    const giftsBtn = document.getElementById('keys-tab-btn-gifts');
    const personalPanel = document.getElementById('keys-tab-personal');
    const giftsPanel = document.getElementById('keys-tab-gifts');
    const isPersonal = tab === 'personal';
    if (personalBtn) {
        personalBtn.classList.toggle('bg-white/10', isPersonal);
        personalBtn.classList.toggle('text-white', isPersonal);
        personalBtn.classList.toggle('text-gray-400', !isPersonal);
    }
    if (giftsBtn) {
        giftsBtn.classList.toggle('bg-white/10', !isPersonal);
        giftsBtn.classList.toggle('text-white', !isPersonal);
        giftsBtn.classList.toggle('text-gray-400', isPersonal);
    }
    if (personalPanel) personalPanel.classList.toggle('hidden', !isPersonal);
    if (giftsPanel) giftsPanel.classList.toggle('hidden', isPersonal);
}

// ===== Keys Page: Pagination for the personal keys list =====
// The personal keys list is rendered server-side (full HTML) into
// #profile-keys-list-container, so pagination here just shows/hides
// the already-rendered cards client-side (no extra requests, no
// re-binding of existing key-toggle listeners needed).
const PROFILE_KEYS_PAGE_SIZE = 5;
let _profileKeysPage = 0;
function initProfileKeysPagination() {
    const container = document.getElementById('profile-keys-list-container');
    if (!container) return;
    window._profileKeysCards = Array.from(container.children).filter(el => el.querySelector && el.querySelector('.key-toggle'));
    _profileKeysPage = 0;
    renderProfileKeysPage();
}
function renderProfileKeysPage() {
    const cards = window._profileKeysCards || [];
    const paginationEl = document.getElementById('profile-keys-pagination');
    if (!paginationEl) return;
    if (!cards.length) { paginationEl.classList.add('hidden'); paginationEl.innerHTML = ''; return; }

    const totalPages = Math.ceil(cards.length / PROFILE_KEYS_PAGE_SIZE);
    const start = _profileKeysPage * PROFILE_KEYS_PAGE_SIZE;
    cards.forEach((el, i) => { el.style.display = (i >= start && i < start + PROFILE_KEYS_PAGE_SIZE) ? '' : 'none'; });

    if (totalPages > 1) {
        paginationEl.classList.remove('hidden');
        paginationEl.innerHTML = `
            <div class="flex items-center justify-between px-1">
                <button type="button" data-profile-keys-page="-1" ${_profileKeysPage === 0 ? 'disabled' : ''}
                    class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                    <span class="material-symbols-rounded text-sm">chevron_left</span>
                </button>
                <span class="text-[10px] text-gray-500">${_profileKeysPage + 1} / ${totalPages} (${cards.length})</span>
                <button type="button" data-profile-keys-page="1" ${_profileKeysPage >= totalPages - 1 ? 'disabled' : ''}
                    class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                    <span class="material-symbols-rounded text-sm">chevron_right</span>
                </button>
            </div>`;
    } else {
        paginationEl.classList.add('hidden');
        paginationEl.innerHTML = '';
    }
}
function changeProfileKeysPage(delta) {
    const cards = window._profileKeysCards || [];
    const totalPages = Math.ceil(cards.length / PROFILE_KEYS_PAGE_SIZE);
    _profileKeysPage = Math.min(Math.max(0, _profileKeysPage + delta), totalPages - 1);
    renderProfileKeysPage();
}

// ===== Keys Page: Live inline search (replaces the old search modal) =====
let _keysSearchDebounceTimer = null;
function onKeysSearchInput() {
    const input = document.getElementById('keys-search-input');
    const clearBtn = document.getElementById('keys-search-clear');
    const q = (input?.value || '').trim();
    if (clearBtn) clearBtn.classList.toggle('hidden', !q);
    clearTimeout(_keysSearchDebounceTimer);
    if (!q) { exitKeysSearchMode(); return; }
    _keysSearchDebounceTimer = setTimeout(() => performKeysSearch(q), 350);
}
function clearKeysSearch() {
    const input = document.getElementById('keys-search-input');
    if (input) input.value = '';
    const clearBtn = document.getElementById('keys-search-clear');
    if (clearBtn) clearBtn.classList.add('hidden');
    clearTimeout(_keysSearchDebounceTimer);
    exitKeysSearchMode();
}
function exitKeysSearchMode() {
    const wrap = document.getElementById('keys-search-results-wrap');
    const tabsEl = document.getElementById('keys-tabs');
    if (wrap) wrap.classList.add('hidden');
    if (tabsEl) tabsEl.classList.remove('hidden');
    switchKeysTab(_activeKeysTab);
}
async function performKeysSearch(q) {
    if (q.length < 2) return;

    const wrap = document.getElementById('keys-search-results-wrap');
    const resultsEl = document.getElementById('keys-search-results');
    const tabsEl = document.getElementById('keys-tabs');
    const personalPanel = document.getElementById('keys-tab-personal');
    const giftsPanel = document.getElementById('keys-tab-gifts');
    if (tabsEl) tabsEl.classList.add('hidden');
    if (personalPanel) personalPanel.classList.add('hidden');
    if (giftsPanel) giftsPanel.classList.add('hidden');
    if (wrap) wrap.classList.remove('hidden');
    if (resultsEl) resultsEl.innerHTML = '<div class="flex justify-center py-3"><span class="material-symbols-rounded animate-spin text-primary">progress_activity</span></div>';

    try {
        const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || window.RENDERED_USER_ID;
        const res = await fetch('/api/keys/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, query: q, token: window.getAuthToken() || '' })
        });
        const data = await res.json();
        if (!resultsEl) return;

        if (!data.ok) { resultsEl.innerHTML = `<div class="text-center text-red-400 text-xs py-2">${data.error || 'Ошибка'}</div>`; return; }

        if (!data.total || !data.html) {
            resultsEl.innerHTML = '<div class="text-center text-gray-500 text-xs py-3">Ничего не найдено</div>';
            return;
        }

        // Server reuses the same key-card renderer as the main "Мои ключи" list,
        // so results come with full buttons/actions already wired up.
        resultsEl.innerHTML = `<div class="mt-1">${data.html}</div>`;
        if (typeof applyKeyCommentsToDom === 'function' && typeof store !== 'undefined') {
            applyKeyCommentsToDom(store.state);
        }
    } catch (e) {
        if (resultsEl) resultsEl.innerHTML = '<div class="text-center text-red-400 text-xs py-2">Ошибка сети</div>';
    }
}

// Keys page search/tabs: bound here instead of inline oninput/onclick in app.html.
document.getElementById('keys-search-input')?.addEventListener('input', onKeysSearchInput);
document.getElementById('keys-search-clear')?.addEventListener('click', clearKeysSearch);
document.getElementById('keys-tab-btn-personal')?.addEventListener('click', () => switchKeysTab('personal'));
document.getElementById('keys-tab-btn-gifts')?.addEventListener('click', () => switchKeysTab('gifts'));
// ── User gifts ───────────────────────────────────────────────────
const GIFTS_PAGE_SIZE = 5;
window._giftsState = { gifts: [], page: 0 };

function _giftLinkRowHtml(label, link, shareText) {
    if (!link) return '';
    const text = encodeURIComponent(shareText || '🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать');
    return `
        <div class="flex flex-col gap-1 min-w-0">
            <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider px-0.5">${label}</div>
            <div class="flex items-center gap-2 min-w-0">
                <div class="flex-1 min-w-0 bg-black/30 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 font-mono truncate">${escapeHtmlAttr(link)}</div>
                <button type="button" data-copy-action="clipboard" class="shrink-0 bg-primary/20 text-primary rounded-lg p-1.5 hover:bg-primary/30 active:scale-95 transition-all">
                    <span class="material-symbols-rounded text-sm">content_copy</span>
                </button>
                <a href="https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}" target="_blank"
                   class="shrink-0 bg-[#0088cc]/20 text-[#00aaff] rounded-lg p-1.5 hover:bg-[#0088cc]/30 active:scale-95 transition-all">
                    <span class="material-symbols-rounded text-sm">send</span>
                </a>
            </div>
        </div>`;
}

function _giftCardHtml(g) {
    if (g.card_html) return g.card_html;
    // Fallback (e.g. underlying key not found): simplified card, but with the same
    // full set of fields/buttons as the server-rendered card (both activation links,
    // copy/share, and the "Активировать себе" button kept visually separated below).
    const webappLink = g.webapp_link || g.link || '';
    const telegramLink = g.telegram_link || '';
    const shareText = window._giftShareText || '';
    return `
        <div class="glass-card border border-white/10 rounded-xl p-3 flex flex-col gap-2 mb-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-rounded text-amber-400 text-base">card_giftcard</span>
                    <div>
                        <div class="text-[10px] font-bold text-white">${g.host_name || 'Подарок'}</div>
                        <div class="text-[9px] text-gray-500">${g.created_at ? g.created_at.slice(0,10) : ''}</div>
                    </div>
                </div>
                <span class="text-[9px] text-amber-400 font-bold uppercase">Не активирован</span>
            </div>
            ${_giftLinkRowHtml('Ссылка активации (в приложении)', webappLink, shareText)}
            ${_giftLinkRowHtml('Ссылка активации (в Telegram)', telegramLink, shareText)}
            <div class="mt-3 pt-2 border-t border-dashed border-white/10">
                <button type="button" data-gift-action="activate" data-gift-code="${escapeHtmlAttr(g.gift_code)}" class="w-full bg-amber-500 hover:bg-amber-600 text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                    <span class="material-symbols-rounded text-sm">redeem</span>
                    <span>Активировать себе</span>
                </button>
            </div>
        </div>`;
}

function renderGiftsPage() {
    const s = window._giftsState;
    const content = document.getElementById('gifts-content');
    const paginationEl = document.getElementById('gifts-pagination');
    if (!content) return;

    const totalPages = Math.ceil(s.gifts.length / GIFTS_PAGE_SIZE);
    const start = s.page * GIFTS_PAGE_SIZE;
    const pageGifts = s.gifts.slice(start, start + GIFTS_PAGE_SIZE);

    content.innerHTML = pageGifts.map(_giftCardHtml).join('');

    if (paginationEl) {
        if (totalPages > 1) {
            paginationEl.classList.remove('hidden');
            paginationEl.innerHTML = `
                <div class="flex items-center justify-between px-1">
                    <button type="button" data-gifts-page="-1" ${s.page === 0 ? 'disabled' : ''}
                    class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                    <span class="material-symbols-rounded text-sm">chevron_left</span>
                </button>
                    <span class="text-[10px] text-gray-500">${s.page + 1} / ${totalPages} (${s.gifts.length})</span>
                    <button type="button" data-gifts-page="1" ${s.page >= totalPages - 1 ? 'disabled' : ''}
                        class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                        <span class="material-symbols-rounded text-sm">chevron_right</span>
                    </button>
                </div>`;
        } else {
            paginationEl.classList.add('hidden');
            paginationEl.innerHTML = '';
        }
    }
}
function changeGiftsPage(delta) {
    const s = window._giftsState;
    const totalPages = Math.ceil(s.gifts.length / GIFTS_PAGE_SIZE);
    s.page = Math.min(Math.max(0, s.page + delta), totalPages - 1);
    renderGiftsPage();
}

async function loadUserGifts() {
    const token = window.getAuthToken();
    const userId = window._currentUserId;
    if (!token && !userId) return;
    try {
        const resp = await fetch('/api/user/gifts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, user_id: userId })
        });
        const d = await resp.json();
        const loading = document.getElementById('gifts-loading');
        const content = document.getElementById('gifts-content');
        const paginationEl = document.getElementById('gifts-pagination');
        if (loading) loading.style.display = 'none';
        if (!d.ok || !content) return;
        content.classList.remove('hidden');
        window._giftShareText = d.share_text || '';
        if (typeof store !== 'undefined' && store.setState) {
            store.setState({ gifts: d.gifts || [] });
            return;
        }
        if (!d.gifts || !d.gifts.length) {
            content.innerHTML = '<div class="text-center text-[11px] text-gray-500 py-3">Нет неактивированных подарков.<br>Купить подарок можно на странице покупки.</div>';
            if (paginationEl) { paginationEl.classList.add('hidden'); paginationEl.innerHTML = ''; }
            return;
        }
        window._giftsState = { gifts: d.gifts, page: 0 };
        renderGiftsPage();
    } catch (e) {
        console.error('Gifts error:', e);
    }
}

async function activateOwnGift(giftCode, btnEl) {
    if (!giftCode) return;
    const userId = window._currentUserId || (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) || window.RENDERED_USER_ID;
    if (!userId) { showNotification('Требуется авторизация', 'error'); return; }
    if (btnEl) { btnEl.disabled = true; btnEl.innerHTML = '<span class="material-symbols-rounded animate-spin text-sm">progress_activity</span>'; }
    try {
        const resp = await fetch('/api/gift/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, gift_code: giftCode, token: window.getAuthToken() || '' })
        });
        const d = await resp.json();
        showNotification(d.ok ? (d.message || 'Подарок активирован!') : (d.error || 'Ошибка активации'), d.ok ? 'success' : 'error');
        if (d.ok) {
            if (typeof refreshAfterGiftActivation === 'function') {
                await refreshAfterGiftActivation({ giftCode: giftCode });
            }
        }
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    } finally {
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerHTML = '<span class="material-symbols-rounded text-sm">redeem</span><span>Активировать себе</span>';
        }
    }
}

window._loadKeysPage = async function () {
    initProfileKeysPagination();
    // Only reset the tab view if the user isn't currently in the middle
    // of a live search (search mode already hides the tab panels itself).
    const searchInput = document.getElementById('keys-search-input');
    if (!searchInput || !searchInput.value.trim()) {
        switchKeysTab(_activeKeysTab);
    }
    const giftsContent = document.getElementById('gifts-content');
    const giftsLoading = document.getElementById('gifts-loading');
    if (giftsContent && giftsLoading && giftsContent.classList.contains('hidden') && giftsLoading.style.display !== 'none') {
        loadUserGifts();
    }
};
// ── Auto-activate gift from URL param ────────────────────────────
(function checkGiftParam() {
    const url = new URL(window.location.href);
    const giftCode = url.searchParams.get('activate_gift');
    if (!giftCode) return;
    url.searchParams.delete('activate_gift');
    window.history.replaceState(null, '', url.toString() || window.location.pathname);
    window.addEventListener('appReady', async () => {
        const userId = window._currentUserId;
        if (!userId) return;
        try {
            const r = await fetch('/api/gift/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, gift_code: giftCode, token: window.getAuthToken() || '' })
            });
            const d = await r.json();
            showNotification(d.ok ? (d.message || 'Подарок активирован!') : (d.error || 'Ошибка активации'), d.ok ? 'success' : 'error');
            if (d.ok && typeof refreshAfterGiftActivation === 'function') {
                await refreshAfterGiftActivation({ giftCode: giftCode });
            }
        } catch (e) { /* silent */ }
    });
})();

document.addEventListener('click', (event) => {
    const profileKeysBtn = event.target.closest('[data-profile-keys-page]');
    if (profileKeysBtn) {
        if (profileKeysBtn.disabled) return;
        const delta = parseInt(profileKeysBtn.getAttribute('data-profile-keys-page') || '', 10);
        if (delta) changeProfileKeysPage(delta);
        return;
    }
    const giftsPageBtn = event.target.closest('[data-gifts-page]');
    if (giftsPageBtn) {
        if (giftsPageBtn.disabled) return;
        const delta = parseInt(giftsPageBtn.getAttribute('data-gifts-page') || '', 10);
        if (delta) changeGiftsPage(delta);
        return;
    }
    const giftAct = event.target.closest('[data-gift-action="activate"]');
    if (giftAct) {
        if (giftAct.disabled) return;
        activateOwnGift(giftAct.getAttribute('data-gift-code') || '', giftAct);
        return;
    }
    const toggle = event.target.closest('.key-toggle');
    if (toggle) {
        toggleKeyCard(toggle);
        return;
    }
});
