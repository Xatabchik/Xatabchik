function telegramPopupSupported() {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return false;
    try {
        if (typeof tg.isVersionAtLeast === 'function') {
            return !!tg.isVersionAtLeast('6.2');
        }
    } catch (e) {
        return false;
    }
    const parts = String(tg.version || '0').split('.');
    const major = parseInt(parts[0], 10) || 0;
    const minor = parseInt(parts[1], 10) || 0;
    return major > 6 || (major === 6 && minor >= 2);
}

function showLocalToast(message, type) {
    const container = document.getElementById('toast-container');
    if (!container || typeof document.createElement !== 'function') return;
    const toast = document.createElement('div');
    toast.className = `px-6 py-3 rounded-2xl text-sm font-bold shadow-2xl transition-all duration-300 translate-y-10 opacity-0 pointer-events-auto border border-white/10 ${type === 'error' ? 'bg-red-500/90 text-white' : 'bg-white text-black'}`;
    toast.textContent = message;
    container.appendChild(toast);
    const reveal = () => {
        if (toast.classList) toast.classList.remove('translate-y-10', 'opacity-0');
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(reveal);
    else reveal();
    setTimeout(() => {
        if (toast.classList) toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => { if (toast.remove) toast.remove(); }, 300);
    }, 3000);
}

function safeTelegramPopup(message, type) {
    const text = String(message == null ? '' : message);
    const fallback = () => { showLocalToast(text, type); };
    try {
        const tg = window.Telegram && window.Telegram.WebApp;
        if (!telegramPopupSupported() || !tg) {
            fallback();
            return;
        }
        let result;
        if (typeof tg.showPopup === 'function') {
            result = tg.showPopup({ message: text });
        } else if (typeof tg.showAlert === 'function') {
            result = tg.showAlert(text);
        } else {
            fallback();
            return;
        }
        if (result && typeof result.then === 'function') {
            result.then(undefined, fallback);
        }
    } catch (e) {
        fallback();
    }
}

function showNotification(message, type = 'info') {
    try {
        safeTelegramPopup(message, type);
    } catch (e) {
        try { showLocalToast(message, type); } catch (e2) { /* feedback UI не ломает действие */ }
    }
}
