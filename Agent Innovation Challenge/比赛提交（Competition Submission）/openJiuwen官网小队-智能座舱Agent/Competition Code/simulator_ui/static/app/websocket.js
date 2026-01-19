// ============ WebSocket ============

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        updateConnectionStatus(true);
        reconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
    };
    
    ws.onclose = () => {
        updateConnectionStatus(false);
        if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            setTimeout(initWebSocket, 2000 * reconnectAttempts);
        }
    };
    
    ws.onerror = () => {};
}

function handleMessage(message) {
    if (message.type === 'full_state') {
        currentState = message.state;
        updateAllUI({ preferState: true });
    } else if (message.type === 'state_update') {
        currentState[message.component] = message.state;
        updateComponentUI(message.component, { preferState: message.component === 'vehicle' });
    }
}
