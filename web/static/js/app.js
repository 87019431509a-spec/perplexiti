// ═══════════════════════════════════════════════════════════════════════════════
// NEURO COMMENT BOT - PREMIUM DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────────────────────────────
// GLOBALS
// ─────────────────────────────────────────────────────────────────────────────────

let ws = null;
let chart = null;
let logs = [];
let reconnectAttempts = 0;
const MAX_LOGS = 500;

// ─────────────────────────────────────────────────────────────────────────────────
// INITIALIZATION
// ─────────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initWebSocket();
    initChart();
    loadInitialData();
    
    // Auto-refresh every 30 seconds
    setInterval(refreshData, 30000);
});

// ─────────────────────────────────────────────────────────────────────────────────
// NAVIGATION
// ─────────────────────────────────────────────────────────────────────────────────

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            showPage(page);
            
            // Update active state
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function showPage(pageId) {
    document.querySelectorAll('.page').forEach(page => {
        page.style.display = 'none';
    });
    document.getElementById(`page-${pageId}`).style.display = 'block';
    
    // Load page-specific data
    switch(pageId) {
        case 'accounts': loadAccounts(); break;
        case 'channels': loadChannels(); break;
        case 'proxies': loadProxies(); break;
        case 'comments': loadComments(); break;
        case 'settings': loadSettings(); break;
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// WEBSOCKET
// ─────────────────────────────────────────────────────────────────────────────────

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        reconnectAttempts = 0;
        addLog('success', 'system', '🔗 Подключено к серверу');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        reconnectAttempts++;
        
        if (reconnectAttempts < 10) {
            setTimeout(initWebSocket, 2000 * reconnectAttempts);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    // Ping to keep connection alive
    setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({type: 'ping'}));
        }
    }, 30000);
}

function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'log':
            addLog(data.data.level, data.data.service, data.data.message);
            break;
        case 'stats':
            updateStats(data.data);
            break;
        case 'status':
            updateServiceStatus(data.data);
            break;
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// LOGS
// ─────────────────────────────────────────────────────────────────────────────────

function addLog(level, service, message) {
    const now = new Date();
    const time = now.toLocaleTimeString('ru-RU');
    
    const log = { time, level, service, message };
    logs.unshift(log);
    
    if (logs.length > MAX_LOGS) {
        logs = logs.slice(0, MAX_LOGS);
    }
    
    // Update logs count badge
    document.getElementById('logs-count').textContent = logs.length;
    
    // Render logs
    renderLogs();
}

function renderLogs() {
    const filter = document.getElementById('log-filter')?.value || 'all';
    const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.service === filter);
    
    const dashboardLogs = document.getElementById('dashboard-logs');
    const fullLogs = document.getElementById('full-logs');
    
    const logsHtml = filteredLogs.slice(0, 100).map((log, i) => `
        <div class="log-entry ${i === 0 ? 'new' : ''}">
            <span class="log-time">${log.time}</span>
            <span class="log-level ${log.level}">${getLevelIcon(log.level)}</span>
            <span class="log-service">${log.service}</span>
            <span class="log-message">${log.message}</span>
        </div>
    `).join('');
    
    if (dashboardLogs) dashboardLogs.innerHTML = logsHtml || '<div class="empty-state"><div class="empty-state-icon">📜</div><div class="empty-state-title">Нет событий</div></div>';
    if (fullLogs) fullLogs.innerHTML = logsHtml || '<div class="empty-state"><div class="empty-state-icon">📜</div><div class="empty-state-title">Нет событий</div></div>';
}

function getLevelIcon(level) {
    const icons = {
        'info': 'ℹ️',
        'success': '✅',
        'warning': '⚠️',
        'error': '❌'
    };
    return icons[level] || '📝';
}

function clearLogs() {
    logs = [];
    renderLogs();
    showNotification('success', 'Логи очищены');
}

// ─────────────────────────────────────────────────────────────────────────────────
// CHART
// ─────────────────────────────────────────────────────────────────────────────────

function initChart() {
    const ctx = document.getElementById('activityChart');
    if (!ctx) return;
    
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: [
                {
                    label: 'Комментарии',
                    data: Array(24).fill(0),
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Прогрев',
                    data: Array(24).fill(0),
                    borderColor: '#db6d28',
                    backgroundColor: 'rgba(219, 109, 40, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#8b949e' }
                }
            },
            scales: {
                x: {
                    grid: { color: '#21262d' },
                    ticks: { color: '#8b949e' }
                },
                y: {
                    grid: { color: '#21262d' },
                    ticks: { color: '#8b949e' },
                    beginAtZero: true
                }
            }
        }
    });
}

function updateChart(hourlyData) {
    if (!chart || !hourlyData) return;
    
    chart.data.datasets[0].data = hourlyData.comments || Array(24).fill(0);
    chart.data.datasets[1].data = hourlyData.warmup || Array(24).fill(0);
    chart.update();
}

// ─────────────────────────────────────────────────────────────────────────────────
// API CALLS
// ─────────────────────────────────────────────────────────────────────────────────

async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) options.body = JSON.stringify(body);
        
        const response = await fetch(`/api${endpoint}`, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showNotification('error', 'Ошибка соединения с сервером');
        return { success: false, error: error.message };
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// DATA LOADING
// ─────────────────────────────────────────────────────────────────────────────────

async function loadInitialData() {
    await Promise.all([
        loadStatus(),
        loadStats(),
        loadSettings()
    ]);
}

async function refreshData() {
    await Promise.all([
        loadStatus(),
        loadStats()
    ]);
}

async function loadStatus() {
    const result = await apiCall('/status');
    if (result.success) {
        updateServiceStatus(result.data.services);
        updateMode(result.data.mode);
    }
}

async function loadStats() {
    const result = await apiCall('/stats');
    if (result.success) {
        updateStats(result.data.today);
        if (result.data.hourly) {
            updateChart(result.data.hourly);
        }
    }
}

function updateStats(stats) {
    if (!stats) return;
    
    document.getElementById('stat-sent').textContent = stats.sent || 0;
    document.getElementById('stat-success').textContent = stats.success || 0;
    document.getElementById('stat-deleted').textContent = stats.deleted || 0;
    document.getElementById('stat-warmup').textContent = stats.warmup_actions || 0;
}

function updateServiceStatus(services) {
    if (!services) return;
    
    // Commenting
    if (services.commenting) {
        const running = services.commenting.running;
        document.getElementById('commenting-dot').className = `status-dot ${running ? 'running' : 'stopped'}`;
        document.getElementById('commenting-status').textContent = running ? 'Работает' : 'Остановлено';
        document.getElementById('btn-commenting-start').disabled = running;
        document.getElementById('btn-commenting-stop').disabled = !running;
        document.getElementById('service-commenting').classList.toggle('running', running);
        
        if (running && services.commenting.uptime) {
            document.getElementById('commenting-uptime').textContent = formatUptime(services.commenting.uptime);
        } else {
            document.getElementById('commenting-uptime').textContent = '';
        }
    }
    
    // Warmup
    if (services.warmup) {
        const running = services.warmup.running;
        document.getElementById('warmup-dot').className = `status-dot ${running ? 'running' : 'stopped'}`;
        document.getElementById('warmup-status').textContent = running ? 'Работает' : 'Остановлено';
        document.getElementById('btn-warmup-start').disabled = running;
        document.getElementById('btn-warmup-stop').disabled = !running;
        document.getElementById('service-warmup').classList.toggle('running', running);
        
        if (running && services.warmup.uptime) {
            document.getElementById('warmup-uptime').textContent = formatUptime(services.warmup.uptime);
        } else {
            document.getElementById('warmup-uptime').textContent = '';
        }
    }
}

function updateMode(mode) {
    const modeText = document.getElementById('mode-text');
    const modeValue = document.getElementById('current-mode');
    const modeSafe = document.getElementById('mode-safe');
    const modeNormal = document.getElementById('mode-normal');
    
    if (mode === 'SAFE') {
        modeText.textContent = 'SAFE';
        modeValue.className = 'mode-value safe';
        modeValue.querySelector('span:first-child').textContent = '🛡️';
        modeSafe?.classList.add('active', 'safe');
        modeNormal?.classList.remove('active');
    } else {
        modeText.textContent = 'NORMAL';
        modeValue.className = 'mode-value normal';
        modeValue.querySelector('span:first-child').textContent = '⚡';
        modeNormal?.classList.add('active');
        modeSafe?.classList.remove('active', 'safe');
    }
}

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
        return `${hours}ч ${minutes}м`;
    }
    return `${minutes}м`;
}

// ─────────────────────────────────────────────────────────────────────────────────
// SERVICE CONTROL
// ─────────────────────────────────────────────────────────────────────────────────

async function startCommenting() {
    document.getElementById('btn-commenting-start').disabled = true;
    showNotification('info', 'Запуск комментирования...');
    
    const result = await apiCall('/commenting/start', 'POST');
    
    if (result.success) {
        showNotification('success', 'Комментирование запущено');
        await loadStatus();
    } else {
        showNotification('error', result.error || 'Ошибка запуска');
        document.getElementById('btn-commenting-start').disabled = false;
    }
}

async function stopCommenting() {
    document.getElementById('btn-commenting-stop').disabled = true;
    showNotification('info', 'Остановка комментирования...');
    
    const result = await apiCall('/commenting/stop', 'POST');
    
    if (result.success) {
        showNotification('success', 'Комментирование остановлено');
        await loadStatus();
    } else {
        showNotification('error', result.error || 'Ошибка остановки');
        document.getElementById('btn-commenting-stop').disabled = false;
    }
}

async function startWarmup() {
    document.getElementById('btn-warmup-start').disabled = true;
    showNotification('info', 'Запуск прогрева...');
    
    const result = await apiCall('/warmup/start', 'POST');
    
    if (result.success) {
        showNotification('success', 'Прогрев запущен');
        await loadStatus();
    } else {
        showNotification('error', result.error || 'Ошибка запуска');
        document.getElementById('btn-warmup-start').disabled = false;
    }
}

async function stopWarmup() {
    document.getElementById('btn-warmup-stop').disabled = true;
    showNotification('info', 'Остановка прогрева...');
    
    const result = await apiCall('/warmup/stop', 'POST');
    
    if (result.success) {
        showNotification('success', 'Прогрев остановлен');
        await loadStatus();
    } else {
        showNotification('error', result.error || 'Ошибка остановки');
        document.getElementById('btn-warmup-stop').disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// ACCOUNTS
// ─────────────────────────────────────────────────────────────────────────────────

async function loadAccounts() {
    const result = await apiCall('/accounts');
    
    if (result.success) {
        const data = result.data;
        
        // Update stats
        document.getElementById('acc-sessions-comments').textContent = data.files?.comments?.sessions || 0;
        document.getElementById('acc-tdata-comments').textContent = data.files?.comments?.tdata || 0;
        document.getElementById('acc-sessions-warmup').textContent = data.files?.warmup?.sessions || 0;
        document.getElementById('acc-tdata-warmup').textContent = data.files?.warmup?.tdata || 0;
        
        // Render table
        const tbody = document.getElementById('accounts-table');
        
        if (!data.accounts || data.accounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Нет аккаунтов в базе данных</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.accounts.map((acc, i) => `
            <tr>
                <td>${i + 1}</td>
                <td class="font-mono">${acc.phone || 'N/A'}</td>
                <td>${acc.pool || 'comments'}</td>
                <td><span class="badge badge-${getStatusBadge(acc.status)}">${acc.status}</span></td>
                <td>
                    <div class="flex items-center gap-2">
                        <div class="progress-bar" style="width: 100px; height: 6px;">
                            <div class="progress-fill success" style="width: ${acc.warmup_level || 0}%"></div>
                        </div>
                        <span class="text-muted">${acc.warmup_level || 0}%</span>
                    </div>
                </td>
                <td>${acc.today_comments || 0}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="toggleAccount(${acc.id}, '${acc.status}')">
                        ${acc.status === 'active' ? '⏸️' : '▶️'}
                    </button>
                </td>
            </tr>
        `).join('');
    }
}

function getStatusBadge(status) {
    const badges = {
        'active': 'success',
        'paused': 'warning',
        'banned': 'danger'
    };
    return badges[status] || 'muted';
}

async function toggleAccount(id, currentStatus) {
    const action = currentStatus === 'active' ? 'pause' : 'resume';
    const result = await apiCall(`/accounts/${id}/${action}`, 'POST');
    
    if (result.success) {
        showNotification('success', `Аккаунт ${action === 'pause' ? 'приостановлен' : 'активирован'}`);
        loadAccounts();
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// CHANNELS
// ─────────────────────────────────────────────────────────────────────────────────

async function loadChannels() {
    const result = await apiCall('/channels');
    
    if (result.success) {
        const data = result.data;
        
        // Update stats
        document.getElementById('ch-comments').textContent = data.counts?.comments || 0;
        
        const channels = data.channels || [];
        document.getElementById('ch-active').textContent = channels.filter(c => c.status === 'active').length;
        document.getElementById('ch-sleep').textContent = channels.filter(c => c.status === 'sleep').length;
        document.getElementById('ch-disabled').textContent = channels.filter(c => c.status === 'disabled').length;
        
        // Render table
        const tbody = document.getElementById('channels-table');
        
        if (channels.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Нет каналов в базе данных</td></tr>';
            return;
        }
        
        tbody.innerHTML = channels.map((ch, i) => `
            <tr>
                <td>${i + 1}</td>
                <td class="font-mono">${ch.username || ch.channel_id}</td>
                <td><span class="badge badge-${getChannelStatusBadge(ch.status)}">${getChannelStatusText(ch.status)}</span></td>
                <td>${ch.comments_count || 0}</td>
                <td>${ch.deletions_count || 0}</td>
                <td>
                    <select class="form-input" style="width: auto; padding: 4px 8px;" onchange="setChannelStatus(${ch.id}, this.value)">
                        <option value="active" ${ch.status === 'active' ? 'selected' : ''}>✅ Активен</option>
                        <option value="sleep" ${ch.status === 'sleep' ? 'selected' : ''}>😴 Спячка</option>
                        <option value="disabled" ${ch.status === 'disabled' ? 'selected' : ''}>⛔ Отключён</option>
                    </select>
                </td>
            </tr>
        `).join('');
    }
}

function getChannelStatusBadge(status) {
    const badges = { 'active': 'success', 'sleep': 'warning', 'disabled': 'danger' };
    return badges[status] || 'muted';
}

function getChannelStatusText(status) {
    const texts = { 'active': '✅ Активен', 'sleep': '😴 Спячка', 'disabled': '⛔ Отключён' };
    return texts[status] || status;
}

async function setChannelStatus(id, status) {
    const result = await apiCall(`/channels/${id}/status`, 'POST', { status });
    
    if (result.success) {
        showNotification('success', 'Статус канала изменён');
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// PROXIES
// ─────────────────────────────────────────────────────────────────────────────────

async function loadProxies() {
    const result = await apiCall('/proxies');
    
    if (result.success) {
        const data = result.data;
        
        document.getElementById('proxy-comments-total').textContent = data.comments?.total || 0;
        document.getElementById('proxy-comments-ok').textContent = data.comments?.working || 0;
        document.getElementById('proxy-warmup-total').textContent = data.warmup?.total || 0;
        document.getElementById('proxy-warmup-ok').textContent = data.warmup?.working || 0;
    }
}

async function checkProxies(pool) {
    showNotification('info', `Проверка прокси (${pool})...`);
    
    const result = await apiCall('/proxies/check', 'POST', { pool });
    
    if (result.success) {
        const data = result.data;
        showNotification('success', `Проверено: ${data.ok} работают, ${data.fail} недоступны`);
        
        // Render results
        const container = document.getElementById('proxy-results');
        container.innerHTML = data.results.map((p, i) => `
            <div class="flex items-center justify-between" style="padding: 12px; border-bottom: 1px solid var(--border-primary);">
                <div class="flex items-center gap-3">
                    <span class="badge badge-${p.status === 'ok' ? 'success' : 'danger'}">#${i + 1}</span>
                    <span class="font-mono text-muted">${p.proxy || 'N/A'}</span>
                </div>
                <div>
                    ${p.status === 'ok' 
                        ? `<span class="text-success">✅ OK (${p.ping || 0}ms)</span>`
                        : `<span class="text-danger">❌ ${p.error || 'Failed'}</span>`
                    }
                </div>
            </div>
        `).join('');
        
        loadProxies();
    } else {
        showNotification('error', result.error || 'Ошибка проверки');
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// COMMENTS
// ─────────────────────────────────────────────────────────────────────────────────

async function loadComments() {
    const result = await apiCall('/comments');
    
    if (result.success) {
        const comments = result.data || [];
        const tbody = document.getElementById('comments-table');
        
        if (comments.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Нет комментариев</td></tr>';
            return;
        }
        
        tbody.innerHTML = comments.map(c => `
            <tr>
                <td class="text-muted">${new Date(c.created_at).toLocaleString('ru-RU')}</td>
                <td class="font-mono">${c.channel || 'N/A'}</td>
                <td>${c.text?.substring(0, 50) || 'N/A'}${c.text?.length > 50 ? '...' : ''}</td>
                <td><span class="badge badge-${c.status === 'deleted' ? 'danger' : 'success'}">${c.status}</span></td>
            </tr>
        `).join('');
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// SETTINGS
// ─────────────────────────────────────────────────────────────────────────────────

async function loadSettings() {
    const result = await apiCall('/settings');
    
    if (result.success) {
        const data = result.data;
        
        // Mode
        updateMode(data.mode);
        
        // Delays
        document.getElementById('delay-min').value = data.delays?.min || 30;
        document.getElementById('delay-max').value = data.delays?.max || 90;
        document.getElementById('read-min').value = data.delays?.read_min || 5;
        document.getElementById('read-max').value = data.delays?.read_max || 15;
        
        // Limits
        document.getElementById('limit-hour').value = data.limits?.hour || 10;
        document.getElementById('limit-day').value = data.limits?.day || 50;
        document.getElementById('probability').value = data.commenting?.probability_percent || 75;
        document.getElementById('probability-value').textContent = data.commenting?.probability_percent || 75;
        
        // GPT
        document.getElementById('gpt-model').value = data.gpt?.model || 'gpt-4o-mini';
        document.getElementById('gpt-temp').value = (data.gpt?.temperature || 0.9) * 100;
        document.getElementById('temp-value').textContent = data.gpt?.temperature || 0.9;
        document.getElementById('gpt-prompt').value = data.gpt?.prompt || '';
        
        // Monitor
        document.getElementById('monitor-interval').value = data.monitor?.delete_check_interval_sec || 60;
        document.getElementById('sanctions-sleep').value = data.sanctions?.sleep_after || 1;
        document.getElementById('sanctions-disable').value = data.sanctions?.disable_after || 3;
    }
}

async function saveSettings() {
    const settings = {
        delays: {
            min: parseInt(document.getElementById('delay-min').value),
            max: parseInt(document.getElementById('delay-max').value),
            read_min: parseInt(document.getElementById('read-min').value),
            read_max: parseInt(document.getElementById('read-max').value)
        },
        limits: {
            hour: parseInt(document.getElementById('limit-hour').value),
            day: parseInt(document.getElementById('limit-day').value)
        },
        commenting: {
            probability_percent: parseInt(document.getElementById('probability').value)
        },
        gpt: {
            model: document.getElementById('gpt-model').value,
            temperature: parseFloat(document.getElementById('gpt-temp').value) / 100,
            prompt: document.getElementById('gpt-prompt').value
        },
        monitor: {
            delete_check_interval_sec: parseInt(document.getElementById('monitor-interval').value)
        },
        sanctions: {
            sleep_after: parseInt(document.getElementById('sanctions-sleep').value),
            disable_after: parseInt(document.getElementById('sanctions-disable').value)
        }
    };
    
    const apiKey = document.getElementById('gpt-key').value;
    if (apiKey && apiKey.startsWith('sk-')) {
        settings.gpt.api_key = apiKey;
    }
    
    const result = await apiCall('/settings', 'POST', settings);
    
    if (result.success) {
        showNotification('success', 'Настройки сохранены');
    } else {
        showNotification('error', result.error || 'Ошибка сохранения');
    }
}

async function setMode(mode) {
    const result = await apiCall('/settings/mode', 'POST', { mode });
    
    if (result.success) {
        updateMode(mode);
        showNotification('success', `Режим изменён на ${mode}`);
    }
}

// ─────────────────────────────────────────────────────────────────────────────────
// NOTIFICATIONS
// ─────────────────────────────────────────────────────────────────────────────────

function showNotification(type, message, title = null) {
    const container = document.getElementById('notifications');
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    const titles = {
        success: 'Успешно',
        error: 'Ошибка',
        warning: 'Внимание',
        info: 'Информация'
    };
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${icons[type]}</span>
        <div class="notification-content">
            <div class="notification-title">${title || titles[type]}</div>
            <div class="notification-message">${message}</div>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// ─────────────────────────────────────────────────────────────────────────────────
// LOG FILTER
// ─────────────────────────────────────────────────────────────────────────────────

document.getElementById('log-filter')?.addEventListener('change', renderLogs);
