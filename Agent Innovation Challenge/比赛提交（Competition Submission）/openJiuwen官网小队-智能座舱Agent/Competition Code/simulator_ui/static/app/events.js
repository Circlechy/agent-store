// ============ 事件监听 ============

function initEventListeners() {
    // 空调
    document.getElementById('ac-power').addEventListener('change', e => sendUpdate('ac', { power: e.target.checked }));
    document.getElementById('temp-minus').addEventListener('click', () => {
        sendUpdate('ac', { temperature: Math.max(16, (currentState.ac.temperature || 24) - 1) });
    });
    document.getElementById('temp-plus').addEventListener('click', () => {
        sendUpdate('ac', { temperature: Math.min(30, (currentState.ac.temperature || 24) + 1) });
    });
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => sendUpdate('ac', { mode: btn.dataset.mode }));
    });
    document.querySelectorAll('.speed-level').forEach(level => {
        level.addEventListener('click', () => sendUpdate('ac', { fan_speed: parseInt(level.dataset.level) }));
    });
    // 内循环和空气净化按钮
    document.getElementById('ac-internal-circulation').addEventListener('click', () => {
        const newState = !currentState.ac.internal_circulation;
        currentState.ac.internal_circulation = newState;
        updateACUI();
        sendUpdate('ac', { internal_circulation: newState });
    });
    document.getElementById('ac-air-purification').addEventListener('click', () => {
        const newState = !currentState.ac.air_purification;
        currentState.ac.air_purification = newState;
        updateACUI();
        sendUpdate('ac', { air_purification: newState });
    });
    
    // 氛围灯
    document.getElementById('light-power').addEventListener('change', e => sendUpdate('lights', { power: e.target.checked }));
    document.getElementById('light-color').addEventListener('input', e => sendUpdate('lights', { color: e.target.value, power: true }));
    document.querySelectorAll('.color-dot').forEach(dot => {
        dot.addEventListener('click', () => sendUpdate('lights', { color: dot.dataset.color, power: true }));
    });
    document.getElementById('light-brightness').addEventListener('input', e => {
        document.getElementById('light-brightness-value').textContent = `${e.target.value}%`;
        sendUpdate('lights', { brightness: parseInt(e.target.value) });
    });
    document.querySelectorAll('.light-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => sendUpdate('lights', { mode: btn.dataset.mode, power: true }));
    });
    
    // 媒体
    document.getElementById('play-btn').addEventListener('click', () => {
        const newPlaying = !currentState.media.playing;
        currentState.media.playing = newPlaying;
        updateMediaUI();
        sendUpdate('media', { playing: newPlaying });
    });
    document.getElementById('prev-btn').addEventListener('click', () => {
        fetch('/api/state/media', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'prev' })
        }).then(r => r.json()).then(data => {
            if (data.success && data.state) {
                currentState.media = data.state;
                updateMediaUI();
                showToast(`播放: ${data.state.track_name}`, 'success');
            }
        });
    });
    document.getElementById('next-btn').addEventListener('click', () => {
        fetch('/api/state/media', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'next' })
        }).then(r => r.json()).then(data => {
            if (data.success && data.state) {
                currentState.media = data.state;
                updateMediaUI();
                showToast(`播放: ${data.state.track_name}`, 'success');
            }
        });
    });
    document.getElementById('media-volume').addEventListener('input', e => {
        document.getElementById('media-volume-value').textContent = e.target.value;
        sendUpdate('media', { volume: parseInt(e.target.value) });
    });
    
    // 场景
    document.querySelectorAll('.scene-btn').forEach(btn => {
        btn.addEventListener('click', () => activateScene(btn.dataset.scene));
    });

    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.addEventListener('click', event => {
            const step = event.target.closest('.tool-step');
            if (!step) return;
            showToolDetailModal(step);
        });
    }

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeToolDetailModal();
        }
    });
}

function sendUpdate(component, updates) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'update', component, updates }));
    }
}

function activateScene(sceneName) {
    showToast(`激活「${sceneName}」...`, 'info');
    
    const scenes = {
        '回家模式': { ac: { temperature: 24, mode: 'auto', power: true }, lights: { color: '#ffaa66', brightness: 40, power: true, mode: 'static' }, media: { playing: true, volume: 40 } },
        '上班模式': { ac: { temperature: 22, mode: 'cool', power: true, fan_speed: 3 }, lights: { color: '#ffffff', brightness: 70, power: true } },
        '送娃模式': { ac: { temperature: 25, mode: 'auto', power: true }, lights: { color: '#ffcc00', brightness: 60, power: true } },
        '约会模式': { ac: { temperature: 23, mode: 'auto', power: true }, lights: { color: '#ff66cc', brightness: 30, power: true, mode: 'breathing' }, media: { playing: true, volume: 35 } },
        '午休模式': { ac: { temperature: 25, fan_speed: 1, power: true }, lights: { power: false }, media: { playing: false } },
        '派对模式': { lights: { color: '#9900ff', brightness: 100, power: true, mode: 'rhythm' }, media: { playing: true, volume: 80 } }
    };
    
    const scene = scenes[sceneName];
    if (scene) {
        Object.entries(scene).forEach(([component, updates]) => sendUpdate(component, updates));
        setTimeout(() => showToast(`「${sceneName}」已激活`, 'success'), 500);
    }
}
