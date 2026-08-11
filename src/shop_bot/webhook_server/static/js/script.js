document.addEventListener('DOMContentLoaded', function () {

    // Disable all background auto-updates by default to avoid UI "jumping".
    // You can re-enable on a specific page by setting `window.disableAutoUpdate = false`
    // BEFORE this script runs.
    if (typeof window.disableAutoUpdate === 'undefined') {
        window.disableAutoUpdate = true;
    }

    function getCsrfToken(){
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    window.showToast = function(category, message, delay){
        try{
            const cont = document.getElementById('toast-container');
            if (!cont) return;
            const el = document.createElement('div');
            const cat = (category === 'danger' ? 'danger' : (category === 'success' ? 'success' : (category === 'warning' ? 'warning' : 'secondary')));
            el.className = 'toast fade align-items-center text-bg-' + cat;
            el.setAttribute('role','alert'); el.setAttribute('aria-live','assertive'); el.setAttribute('aria-atomic','true');
            el.innerHTML = '<div class="d-flex"><div class="toast-body">'+ (message||'') +'</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>';
            cont.appendChild(el);
            new bootstrap.Toast(el, { delay: Math.max(2000, delay||4000), autohide: true }).show();
        }catch(_){ }
    }

    // Bootstrap can leave orphaned .modal-backdrop nodes (and body.modal-open)
    // when nested modals are used or when `new bootstrap.Modal(el).show()` is
    // called on an already-open modal. Prefer getOrCreateInstance via helpers.
    window.cleanupModalBackdrops = function(){
        try {
            const openModals = document.querySelectorAll('.modal.show');
            const backdrops = document.querySelectorAll('.modal-backdrop');
            if (openModals.length === 0) {
                backdrops.forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('overflow');
                document.body.style.removeProperty('padding-right');
                return;
            }
            const excess = backdrops.length - openModals.length;
            if (excess > 0) {
                Array.from(backdrops).slice(0, excess).forEach(el => el.remove());
            }
        } catch(_){ }
    };

    window.getModal = function(el, options){
        if (!el || !window.bootstrap || !bootstrap.Modal) return null;
        try {
            if (typeof bootstrap.Modal.getOrCreateInstance === 'function') {
                return bootstrap.Modal.getOrCreateInstance(el, options || {});
            }
            return bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el, options || {});
        } catch(_){
            try { return new bootstrap.Modal(el, options || {}); } catch(__){ return null; }
        }
    };

    window.showModal = function(el, options){
        const modal = window.getModal(el, options);
        if (!modal) return null;
        try {
            if (!el.classList.contains('show')) modal.show();
        } catch(_){ }
        return modal;
    };

    window.hideModal = function(el){
        try {
            const modal = (el && window.bootstrap && bootstrap.Modal)
                ? (bootstrap.Modal.getInstance(el) || null)
                : null;
            if (modal) modal.hide();
            else window.cleanupModalBackdrops();
        } catch(_){
            try { window.cleanupModalBackdrops(); } catch(__){}
        }
    };

    document.addEventListener('hidden.bs.modal', function(){
        // Let Bootstrap finish its own teardown, then remove leftovers.
        setTimeout(function(){ try { window.cleanupModalBackdrops(); } catch(_){ } }, 0);
    });

    // Safety net: clear stuck backdrops if no modal is visible.
    document.addEventListener('click', function(e){
        try {
            if (!document.body.classList.contains('modal-open')) return;
            if (document.querySelector('.modal.show')) return;
            // Clicking through a leftover backdrop should clear it.
            if (e.target && e.target.classList && e.target.classList.contains('modal-backdrop')) {
                window.cleanupModalBackdrops();
            }
        } catch(_){ }
    }, true);

    function isFullDocument(html){
        if (!html) return false;
        const s = String(html).trim().slice(0, 512).toLowerCase();
        if (s.startsWith('<!doctype') || s.startsWith('<html')) return true;

        if (s.includes('<head') && s.includes('<title') && s.includes('</html>')) return true;
        return false;
    }

    window.refreshContainerById = async function(id){
        const node = document.getElementById(id);
        if (!node) return;
        const url = node.getAttribute('data-fetch-url');
        if (!url) return;
        try {
            const resp = await fetch(url, { headers: { 'Accept': 'text/html' }, cache: 'no-store', credentials: 'same-origin' });
            if (resp.redirected) { window.location.href = resp.url; return; }
            if (resp.status === 401 || resp.status === 403) { window.location.href = '/login'; return; }
            if (!resp.ok) return;
            const html = await resp.text();
            if (isFullDocument(html)) {
                try { window.showToast('warning', 'Не удалось обновить блок: получена HTML-страница сервера.'); } catch(_){ }
                return;
            }
            if (html && html !== node.innerHTML) {

                const prevH = node.offsetHeight;
                if (prevH > 0) node.style.minHeight = prevH + 'px';
                node.classList.add('is-swapping');
                node.innerHTML = html;
                try {
                    node.classList.add('flash');
                    setTimeout(()=> node.classList.remove('flash'), 600);
                } catch(_){ }
                try { initTooltipsWithin(node); } catch(_){ }

                try { setupConfirmationForms(node); } catch(_){ }

                setTimeout(()=>{ node.style.minHeight = ''; node.classList.remove('is-swapping'); }, 260);
            }
        } catch(_){ }
    }

    function initTooltipsWithin(root){
        if (!window.bootstrap) return;
        const scope = root || document;

        scope.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el=>{
            try { bootstrap.Tooltip.getInstance(el)?.dispose(); } catch(_){ }
        });
        const targets = scope.querySelectorAll('[data-bs-toggle="tooltip"], .btn[title], a.btn[title]');
        targets.forEach(el=>{
            try { new bootstrap.Tooltip(el, { container: 'body' }); } catch(_){ }
        });
    }

    function initializeCsrfForForms() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        const token = meta ? meta.getAttribute('content') : null;
        if (!token) return;

        document.querySelectorAll('form').forEach(form => {
            const method = (form.getAttribute('method') || '').toLowerCase();
            if (method !== 'post') return;
            form.addEventListener('submit', function () {
                if (form.querySelector('input[name="csrf_token"]')) return;
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrf_token';
                input.value = token;
                form.appendChild(input);
            });
        });
    }

    function initializeThemeToggle() {
        const THEME_KEY = 'ui_theme';
        const root = document.documentElement;
        const btn = document.getElementById('theme-toggle');
        const label = btn ? btn.querySelector('.theme-label') : null;

        function applyTheme(theme) {
            const next = (theme === 'light' || theme === 'dark') ? theme : 'dark';
            root.setAttribute('data-bs-theme', next);
            try { localStorage.setItem(THEME_KEY, next); } catch (_) {}
            if (label) label.textContent = next === 'dark' ? 'Тёмная' : 'Светлая';
        }


        let saved = 'dark';
        try { saved = localStorage.getItem(THEME_KEY) || 'dark'; } catch (_) {}
        applyTheme(saved);

        if (btn) {
            btn.addEventListener('click', function () {
                const current = root.getAttribute('data-bs-theme') || 'dark';
                const next = current === 'dark' ? 'light' : 'dark';
                applyTheme(next);
            });
        }
    }

    function initializePasswordToggles() {
        const togglePasswordButtons = document.querySelectorAll('.toggle-password');
        togglePasswordButtons.forEach(button => {

            const parent = button.closest('.password-wrapper') || button.closest('.form-group') || document;
            const input = parent.querySelector('input[type="password"], input[type="text"]');
            const setIcon = () => {
                if (!input) return;
                const isHidden = input.type === 'password';
                // Tabler icons вместо emoji (👁️ / 🙈)
                button.innerHTML = isHidden
                    ? '<i class="ti ti-eye" aria-hidden="true"></i>'
                    : '<i class="ti ti-eye-off" aria-hidden="true"></i>';
                button.setAttribute('aria-label', isHidden ? 'Показать пароль' : 'Скрыть пароль');
                button.setAttribute('title', isHidden ? 'Показать' : 'Скрыть');
            };
            setIcon();

            button.addEventListener('click', function () {
                const scope = this.closest('.password-wrapper') || this.closest('.form-group') || document;
                const passwordInput = scope.querySelector('input[type="password"], input[type="text"]');
                if (!passwordInput) return;
                if (passwordInput.type === 'password') {
                    try { passwordInput.type = 'text'; } catch(_) {}
                } else {
                    try { passwordInput.type = 'password'; } catch(_) {}
                }
                setIcon();
            });
        });
    }

    function setupBotControlForms() {
        const forms = document.querySelectorAll(
            'form[action*="start-bot"], form[action*="stop-bot"], form[action*="start-both-bots"], form[action*="stop-both-bots"], form[action*="restart-both-bots"], form[action*="start-support-bot"], form[action*="stop-support-bot"]'
        );
        forms.forEach(form => {
            form.addEventListener('submit', function () {
                const button = form.querySelector('button[type="submit"]');
                if (button) {
                    button.disabled = true;
                    const original = button.textContent;
                    button.dataset.originalLabel = original;
                    button.textContent = '...';
                }
                // Блокируем соседние кнопки управления ботами на время запроса
                document.querySelectorAll('.bot-control button, .mobile-bot-control button').forEach(btn => {
                    btn.disabled = true;
                });
            });
        });
    }

    function setupConfirmationForms(root) {
        const scope = root || document;
        const forms = scope.querySelectorAll('form[data-confirm]');
        forms.forEach(form => {
            form.addEventListener('submit', async function (event) {
                const message = form.getAttribute('data-confirm');
                if (!confirm(message)) {
                    event.preventDefault();
                    return;
                }

                if (form.getAttribute('data-ajax') === 'delete') {
                    event.preventDefault();
                    try {
                        const fd = new FormData(form);

                        if (!fd.get('csrf_token')){
                            const t = getCsrfToken();
                            if (t) fd.append('csrf_token', t);
                        }
                        const resp = await fetch(form.action, { method: 'POST', body: fd, credentials: 'same-origin' });
                        if (resp.ok) {
                            const action = form.getAttribute('data-action');
                            const msg = action === 'revoke-keys' ? 'Ключи отозваны' : 'Удалено';
                            try { window.showToast('success', msg); } catch(_){ }
                            const targetId = form.getAttribute('data-refresh-target');
                            if (targetId) { try { await window.refreshContainerById(targetId); } catch(_){ } }
                        } else {
                            const action = form.getAttribute('data-action');
                            const msg = action === 'revoke-keys' ? 'Не удалось отозвать ключи' : 'Не удалось удалить';
                            try { window.showToast('danger', msg); } catch(_){ }
                        }
                    } catch(_){ try { window.showToast('danger', 'Ошибка удаления'); } catch(__){} }
                }
            });
        });
    }


    document.querySelectorAll('.modal .modal-dialog').forEach(dlg => {
        if (!dlg.classList.contains('modal-dialog-centered')) {
            dlg.classList.add('modal-dialog-centered');
        }
    });

    function initializeDashboardCharts() {
        const usersChartCanvas = document.getElementById('newUsersChart');
        if (!usersChartCanvas || typeof CHART_DATA === 'undefined') {
            return;
        }

        function prepareChartData(data, label, color) {
            const labels = [];
            const values = [];
            const today = new Date();

            for (let i = 29; i >= 0; i--) {
                const date = new Date(today);
                date.setDate(today.getDate() - i);
                const dateString = date.toISOString().split('T')[0];
                const formattedDate = `${date.getDate().toString().padStart(2, '0')}.${(date.getMonth() + 1).toString().padStart(2, '0')}`;
                labels.push(formattedDate);
                values.push(data[dateString] || 0);
            }

            return {
                labels: labels,
                datasets: [
                    {
                        label: label,
                        data: values,
                        borderColor: color,
                        backgroundColor: color + '33',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                    },
                ],
            };
        }

        function updateChartFontsAndLabels(chart) {
            const isMobile = window.innerWidth <= 768;
            const isVerySmall = window.innerWidth <= 470;
            chart.options.scales.x.ticks.font.size = isMobile ? 10 : 12;
            chart.options.scales.y.ticks.font.size = isMobile ? 10 : 12;
            chart.options.plugins.legend.labels.font.size = isMobile ? 12 : 14;
            chart.options.scales.x.ticks.maxTicksLimit = isMobile ? 8 : 15;

            chart.options.scales.x.ticks.display = !isVerySmall;
            chart.options.scales.y.ticks.display = !isVerySmall;
            chart.options.plugins.legend.display = !isVerySmall;
            chart.update();
        }

        const usersCtx = usersChartCanvas.getContext('2d');
        const usersChartData = prepareChartData(
            CHART_DATA.users,
            'Новые пользователи',
            '#007bff'
        );
        const usersChart = new Chart(usersCtx, {
            type: 'line',
            data: usersChartData,
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0,
                            font: {
                                size: window.innerWidth <= 768 ? 10 : 12
                            },
                            display: true
                        }
                    },
                    x: {
                        ticks: {
                            font: {
                                size: window.innerWidth <= 768 ? 10 : 12
                            },
                            maxTicksLimit: window.innerWidth <= 768 ? 8 : 15,
                            maxRotation: 45,
                            minRotation: 45,
                            display: true
                        }
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    autoPadding: true,
                    padding: 0
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            font: {
                                size: window.innerWidth <= 768 ? 12 : 14
                            }
                        }
                    }
                }
            }
        });

        const keysChartCanvas = document.getElementById('newKeysChart');
        if (!keysChartCanvas) return;

        const keysCtx = keysChartCanvas.getContext('2d');
        const keysChartData = prepareChartData(
            CHART_DATA.keys,
            'Новые ключи',
            '#28a745'
        );
        const keysChart = new Chart(keysCtx, {
            type: 'line',
            data: keysChartData,
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0,
                            font: {
                                size: window.innerWidth <= 768 ? 10 : 12
                            },
                            display: window.innerWidth > 470
                        }
                    },
                    x: {
                        ticks: {
                            font: {
                                size: window.innerWidth <= 768 ? 10 : 12
                            },
                            maxTicksLimit: window.innerWidth <= 768 ? 8 : 15,
                            maxRotation: 45,
                            minRotation: 45,
                            display: window.innerWidth > 470
                        }
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    autoPadding: true,
                    padding: 0
                },
                plugins: {
                    legend: {
                        labels: {
                            font: {
                                size: window.innerWidth <= 768 ? 12 : 14
                            },
                            display: window.innerWidth > 470
                        }
                    }
                }
            }
        });

        window.addEventListener('resize', () => {
            updateChartFontsAndLabels(usersChart);
            updateChartFontsAndLabels(keysChart);
        });


        async function refreshCharts(){
            try{
                const resp = await fetch('/dashboard/charts.json', { headers: { 'Accept': 'application/json' }, credentials: 'same-origin', cache: 'no-store' });
                if (resp.redirected) { window.location.href = resp.url; return; }
                if (resp.status === 401 || resp.status === 403) { window.location.href = '/login'; return; }
                if (!resp.ok) return;
                const fresh = await resp.json();
                if (!fresh) return;
                const newUsers = prepareChartData(fresh.users, 'Новые пользователи', '#007bff');
                const newKeys = prepareChartData(fresh.keys, 'Новые ключи', '#28a745');
                usersChart.data.labels = newUsers.labels;
                usersChart.data.datasets[0].data = newUsers.datasets[0].data;
                keysChart.data.labels = newKeys.labels;
                keysChart.data.datasets[0].data = newKeys.datasets[0].data;
                usersChart.update('none');
                keysChart.update('none');
            }catch(_){}
        }
        

        if (!window.disableAutoUpdate) {
            setTimeout(() => {
                setInterval(refreshCharts, 10000);
            }, 1500);
        }
    }

    function initializeTicketAutoRefresh() {
        const root = document.getElementById('ticket-root');
        if (!root) return;

        if (window.disableAutoUpdate) return;

        const ticketId = root.getAttribute('data-ticket-id');
        const chatBox = document.getElementById('chat-box');
        const statusEl = document.getElementById('ticket-status');
        if (!ticketId || !chatBox || !statusEl) return;

        let lastKey = '';
        let lastCount = 0;

        function buildMessageNode(m) {
            const wrap = document.createElement('div');
            wrap.className = 'chat-message ' + (m.sender === 'admin' ? 'from-admin' : 'from-user');

            const meta = document.createElement('div');
            meta.className = 'meta';
            const sender = document.createElement('span');
            sender.className = 'sender';
            sender.textContent = m.sender === 'admin' ? 'Админ' : 'Пользователь';
            const time = document.createElement('span');
            time.className = 'time';
            time.textContent = m.created_at || '';
            meta.appendChild(sender);
            meta.appendChild(time);

            const content = document.createElement('div');
            content.className = 'content';
            content.textContent = m.content || '';

            wrap.appendChild(meta);
            wrap.appendChild(content);
            return wrap;
        }

        function updateStatus(status) {
            if (status === 'open') {
                statusEl.innerHTML = '<span class="status-dot status-dot-animated bg-green"></span><span class="badge bg-green ms-1">Открыт</span>';
                const textarea = document.getElementById('reply-text');
                const replyBtn = document.getElementById('reply-btn');
                if (textarea) textarea.disabled = false;
                if (replyBtn) replyBtn.disabled = false;
                const toggleBtn = document.getElementById('toggle-status-btn');
                if (toggleBtn) { toggleBtn.textContent = 'Закрыть'; toggleBtn.value = 'close'; toggleBtn.className = 'btn btn-danger'; }
            } else {
                statusEl.innerHTML = '<span class="status-dot"></span><span class="badge ms-1">Закрыт</span>';
                const textarea = document.getElementById('reply-text');
                const replyBtn = document.getElementById('reply-btn');
                if (textarea) textarea.disabled = true;
                if (replyBtn) replyBtn.disabled = true;
                const toggleBtn = document.getElementById('toggle-status-btn');
                if (toggleBtn) { toggleBtn.textContent = 'Открыть'; toggleBtn.value = 'open'; toggleBtn.className = 'btn btn-success'; }
            }
        }

        async function fetchAndRender() {
            try {
                const resp = await fetch(`/support/${ticketId}/messages.json`, { headers: { 'Accept': 'application/json' } });
                if (!resp.ok) return;
                const data = await resp.json();
                const items = Array.isArray(data.messages) ? data.messages : [];
                const key = JSON.stringify({ len: items.length, last: items[items.length - 1] || null, status: data.status });
                if (key === lastKey) return;

                const nearBottom = (chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight) < 60;

                chatBox.innerHTML = '';
                if (items.length === 0) {
                    const p = document.createElement('p');
                    p.className = 'no-messages';
                    p.textContent = 'Сообщений пока нет.';
                    chatBox.appendChild(p);
                } else {
                    for (let i = 0; i < items.length; i++) {
                        const node = buildMessageNode(items[i]);
                        if (i >= lastCount) {
                            node.classList.add('flash');
                            setTimeout(() => node.classList.remove('flash'), 1800);
                        }
                        chatBox.appendChild(node);
                    }
                }

                updateStatus(data.status);

                if (nearBottom) {
                    chatBox.scrollTop = chatBox.scrollHeight;
                }

                lastKey = key;
                lastCount = items.length;
            } catch (e) {

            }
        }

        fetchAndRender();
        const interval = setInterval(fetchAndRender, 2500);
        window.addEventListener('beforeunload', () => clearInterval(interval));
    }


    function initializeGlobalAutoRefresh() {
        
    }


    function initializeSoftAutoUpdate() {
        const nodes = Array.from(document.querySelectorAll('[data-fetch-url]'));
        if (!nodes.length) return;
        nodes.forEach(node => {
            if (window.disableAutoUpdate) return;
            const url = node.getAttribute('data-fetch-url');
            const intervalAttr = node.getAttribute('data-fetch-interval');
            let intervalMs = Number(intervalAttr || '8000');
            if (!Number.isFinite(intervalMs) || intervalMs <= 0) intervalMs = 8000;
            if (!url) return;
            let timer = null;
            let isFirstLoad = true;
            
            async function tick(){
                if (window.disableAutoUpdate) return;
                try{

                    if (!isFirstLoad) {
                        node.classList.add('loading');
                    }
                    
                    const resp = await fetch(url, { headers: { 'Accept': 'text/html' }, cache: 'no-store', credentials: 'same-origin' });
                    if (resp.redirected) { window.location.href = resp.url; return; }
                    if (resp.status === 401 || resp.status === 403) { window.location.href = '/login'; return; }
                    if (!resp.ok) return;
                    const html = await resp.text();
                    if (isFullDocument(html)) {
                        try { window.showToast('warning', 'Автообновление пропущено: получена HTML-страница сервера.'); } catch(_){ }
                        return;
                    }
                    if (html && html !== node.innerHTML) {
                        const prevH = node.offsetHeight;
                        if (prevH > 0) node.style.minHeight = prevH + 'px';
                        node.classList.add('is-swapping');
                        node.innerHTML = html;
                        try {
                            node.classList.add('flash');
                            setTimeout(()=> node.classList.remove('flash'), 6000);
                        } catch(_){ }

                        try { initTooltipsWithin(node); } catch(_){ }
                        try { setupConfirmationForms(node); } catch(_){ }
                        setTimeout(()=>{ node.style.minHeight = ''; node.classList.remove('is-swapping'); }, 260);
                    }
                    

                    node.classList.remove('loading');
                    if (isFirstLoad) {
                        node.classList.add('dashboard-loaded');
                        isFirstLoad = false;
                    }
                }catch(_){}
            }
            

            setTimeout(() => {
                tick();
                timer = setInterval(tick, Math.max(4000, intervalMs));
            }, 1000);
            
            node.addEventListener('soft-update-stop', ()=>{ if (timer){ clearInterval(timer); timer=null; } });
            window.addEventListener('beforeunload', ()=>{ if (timer){ clearInterval(timer); timer=null; } });
        });
    }


    function initializeSettingsTabs() {
        const nav = document.querySelector('#settings-tabs') || document.querySelector('.nav.nav-tabs.settings-tabs') || document.querySelector('.nav.nav-tabs');
        const container = document.querySelector('.settings-container');
        if (!nav || !container) return;

        const links = Array.from(nav.querySelectorAll('a.nav-link'));
        const SCROLL_KEY = 'settings-tabs-scroll-left';

        const sections = Array.from(document.querySelectorAll('.settings-section'));
        const rightCol = document.querySelector('.settings-column-right');

        function saveTabsScroll() {
            try { sessionStorage.setItem(SCROLL_KEY, String(nav.scrollLeft || 0)); } catch (_) {}
        }

        function restoreTabsScroll() {
            try {
                const raw = sessionStorage.getItem(SCROLL_KEY);
                if (raw == null || raw === '') return false;
                const left = Number(raw);
                if (!Number.isFinite(left)) return false;
                nav.scrollLeft = left;
                return true;
            } catch (_) {
                return false;
            }
        }

        function scrollActiveTabIntoView(smooth) {
            const active = nav.querySelector('.nav-link.active');
            if (!active) return;
            const item = active.closest('.nav-item') || active;
            try {
                const navRect = nav.getBoundingClientRect();
                const itemRect = item.getBoundingClientRect();
                const fullyVisible = itemRect.left >= navRect.left && itemRect.right <= navRect.right;
                if (fullyVisible && !smooth) return;
                const delta = (itemRect.left - navRect.left) - (navRect.width - itemRect.width) / 2;
                const next = Math.max(0, nav.scrollLeft + delta);
                if (typeof nav.scrollTo === 'function') {
                    nav.scrollTo({ left: next, behavior: smooth ? 'smooth' : 'auto' });
                } else {
                    nav.scrollLeft = next;
                }
            } catch (_) {
                try { item.scrollIntoView({ inline: 'center', block: 'nearest', behavior: smooth ? 'smooth' : 'auto' }); } catch (__){}
            }
            saveTabsScroll();
        }

        function show(targetHash) {
            const hash = (targetHash && targetHash.startsWith('#')) ? targetHash : '#panel';

            let currentVisible = document.querySelector('.settings-column-right .settings-section:not(.is-hidden)');
            const currentHeight = currentVisible ? currentVisible.offsetHeight : 0;
            const targetEl = document.querySelector(hash);
            const targetHeight = targetEl ? targetEl.offsetHeight : 0;
            if (rightCol) {
                const h = Math.max(currentHeight, targetHeight);
                if (h > 0) rightCol.style.minHeight = h + 'px';
            }
            sections.forEach(sec => {
                const isTarget = ('#' + sec.id === hash);
                if (isTarget) {

                    sec.classList.remove('is-hidden');
                    try {
                        sec.querySelectorAll('input, select, textarea').forEach(el => {
                            const wasRequired = el.getAttribute('data-was-required');
                            if (wasRequired === '1') {
                                el.setAttribute('required', '');
                                el.removeAttribute('data-was-required');
                            }
                        });
                    } catch (_) {  }
                } else {

                    sec.classList.add('is-hidden');
                    try {
                        sec.querySelectorAll('input, select, textarea').forEach(el => {
                            if (el.hasAttribute('required')) {
                                el.setAttribute('data-was-required', '1');
                                el.removeAttribute('required');
                            }
                        });
                    } catch (_) {  }
                }
            });
            links.forEach(a => {
                if (a.getAttribute('href') === hash) a.classList.add('active');
                else a.classList.remove('active');
            });

            const anyVisible = sections.some(sec => !sec.classList.contains('is-hidden'));
            if (!anyVisible && sections.length) {
                sections[0].classList.remove('is-hidden');
                try {
                    sections[0].querySelectorAll('input, select, textarea').forEach(el => {
                        const wasRequired = el.getAttribute('data-was-required');
                        if (wasRequired === '1') {
                            el.setAttribute('required', '');
                            el.removeAttribute('data-was-required');
                        }
                    });
                } catch (_) {  }
            }

            if (rightCol) setTimeout(() => { rightCol.style.minHeight = ''; }, 260);


            const leftCol = document.querySelector('.settings-column-left');
            if (hash === '#hosts') {
                if (leftCol) {
                    leftCol.style.display = '';
                    leftCol.style.flex = '1 1 100%';
                    leftCol.style.minWidth = '0';
                }
                if (rightCol) {
                    rightCol.style.display = 'none';
                    rightCol.style.flex = '';
                    rightCol.style.minWidth = '';
                }
            } else {
                if (leftCol) {
                    leftCol.style.display = 'none';
                    leftCol.style.flex = '';
                    leftCol.style.minWidth = '';
                }
                if (rightCol) {
                    rightCol.style.display = '';
                    rightCol.style.flex = '1 1 100%';
                    rightCol.style.minWidth = '0';
                }
            }
        }


        links.forEach(a => {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                const href = a.getAttribute('href');
                if (!href) return;
                const y = window.scrollY;
                show(href);

                const tabName = href.startsWith('#') ? href.slice(1) : href;
                try { history.replaceState(null, '', `?tab=${encodeURIComponent(tabName)}${href}`); } catch(_) {}

                window.scrollTo(0, y);
                requestAnimationFrame(() => scrollActiveTabIntoView(true));
            });
        });


        window.addEventListener('hashchange', () => {
            const y = window.scrollY;
            show(location.hash);
            window.scrollTo(0, y);
            requestAnimationFrame(() => scrollActiveTabIntoView(true));
        });

        let scrollSaveTimer = null;
        nav.addEventListener('scroll', () => {
            if (scrollSaveTimer) clearTimeout(scrollSaveTimer);
            scrollSaveTimer = setTimeout(saveTabsScroll, 80);
        }, { passive: true });


        const params = new URLSearchParams(window.location.search);
        const tabParam = params.get('tab');
        const initialHash = tabParam ? `#${tabParam}` : (location.hash || '#panel');
        show(initialHash);

        try {
            const tabName = initialHash.startsWith('#') ? initialHash.slice(1) : initialHash;
            history.replaceState(null, '', `?tab=${encodeURIComponent(tabName)}${initialHash}`);
        } catch(_) {}

        // Restore prior scroll, then ensure the selected tab is visible
        restoreTabsScroll();
        requestAnimationFrame(() => {
            scrollActiveTabIntoView(false);
            requestAnimationFrame(() => scrollActiveTabIntoView(false));
        });
    }


    initTooltipsWithin(document);
    initializePasswordToggles();
    setupBotControlForms();
    setupConfirmationForms();
    initializeDashboardCharts();
    initializeTicketAutoRefresh();

    initializeSoftAutoUpdate();
    initializeSettingsTabs();
    initializeThemeToggle();
    initializeCsrfForForms();

    // Hide lingering tooltips when a modal opens (they render on body at high z-index)
    document.addEventListener('show.bs.modal', () => {
        try {
            document.querySelectorAll('.tooltip').forEach((node) => {
                try {
                    const tip = bootstrap.Tooltip.getInstance(node);
                    if (tip) tip.hide();
                } catch (_) {}
                node.classList.remove('show');
                node.setAttribute('aria-hidden', 'true');
            });
            if (window.bootstrap?.Tooltip) {
                document.querySelectorAll('[data-bs-toggle="tooltip"], .btn[title], a.btn[title]').forEach((el) => {
                    try { bootstrap.Tooltip.getInstance(el)?.hide(); } catch (_) {}
                });
            }
        } catch (_) {}
    });


    (function initializeBackupRestoreUI(){
        const select = document.getElementById('existing_backup');
        const dateBadge = document.getElementById('backup-date');
        const pickBtn = document.getElementById('btn-pick-file');
        const fileInput = document.getElementById('db_file');
        const fileNameBox = document.getElementById('picked-file-name');
        if (!select && !fileInput) return;

        function setDateText(val){
            if (!dateBadge) return;
            dateBadge.textContent = val && val.trim() ? val : '—';
        }


        if (select){
            select.addEventListener('change', () => {
                const opt = select.options[select.selectedIndex];
                const mtime = opt ? (opt.getAttribute('data-mtime') || '') : '';
                setDateText(mtime);
                if (fileInput){
                    try { fileInput.value = ''; } catch(_){}
                }
                if (fileNameBox){ fileNameBox.value = fileInput && fileInput.files && fileInput.files[0] ? (fileInput.files[0].name||'Файл не выбран') : 'Файл не выбран'; }
            });
        }


        if (pickBtn && fileInput){
            pickBtn.addEventListener('click', () => {
                try { fileInput.click(); } catch(_){ }
            });
            fileInput.addEventListener('change', () => {
                const name = (fileInput.files && fileInput.files[0]) ? (fileInput.files[0].name || 'Файл не выбран') : 'Файл не выбран';
                if (fileNameBox) fileNameBox.value = name;
                if (select){ select.value = ''; }
                setDateText('');
            });
        }


        (function(){
            const wrap = document.querySelector('.soft-select[data-target="existing_backup"]');
            const selectEl = document.getElementById('existing_backup');
            if (!wrap || !selectEl) return;
            const toggleEl = document.getElementById('existing_backup_toggle');
            const menuEl = document.getElementById('existing_backup_menu');
            if (!toggleEl || !menuEl) return;

            function labelForOption(opt){
                const txt = (opt && (opt.textContent || '').trim()) || '';
                return txt || '— Не выбран —';
            }

            function build(){

                menuEl.innerHTML = '';
                const opts = Array.from(selectEl.options||[]);


                const ph = document.createElement('div');
                ph.className = 'soft-select-item is-placeholder' + (selectEl.value === '' ? ' is-active' : '');
                ph.textContent = '— Выберите архив из списка —';
                ph.addEventListener('click', () => {
                    selectEl.value = '';
                    selectEl.dispatchEvent(new Event('change', { bubbles:true }));
                    closeMenu();
                });
                menuEl.appendChild(ph);


                opts.forEach(opt => {
                    if (opt.value === '') return;
                    const item = document.createElement('div');
                    item.className = 'soft-select-item' + (opt.selected ? ' is-active' : '');
                    item.dataset.value = opt.value;
                    item.textContent = labelForOption(opt);
                    item.addEventListener('click', () => {
                        selectEl.value = opt.value;

                        menuEl.querySelectorAll('.soft-select-item').forEach(n => n.classList.remove('is-active'));
                        item.classList.add('is-active');

                        toggleEl.textContent = labelForOption(opt);
                        closeMenu();

                        selectEl.dispatchEvent(new Event('change', { bubbles:true }));
                    });
                    menuEl.appendChild(item);
                });

                const active = opts.find(o=>o.selected) || opts[0];
                toggleEl.textContent = labelForOption(active);
            }

            function placeMenu(){
                const r = toggleEl.getBoundingClientRect();
                menuEl.style.position = 'fixed';
                menuEl.style.left = `${Math.round(r.left)}px`;

                const prevDisplay = menuEl.style.display;
                menuEl.style.display = 'block';
                const h = Math.max(0, menuEl.offsetHeight || 0);

                let top = Math.round(r.top - h - 6);

                if (top < 8) {
                    const below = Math.round(r.bottom + 6);

                    const maxBottom = window.innerHeight - 8;
                    top = Math.min(below, maxBottom - h);
                }
                menuEl.style.top = `${top}px`;
                menuEl.style.width = `${Math.round(r.width)}px`;
                menuEl.style.zIndex = '1065';

                menuEl.style.display = prevDisplay || 'block';
            }
            function openMenu(){
                if (menuEl.parentElement !== document.body) document.body.appendChild(menuEl);
                placeMenu();
                wrap.classList.add('open');
                menuEl.style.display = 'block';
                window.addEventListener('scroll', placeMenu, true);
                window.addEventListener('resize', placeMenu, true);
            }
            function closeMenu(){
                wrap.classList.remove('open');
                menuEl.style.display = 'none';
                if (menuEl.parentElement === document.body) wrap.appendChild(menuEl);
                window.removeEventListener('scroll', placeMenu, true);
                window.removeEventListener('resize', placeMenu, true);
            }

            toggleEl.addEventListener('click', (e)=>{
                e.stopPropagation();
                if (wrap.classList.contains('open')) closeMenu(); else openMenu();
            });
            document.addEventListener('click', (e)=>{ if (!wrap.contains(e.target)) closeMenu(); });
            document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape') closeMenu(); });


            selectEl.addEventListener('change', ()=>{
                const selOpt = selectEl.options[selectEl.selectedIndex];
                toggleEl.textContent = labelForOption(selOpt);
                const mtime = selOpt ? (selOpt.getAttribute('data-mtime')||'') : '';
                if (dateBadge) dateBadge.textContent = mtime || '—';
            });

            build();
        })();
    })();


    (function(){
        const select = document.getElementById('referral_reward_type');
        const compatToggle = document.getElementById('enable_fixed_referral_bonus');
        const sections = Array.from(document.querySelectorAll('[data-ref-section]'));
        if (!select || sections.length === 0) return;
        function apply(){
            const val = (select.value || 'percent_purchase').trim();
            sections.forEach(sec => {
                const show = sec.getAttribute('data-ref-section') === val;
                sec.style.display = show ? '' : 'none';
                sec.querySelectorAll('input,select,textarea,button').forEach(el => el.disabled = !show);
            });
            if (compatToggle) compatToggle.value = (val === 'fixed_purchase') ? 'true' : 'false';
        }
        apply();
        select.addEventListener('change', apply);
    })();


    (function(){
        const wrap = document.querySelector('.soft-select[data-target="referral_reward_type"]');
        const selectEl = document.getElementById('referral_reward_type');
        if (!wrap || !selectEl) return;
        const toggleEl = document.getElementById('referral_reward_type_toggle');
        const menuEl = document.getElementById('referral_reward_type_menu');
        if (!toggleEl || !menuEl) return;

        function build(){

            menuEl.innerHTML = '';
            const opts = Array.from(selectEl.options||[]);
            opts.forEach(opt => {
                const item = document.createElement('div');
                item.className = 'soft-select-item' + (opt.selected ? ' is-active' : '');
                item.dataset.value = opt.value;
                item.textContent = opt.textContent || '';
                item.addEventListener('click', () => {
                    selectEl.value = opt.value;

                    menuEl.querySelectorAll('.soft-select-item').forEach(n => n.classList.remove('is-active'));
                    item.classList.add('is-active');

                    toggleEl.textContent = opt.textContent || '';
                    closeMenu();

                    selectEl.dispatchEvent(new Event('change', { bubbles:true }));
                });
                menuEl.appendChild(item);
            });
            const active = opts.find(o=>o.selected) || opts[0];
            toggleEl.textContent = active ? (active.textContent||'') : '';
        }

        function placeMenu(){
            const r = toggleEl.getBoundingClientRect();
            menuEl.style.position='fixed';
            menuEl.style.left = `${Math.round(r.left)}px`;
            menuEl.style.top = `${Math.round(r.bottom + 6)}px`;
            menuEl.style.width = `${Math.round(r.width)}px`;
            menuEl.style.zIndex = '1065';
        }
        function openMenu(){
            if (menuEl.parentElement !== document.body) document.body.appendChild(menuEl);
            placeMenu();
            wrap.classList.add('open');
            menuEl.style.display='block';
            window.addEventListener('scroll', placeMenu, true);
            window.addEventListener('resize', placeMenu, true);
        }
        function closeMenu(){
            wrap.classList.remove('open');
            menuEl.style.display='none';
            if (menuEl.parentElement === document.body) wrap.appendChild(menuEl);
            window.removeEventListener('scroll', placeMenu, true);
            window.removeEventListener('resize', placeMenu, true);
        }

        toggleEl.addEventListener('click', (e)=>{
            e.stopPropagation();
            if (wrap.classList.contains('open')) closeMenu(); else openMenu();
        });
        document.addEventListener('click', (e)=>{ if (!wrap.contains(e.target)) closeMenu(); });
        document.addEventListener('keydown', (e)=>{ if (e.key==='Escape') closeMenu(); });


        selectEl.addEventListener('change', build);
        build();
    })();


    document.querySelectorAll('[data-edit-row]').forEach(row => {
        const input = row.querySelector('[data-edit-target]');
        const btnEdit = row.querySelector('[data-action="edit"]');
        const btnSave = row.querySelector('[data-action="save"]');
        const btnCancel = row.querySelector('[data-action="cancel"]');
        if (!input || !btnEdit || !btnSave || !btnCancel) return;

        const orig = { value: input.value };
        function setMode(editing) {
            if (editing) {
                input.readOnly = false;
                input.classList.add('is-editing');
                btnEdit.classList.add('d-none');
                btnSave.classList.remove('d-none');
                btnCancel.classList.remove('d-none');
                input.focus();
                try { input.setSelectionRange(input.value.length, input.value.length); } catch(_) {}
            } else {
                input.readOnly = true;
                input.classList.remove('is-editing');
                btnEdit.classList.remove('d-none');
                btnSave.classList.add('d-none');
                btnCancel.classList.add('d-none');
            }
        }

        btnEdit.addEventListener('click', () => setMode(true));
        btnCancel.addEventListener('click', () => { input.value = orig.value; setMode(false); });
        row.addEventListener('submit', () => { orig.value = input.value; setMode(false); });
    });


    // Mobile sidebar drawer (off-canvas)
    function setupMobileSidebarDrawer() {
        const burger = document.getElementById('burger');
        const sidebar = document.querySelector('.sidebar');
        if (!burger || !sidebar) return;

        let overlay = document.getElementById('sidebar-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'sidebar-overlay';
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);
        }

        function sync() {
            document.body.classList.toggle('sidebar-open', !!burger.checked);
        }

        burger.addEventListener('change', sync);
        overlay.addEventListener('click', function () {
            burger.checked = false;
            sync();
        });

        // Close drawer after navigation on small screens
        sidebar.querySelectorAll('a.nav-link').forEach(function (a) {
            a.addEventListener('click', function () {
                if (window.matchMedia && window.matchMedia('(max-width: 992px)').matches) {
                    burger.checked = false;
                    sync();
                }
            });
        });

        window.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && burger.checked) {
                burger.checked = false;
                sync();
            }
        });

        // If user rotates/resizes to desktop, ensure drawer is closed
        window.addEventListener('resize', function () {
            if (window.matchMedia && !window.matchMedia('(max-width: 992px)').matches && burger.checked) {
                burger.checked = false;
                sync();
            }
        });

        sync();
    }

    setupMobileSidebarDrawer();

    // Support tickets search
    const supportSearch = document.getElementById('support-search');
    if (supportSearch) {
        supportSearch.addEventListener('input', function(e) {
            const query = e.target.value.toLowerCase().trim();
            const ticketCards = document.querySelectorAll('.support-ticket-card');
            
            ticketCards.forEach(card => {
                if (!query) {
                    card.style.display = '';
                    return;
                }
                
                const ticketId = card.querySelector('.support-ticket-id')?.textContent.toLowerCase() || '';
                const ticketSubject = card.querySelector('.support-ticket-subject')?.textContent.toLowerCase() || '';
                const ticketMeta = card.querySelector('.support-ticket-meta')?.textContent.toLowerCase() || '';
                
                const matches = ticketId.includes(query) || 
                               ticketSubject.includes(query) || 
                               ticketMeta.includes(query);
                
                card.style.display = matches ? '' : 'none';
            });
        });
    }
});
// Отключение автоматической перезагрузки
(function() {
    // Очищаем все интервалы
    let id = 1;
    while(id < 10000) {
        clearInterval(id);
        id++;
    }
    
    // Отправляем событие остановки
    document.querySelectorAll('[data-fetch-url]').forEach(e => {
        e.dispatchEvent(new Event('soft-update-stop'));
    });
    
    console.log('Auto-updates disabled');
})();
