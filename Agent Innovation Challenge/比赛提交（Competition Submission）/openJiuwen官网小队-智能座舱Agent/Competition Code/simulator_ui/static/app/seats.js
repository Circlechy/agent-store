// ============ 座椅控制 ============

function selectSeat(seat) {
    currentSelectedSeat = seat;
    
    // 更新座椅SVG选中状态
    document.querySelectorAll('.seat-detail-group').forEach(g => {
        g.classList.remove('selected');
        // 重置文字颜色
        const text = g.querySelector('text');
        if (text) {
            text.setAttribute('fill', '#a0aec0');
        }
    });
    
    const selectedGroup = document.getElementById(`seat-${seat}-detail`);
    selectedGroup.classList.add('selected');
    
    // 高亮选中文字 - 彻底移除发光、描边和滤镜，确保清晰
    const selectedText = selectedGroup.querySelector('text');
    if (selectedText) {
        selectedText.setAttribute('fill', '#ffffff'); // 纯白文字
        selectedText.setAttribute('font-weight', '700');
        selectedText.style.filter = 'none';
        selectedText.style.stroke = 'none';
        selectedText.removeAttribute('stroke');
        selectedText.removeAttribute('stroke-width');
        selectedText.removeAttribute('paint-order');
    }
    
    // 更新乘客卡片选中状态
    document.querySelectorAll('.passenger-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    const cardId = seat === 'driver' ? 'driver-card' : 'passenger-card';
    const selectedCard = document.getElementById(cardId);
    if (selectedCard) {
        selectedCard.classList.add('selected');
    }
    
    // 更新当前值
    updateSeatControlPanel(seat);
}

function updateSeatControlPanel(seat) {
    const seats = currentState.seats;
    const heating = seats[`${seat}_heating`] || 0;
    const ventilation = seats[`${seat}_ventilation`] || 0;
    const massage = seats[`${seat}_massage`] || false;
    const massageMode = seats[`${seat}_massage_mode`] || 'wave';
    
    document.getElementById('heating-value').textContent = heating > 0 ? `${heating}档` : '0档';
    document.getElementById('ventilation-value').textContent = ventilation > 0 ? `${ventilation}档` : '0档';
    
    if (massage) {
        const modeNames = { wave: '波浪', pulse: '脉冲', knead: '揉捏' };
        document.getElementById('massage-value').textContent = modeNames[massageMode] || '开启';
    } else {
        document.getElementById('massage-value').textContent = '关闭';
    }
    
    // 更新按钮状态
    updateControlButtons('heating', heating);
    updateControlButtons('ventilation', ventilation);
    updateControlButtons('massage', massage ? massageMode : false);
}

function updateControlButtons(type, value) {
    let controlItem;
    if (type === 'massage') {
        controlItem = document.getElementById('massage-value').closest('.control-item');
    } else if (type === 'heating') {
        controlItem = document.getElementById('heating-value').closest('.control-item');
    } else {
        controlItem = document.getElementById('ventilation-value').closest('.control-item');
    }
    
    if (!controlItem) return;
    
    const buttons = controlItem.querySelectorAll('.control-btn');
    buttons.forEach((btn) => {
        if (type === 'massage') {
            if (btn.textContent === '关') {
                btn.classList.toggle('active', !value);
            } else {
                btn.classList.toggle('active', btn.textContent === (value === 'wave' ? '波浪' : value === 'pulse' ? '脉冲' : value === 'knead' ? '揉捏' : ''));
            }
        } else {
            const btnValue = btn.textContent === '关' ? 0 : parseInt(btn.textContent);
            btn.classList.toggle('active', btnValue === value);
        }
    });
}

function adjustSeatSetting(type, value) {
    if (!currentSelectedSeat) return;
    
    const settings = {};
    
    if (type === 'heating') {
        settings.heating = parseInt(value);
    } else if (type === 'ventilation') {
        settings.ventilation = parseInt(value);
    } else if (type === 'massage') {
        if (value === false) {
            settings.massage = false;
        } else {
            // value 是模式字符串：'wave', 'pulse', 'knead'
            settings.massage = true;
            settings.massage_mode = value;
        }
    }
    
    // 发送更新请求
    fetch('/api/state/seats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            seat: currentSelectedSeat,
            settings: settings
        })
    }).then(r => r.json()).then(data => {
        if (data.success) {
            // 重新加载状态（从服务器获取最新值）
            fetch('/api/state')
                .then(r => r.json())
                .then(newState => {
                    currentState = newState;
                    // 更新UI
                    updateSeatsUI();
                    updateSeatControlPanel(currentSelectedSeat);
                    let message = '';
                    if (type === 'heating') {
                        message = `加热已${value > 0 ? `设为${value}档` : '关闭'}`;
                    } else if (type === 'ventilation') {
                        message = `通风已${value > 0 ? `设为${value}档` : '关闭'}`;
                    } else {
                        if (value === false) {
                            message = '按摩已关闭';
                        } else {
                            const modeNames = { wave: '波浪', pulse: '脉冲', knead: '揉捏' };
                            message = `按摩已开启，模式：${modeNames[value] || value}`;
                        }
                    }
                    showToast(message, 'success');
                });
        } else {
            showToast(data.error || '设置失败', 'error');
        }
    }).catch(() => {
        showToast('网络错误', 'error');
    });
}

// 到达途经点
async function arriveAtWaypoint() {
    const nav = currentState.navigation;
    
    if (!nav.active || !nav.waypoints || nav.waypoints.length === 0) {
        showToast('当前没有途经点', 'info');
        return;
    }
    
    const nextWaypointName = nav.waypoints[0].name || '途经点';
    
    if (!confirm(`确认已到达 ${nextWaypointName}？系统将自动切换到下一个途经点或目的地。`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/navigation/arrive-waypoint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || '已切换到下一个途经点', 'success');
            
            // 刷新状态
            await pollState();
        } else {
            showToast('操作失败: ' + (data.error || '未知错误'), 'error');
        }
    } catch (error) {
        showToast('操作失败: ' + error.message, 'error');
    }
}
