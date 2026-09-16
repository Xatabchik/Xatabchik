// --- Telegram WebApp version-safe helpers ---
// setHeaderColor / setBackgroundColor / HapticFeedback: Bot API 6.1+.
// isVersionAtLeast itself is 6.1+; on 6.0 the missing method means skip.
function telegramVersionAtLeast(minVersion) {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return false;
    try {
        if (typeof tg.isVersionAtLeast === 'function') {
            return !!tg.isVersionAtLeast(minVersion);
        }
    } catch (e) { }
    return false;
}

function safeTelegramAppearance(options) {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;
    const opts = options || {};
    try {
        if (!telegramVersionAtLeast('6.1')) return;
        if (opts.header && typeof tg.setHeaderColor === 'function') {
            tg.setHeaderColor(opts.header);
        }
        if (opts.background && typeof tg.setBackgroundColor === 'function') {
            tg.setBackgroundColor(opts.background);
        }
    } catch (error) {
        console.warn('Telegram appearance API unavailable');
    }
}

function safeTelegramHaptic(kind) {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;
    try {
        if (!telegramVersionAtLeast('6.1')) return;
        if (tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === 'function') {
            tg.HapticFeedback.notificationOccurred(kind);
        }
    } catch (e) { }
}
// --- end Telegram WebApp version-safe helpers ---
