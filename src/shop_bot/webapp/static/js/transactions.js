/* Mini App transactions — история операций на странице «Финансы».
 *
 * Classic deferred script (not type=module), loaded after store.js and
 * before app.js. Модалка полной истории + превью на вкладке + пагинация
 * data-tx-action. Тела функций — 1:1 из app.js; URL/payload API не менялись.
 */

let _txPage = 1;
async function loadTransactions(page) {
    _txPage = page || 1;
    const contentEl = document.getElementById('action-modal-content');
    if (!contentEl) return;

    try {
        const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || window.RENDERED_USER_ID;
        const res = await window.apiFetch('/api/user/transactions?page=' + _txPage + '&per_page=10');
        const data = await res.json();

        if (!data.ok) {
            contentEl.innerHTML = `<div class="text-center text-red-400 py-3 text-xs">${data.error || 'Ошибка'}</div>`;
            return;
        }

        const txs = data.transactions || [];
        if (!txs.length && _txPage === 1) {
            contentEl.innerHTML = '<div class="text-center text-gray-500 py-5 text-xs font-medium">История транзакций пуста</div>';
            return;
        }

        const methodIcons = { 'Balance': 'account_balance', 'ReferralBalance': 'diamond', 'Stars': 'star', 'Cryptobot': 'currency_bitcoin', 'CryptoBot': 'currency_bitcoin', 'Platega': 'credit_card', 'YooMoney': 'account_balance_wallet', 'YooKassa': 'account_balance_wallet', 'Heleket': 'currency_bitcoin', 'RollyPay': 'credit_card', 'TON Connect': 'currency_bitcoin', 'Ton': 'currency_bitcoin' };
        const escTx = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        let html = '<div class="flex flex-col gap-2">';
        txs.forEach(tx => {
            const icon = methodIcons[tx.payment_method] || 'receipt';
            const dateStr = tx.created_date ? tx.created_date.split(' ')[0] : '—';
            const amount = tx.amount_rub != null ? `${Number(tx.amount_rub).toFixed(0)} ₽` : '—';
            const st = String(tx.status || '').toLowerCase();
            const statusColor = (st === 'paid' || st === 'success' || st === 'completed' || st === 'succeeded')
                ? 'text-emerald-400'
                : (st === 'pending' ? 'text-amber-400' : (st === 'cancelled' || st === 'canceled' ? 'text-red-400' : 'text-gray-400'));
            const statusText = escTx(tx.status_label || tx.status || '—');
            const providerId = escTx(tx.provider_transaction_id || '');
            html += `
                <div class="flex items-center gap-3 p-2.5 bg-white/5 border border-white/5 rounded-xl">
                    <div class="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center shrink-0">
                        <span class="material-symbols-rounded text-primary text-sm">${icon}</span>
                    </div>
                    <div class="flex-1 overflow-hidden">
                        <div class="text-[10px] font-bold text-white truncate">${escTx(tx.action_label)}</div>
                        <div class="text-[9px] text-gray-500">${escTx(tx.payment_method)} • ${escTx(dateStr)}</div>
                        ${providerId ? `<div class="text-[9px] text-gray-500 truncate">ID: ${providerId}</div>` : ''}
                    </div>
                    <div class="text-right shrink-0">
                        <div class="text-xs font-black text-primary">${escTx(amount)}</div>
                        <div class="text-[9px] ${statusColor}">${statusText}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        // Pagination
        if (data.total > 10) {
            const totalPages = Math.ceil(data.total / 10);
            html += `<div class="flex items-center justify-between mt-2 px-1">
                <button type="button" data-tx-action="page-prev" ${_txPage <= 1 ? 'disabled' : ''}
                    class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                    <span class="material-symbols-rounded text-sm">chevron_left</span>
                </button>
                <span class="text-[10px] text-gray-500">${_txPage} / ${totalPages} (${data.total})</span>
                <button type="button" data-tx-action="page-next" ${!data.has_more ? 'disabled' : ''}
                    class="w-9 h-9 rounded-xl bg-white/5 border border-white/5 flex items-center justify-center text-gray-400 hover:bg-white/10 disabled:opacity-30">
                    <span class="material-symbols-rounded text-sm">chevron_right</span>
                </button>
            </div>`;
        }

        contentEl.innerHTML = html;
    } catch (e) {
        const contentEl2 = document.getElementById('action-modal-content');
        if (contentEl2) contentEl2.innerHTML = '<div class="text-center text-red-400 py-3 text-xs">Ошибка сети</div>';
    }
}

window._loadFinancePage = async function () {
    try {
        await refreshBalance({ silent: true });
    } catch (e) { /* silent */ }

    const prevEl = document.getElementById('finance-transactions-preview');
    if (!prevEl) return;
    try {
        const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id || window.RENDERED_USER_ID;
        const res = await window.apiFetch('/api/user/transactions?page=1&per_page=3');
        const data = await res.json();
        if (data.ok && data.transactions && data.transactions.length) {
            let html = '<div class="flex flex-col gap-2">';
            data.transactions.slice(0, 3).forEach(tx => {
                const dateStr = tx.created_date ? tx.created_date.split(' ')[0] : '—';
                const amount = tx.amount_rub != null ? Number(tx.amount_rub).toFixed(0) + ' ₽' : '—';
                const st = String(tx.status || '').toLowerCase();
                const statusColor = (st === 'paid' || st === 'success' || st === 'completed' || st === 'succeeded')
                    ? 'text-emerald-400' : (st === 'pending' ? 'text-amber-400' : 'text-gray-400');
                const esc = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const providerId = esc(tx.provider_transaction_id || '');
                html += '<div class="flex items-center gap-3 p-2.5 bg-white/5 border border-white/5 rounded-xl">' +
                    '<div class="w-7 h-7 bg-primary/10 rounded-lg flex items-center justify-center shrink-0"><span class="material-symbols-rounded text-primary text-sm">receipt</span></div>' +
                    '<div class="flex-1 overflow-hidden"><div class="text-[10px] font-bold text-white truncate">' + esc(tx.action_label) + '</div>' +
                    '<div class="text-[9px] text-gray-500">' + esc(dateStr) + (providerId ? ' • ID: ' + providerId : '') + '</div></div>' +
                    '<div class="text-right shrink-0"><div class="text-xs font-black text-primary">' + esc(amount) + '</div>' +
                    '<div class="text-[9px] ' + statusColor + '">' + esc(tx.status_label || tx.status || '') + '</div></div></div>';
            });
            html += '</div>';
            prevEl.innerHTML = html;
        } else {
            prevEl.innerHTML = '<div class="text-center text-[11px] text-gray-500 py-3">Нет транзакций</div>';
        }
    } catch (e) {
        prevEl.innerHTML = '<div class="text-center text-[11px] text-gray-500 py-3">Ошибка загрузки</div>';
    }
};

document.addEventListener('click', (event) => {
    const txBtn = event.target.closest('[data-tx-action]');
    if (txBtn) {
        if (txBtn.disabled) return;
        const txAction = txBtn.getAttribute('data-tx-action');
        if (txAction === 'page-prev') loadTransactions(_txPage - 1);
        else if (txAction === 'page-next') loadTransactions(_txPage + 1);
        return;
    }
});

document.getElementById('finance-tx-all-btn')?.addEventListener('click', () => openActionModal('transactions', null));
