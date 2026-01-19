// ============ 当前位置管理 ============

function handleLocationKeypress(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        setCurrentLocationByAddress();
    }
}

async function setCurrentLocationByAddress() {
    const input = document.getElementById('current-location-input');
    const address = input.value.trim();
    
    if (!address) {
        showToast('请输入当前位置', 'info');
        return;
    }
    
    const btn = document.querySelector('.location-set-btn');
    btn.disabled = true;
    
    try {
        // 调用后端API，后端会进行地理编码
        const response = await fetch('/api/location/geocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ address: address })
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`📍 当前位置: ${data.location_name}`, 'success');
            input.value = data.location_name;
            
            // 如果后端返回了导航更新信息
            if (data.navigation_updated && data.navigation) {
                currentState.navigation.eta_minutes = data.navigation.eta_minutes;
                currentState.navigation.distance_km = data.navigation.distance_km;
                updateNavigationUI();
                updateMapInfoPanel();
                showToast(`🧭 导航已更新: ${data.navigation.distance_km}km, ${data.navigation.eta_minutes}分钟`, 'info');
            }
        } else {
            showToast('设置位置失败: ' + (data.error || '未知错误'), 'error');
        }
    } catch (error) {
        showToast('设置位置失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function loadCurrentLocation() {
    try {
        const response = await fetch('/api/location');
        const data = await response.json();
        
        if (data.success && data.current_location) {
            const input = document.getElementById('current-location-input');
            if (input && data.current_location.name) {
                input.value = data.current_location.name;
            }
        }
    } catch (error) {
        console.error('加载当前位置失败:', error);
    }
}
