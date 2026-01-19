// ============ UI更新 ============

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('ws-status');
    const dot = statusEl.querySelector('.dot');
    const text = statusEl.querySelector('.text');
    
    if (connected) {
        dot.className = 'dot connected';
        text.textContent = '已连接';
    } else {
        dot.className = 'dot disconnected';
        text.textContent = '未连接';
    }
}

function updateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('current-time').textContent = timeStr;
}

function updateTtsToggleUI(status) {
    const button = document.getElementById('tts-toggle');
    if (!button) return;
    if (!status) {
        button.classList.remove('enabled', 'disabled');
        button.querySelector('.tts-text').textContent = 'TTS: --';
        button.disabled = true;
        return;
    }

    const { enabled, available } = status;
    button.classList.remove('enabled', 'disabled');
    const effectiveAvailable = ttsPlaybackMode === 'server'
        ? available !== false
        : true;
    if (!effectiveAvailable) {
        button.classList.add('disabled');
        button.querySelector('.tts-text').textContent = 'TTS: 不可用';
        button.disabled = true;
        return;
    }

    button.disabled = false;
    button.classList.add(enabled ? 'enabled' : 'disabled');
    button.querySelector('.tts-text').textContent = `TTS: ${enabled ? '开' : '关'}`;
    if (!enabled && browserTtsAvailable) {
        window.speechSynthesis.cancel();
    }
}

async function fetchTtsStatus() {
    try {
        if (ttsPlaybackMode === 'browser' || ttsPlaybackMode === 'browser_audio') {
            ttsAutoEnabled = getBrowserTtsEnabledFromStorage();
            updateTtsToggleUI({ enabled: ttsAutoEnabled, available: true });
            return;
        }
        const response = await fetch('/api/tts/status');
        if (!response.ok) return;
        const data = await response.json();
        ttsAutoEnabled = !!data.enabled;
        updateTtsToggleUI(data);
    } catch (error) {}
}

async function setTtsEnabled(enabled) {
    try {
        ttsToggleBusy = true;
        if (ttsPlaybackMode === 'browser' || ttsPlaybackMode === 'browser_audio') {
            ttsAutoEnabled = !!enabled;
            setBrowserTtsEnabledToStorage(ttsAutoEnabled);
            updateTtsToggleUI({ enabled: ttsAutoEnabled, available: true });
            showToast(`TTS自动播报已${ttsAutoEnabled ? '开启' : '关闭'}`, 'success');
            if (!ttsAutoEnabled && browserTtsAvailable) {
                window.speechSynthesis.cancel();
            }
            return;
        }
        const response = await fetch('/api/tts/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        if (!response.ok) {
            showToast('TTS切换失败', 'error');
            return;
        }
        const data = await response.json();
        ttsAutoEnabled = !!data.tts_enabled;
        await fetchTtsStatus();
        showToast(`TTS自动播报已${ttsAutoEnabled ? '开启' : '关闭'}`, 'success');
        if (!ttsAutoEnabled && browserTtsAvailable) {
            window.speechSynthesis.cancel();
        }
    } catch (error) {
        showToast('TTS切换失败', 'error');
    } finally {
        ttsToggleBusy = false;
    }
}

function truncateForTts(text, maxLength = 200) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    let cutPoint = text.lastIndexOf('。', maxLength);
    if (cutPoint === -1) {
        cutPoint = text.lastIndexOf('，', maxLength);
    }
    if (cutPoint === -1) {
        cutPoint = maxLength;
    }
    return text.slice(0, cutPoint + 1);
}

function speakInBrowser(text) {
    if (!browserTtsAvailable) return false;
    const cleaned = (text || '').replace(/\s+/g, ' ').trim();
    if (!cleaned) return false;
    const utterance = new SpeechSynthesisUtterance(cleaned);
    utterance.lang = 'zh-CN';
    const voices = window.speechSynthesis.getVoices();
    const zhVoice = voices.find(v => (v.lang || '').toLowerCase().startsWith('zh'));
    if (zhVoice) {
        utterance.voice = zhVoice;
    }
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return true;
}

function maybeSpeakAssistant(text) {
    if (!ttsAutoEnabled) return;
    if (ttsPlaybackMode !== 'browser') return;
    const speechText = truncateForTts(text, 200);
    speakInBrowser(speechText);
}

function playAudioBase64(audioBase64, mimeType = 'audio/mpeg') {
    if (!audioBase64) return false;
    try {
        const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
        audio.play();
        return true;
    } catch (e) {
        console.warn('播放音频失败:', e);
        return false;
    }
}

function initTtsPlaybackMode() {
    const select = document.getElementById('tts-playback-select');
    if (!select) return;
    ttsPlaybackMode = normalizeTtsPlaybackMode(ttsPlaybackMode);
    const browserOption = select.querySelector('option[value="browser"]');
    if (!browserTtsAvailable && browserOption) {
        browserOption.disabled = true;
        if (ttsPlaybackMode === 'browser') {
            ttsPlaybackMode = 'browser_audio';
        }
    }
    select.value = ttsPlaybackMode;
    localStorage.setItem('ttsPlaybackMode', ttsPlaybackMode);

    select.addEventListener('change', () => {
        ttsPlaybackMode = normalizeTtsPlaybackMode(select.value);
        localStorage.setItem('ttsPlaybackMode', ttsPlaybackMode);
        if (ttsPlaybackMode === 'browser' || ttsPlaybackMode === 'browser_audio') {
            ttsAutoEnabled = getBrowserTtsEnabledFromStorage();
            updateTtsToggleUI({ enabled: ttsAutoEnabled, available: true });
        } else {
            fetchTtsStatus();
            if (browserTtsAvailable) {
                window.speechSynthesis.cancel();
            }
        }
    });
}

function initTtsToggle() {
    const button = document.getElementById('tts-toggle');
    if (!button) return;
    button.addEventListener('click', () => {
        if (ttsToggleBusy) return;
        const nextValue = ttsAutoEnabled === null ? true : !ttsAutoEnabled;
        setTtsEnabled(nextValue);
    });
    fetchTtsStatus();
}

function updateAllUI(options = {}) {
    updateACUI();
    updateWindowsUI();
    updateSeatsUI();
    updateLightsUI();
    updateMediaUI();
    updateVehicleUI(options);
    updateNavigationUI();
    updateQuickInfo();
    updateMapFromState();
}

function updateComponentUI(component, options = {}) {
    switch (component) {
        case 'ac': updateACUI(); break;
        case 'windows': updateWindowsUI(); break;
        case 'seats': updateSeatsUI(); break;
        case 'lights': updateLightsUI(); break;
        case 'media': updateMediaUI(); break;
        case 'vehicle': updateVehicleUI(options); break;
        case 'navigation': updateNavigationUI(); break;
    }
    updateQuickInfo();
}

function updateQuickInfo() {
    const ac = currentState.ac;
    const lights = currentState.lights;
    const media = currentState.media;

    document.getElementById('quick-temp').textContent = `${ac.temperature || 24}°C`;
    document.getElementById('quick-light').textContent = lights.power ? '开启' : '关闭';
    document.getElementById('quick-music').textContent = media.playing ? '播放中' : '未播放';
}

function updateTirePressureInVisual(pressures) {
    // 更新车辆可视化中每个轮胎的胎压显示（外部标签）
    const tireLabels = {
        'fl': document.getElementById('tire-label-fl'),
        'fr': document.getElementById('tire-label-fr'),
        'rl': document.getElementById('tire-label-rl'),
        'rr': document.getElementById('tire-label-rr')
    };
    
    const tireValues = {
        'fl': document.getElementById('tire-value-fl'),
        'fr': document.getElementById('tire-value-fr'),
        'rl': document.getElementById('tire-value-rl'),
        'rr': document.getElementById('tire-value-rr')
    };
    
    const wheelGroups = {
        'fl': document.getElementById('wheel-front-left'),
        'fr': document.getElementById('wheel-front-right'),
        'rl': document.getElementById('wheel-rear-left'),
        'rr': document.getElementById('wheel-rear-right')
    };
    
    // 正常范围：2.2-2.6 bar
    const NORMAL_MIN = 2.2;
    const NORMAL_MAX = 2.6;
    
    // 更新每个轮胎的显示
    ['fl', 'fr', 'rl', 'rr'].forEach((tire, index) => {
        const pressure = pressures[index] || 2.4;
        const label = tireLabels[tire];
        const valueElement = tireValues[tire];
        const wheelGroup = wheelGroups[tire];
        
        // 更新胎压数值（如果不在编辑状态）
        if (valueElement) {
            const isEditing = label && label.classList.contains('editing');
            if (!isEditing) {
                valueElement.textContent = pressure.toFixed(1);
            }
        }
        
        // 更新状态样式（即使正在编辑也要更新状态，这样取消编辑时状态是正确的）
        if (label) {
            // 移除所有状态类
            label.classList.remove('tire-low', 'tire-high', 'tire-normal');
            
            // 根据胎压状态设置样式
            if (pressure < NORMAL_MIN) {
                // 胎压过低 - 红色
                label.classList.add('tire-low');
                if (wheelGroup) {
                    wheelGroup.classList.add('tire-low');
                    wheelGroup.classList.remove('tire-high', 'tire-normal');
                }
            } else if (pressure > NORMAL_MAX) {
                // 胎压过高 - 橙色
                label.classList.add('tire-high');
                if (wheelGroup) {
                    wheelGroup.classList.add('tire-high');
                    wheelGroup.classList.remove('tire-low', 'tire-normal');
                }
            } else {
                // 胎压正常 - 青色
                label.classList.add('tire-normal');
                if (wheelGroup) {
                    wheelGroup.classList.add('tire-normal');
                    wheelGroup.classList.remove('tire-low', 'tire-high');
                }
            }
        }
    });
}

function updateACUI() {
    const ac = currentState.ac;
    document.getElementById('ac-power').checked = ac.power;
    const tempElement = document.getElementById('ac-temp');
    tempElement.textContent = ac.temperature || 24;
    
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === ac.mode);
    });
    
    document.querySelectorAll('.speed-level').forEach(level => {
        level.classList.toggle('active', parseInt(level.dataset.level) <= (ac.fan_speed || 0));
    });
    
    // 更新内循环和空气净化按钮状态
    const internalCirculation = document.getElementById('ac-internal-circulation');
    const airPurification = document.getElementById('ac-air-purification');
    if (internalCirculation) {
        internalCirculation.classList.toggle('active', ac.internal_circulation || false);
    }
    if (airPurification) {
        airPurification.classList.toggle('active', ac.air_purification || false);
    }
    
    // 根据模式设置温度数字和风速颜色
    const mode = ac.mode || 'auto';
    let color, shadowColor;
    
    if (mode === 'cool') {
        // 制冷：柔和蓝色
        color = '#6bb3ff';
        shadowColor = '#6bb3ff';
    } else if (mode === 'heat') {
        // 制热：柔和红色
        color = '#ff7777';
        shadowColor = '#ff7777';
    } else {
        // 自动：柔和绿色
        color = '#66cc99';
        shadowColor = '#66cc99';
    }
    
    // 设置温度数字颜色
    tempElement.style.color = color;
    tempElement.style.textShadow = `0 0 30px ${shadowColor}`;
    
    // 设置风速级别颜色
    document.querySelectorAll('.speed-level.active').forEach(level => {
        level.style.background = color;
        level.style.borderColor = color;
        level.style.boxShadow = `0 0 15px ${shadowColor}`;
    });
    
    // 重置非激活状态的风速级别样式
    document.querySelectorAll('.speed-level:not(.active)').forEach(level => {
        level.style.background = '';
        level.style.borderColor = '';
        level.style.boxShadow = '';
    });
    
    // 设置模式按钮颜色
    document.querySelectorAll('.mode-btn').forEach(btn => {
        const btnMode = btn.dataset.mode;
        let btnColor, btnShadow;
        
        if (btnMode === 'cool') {
            btnColor = '#6bb3ff';
            btnShadow = '#6bb3ff';
        } else if (btnMode === 'heat') {
            btnColor = '#ff7777';
            btnShadow = '#ff7777';
        } else {
            btnColor = '#66cc99';
            btnShadow = '#66cc99';
        }
        
        if (btn.classList.contains('active')) {
            // 激活状态：使用对应模式的颜色
            btn.style.background = `linear-gradient(135deg, ${btnColor}, ${btnColor}dd)`;
            btn.style.borderColor = 'transparent';
            btn.style.color = 'white';
            btn.style.boxShadow = `0 0 15px ${btnShadow}`;
        } else {
            // 非激活状态：重置为默认样式
            btn.style.background = '';
            btn.style.borderColor = '';
            btn.style.color = '';
            btn.style.boxShadow = '';
        }
    });
}

function updateWindowsUI() {
    const windows = currentState.windows;
    const windowMap = {
        'window-fl': 'front_left', 'window-fr': 'front_right',
        'window-rl': 'rear_left', 'window-rr': 'rear_right'
    };
    
    Object.entries(windowMap).forEach(([elId, key]) => {
        const group = document.getElementById(`${elId}-group`);
        const mask = document.getElementById(`${elId}-mask`);
        const label = document.getElementById(`label-${elId.split('-')[1]}`);
        const value = windows[key] || 0;
        
        if (group) {
            group.classList.toggle('open', value > 50);
            group.classList.toggle('half', value > 0 && value <= 50);
        }
        if (mask) {
            mask.style.transform = `scaleY(${1 - value / 100})`;
            mask.style.transformOrigin = 'bottom';
        }
        if (label) {
            label.querySelector('.percent').textContent = `${value}%`;
        }
    });
    
    const sunroof = document.getElementById('sunroof-glass');
    const sunLabel = document.getElementById('label-sun');
    const sunValue = windows.sunroof || 0;
    
    if (sunroof) sunroof.classList.toggle('open', sunValue > 0);
    if (sunLabel) sunLabel.querySelector('.percent').textContent = `${sunValue}%`;
}

function updateSeatsUI() {
    const seats = currentState.seats;
    
    const indicators = [
        { id: 'seat-driver-heat', value: seats.driver_heating || 0 },
        { id: 'seat-driver-vent', value: seats.driver_ventilation || 0 },
        { id: 'seat-driver-massage', value: seats.driver_massage },
        { id: 'seat-passenger-heat', value: seats.passenger_heating || 0 },
        { id: 'seat-passenger-vent', value: seats.passenger_ventilation || 0 },
        { id: 'seat-passenger-massage', value: seats.passenger_massage },
    ];
    
    indicators.forEach(ind => {
        const el = document.getElementById(ind.id);
        if (el) {
            const isActive = typeof ind.value === 'boolean' ? ind.value : ind.value > 0;
            el.classList.toggle('active', isActive);
            el.style.opacity = isActive ? '1' : '0.2';
        }
    });
    
    // 如果控制面板已打开，更新其显示
    if (currentSelectedSeat) {
        updateSeatControlPanel(currentSelectedSeat);
    }
}

function updateLightsUI() {
    const lights = currentState.lights;
    
    document.getElementById('light-power').checked = lights.power;
    document.getElementById('light-color').value = lights.color || '#0066ff';
    document.getElementById('light-brightness').value = lights.brightness || 50;
    document.getElementById('light-brightness-value').textContent = `${lights.brightness || 50}%`;
    
    const preview = document.getElementById('light-color-preview');
    preview.style.background = lights.color || '#0066ff';
    preview.style.boxShadow = lights.power ? `0 0 20px ${lights.color || '#0066ff'}` : 'none';
    
    const glow = document.getElementById('ambient-glow');
    glow.classList.toggle('active', lights.power);
    glow.style.setProperty('--ambient-color', lights.color || '#0066ff');
    
    glow.classList.remove('breathing', 'rhythm');
    if (lights.power && lights.mode && lights.mode !== 'static') {
        glow.classList.add(lights.mode);
    }
    
    document.querySelectorAll('.light-mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === (lights.mode || 'static'));
    });
}

function updateMediaUI() {
    const media = currentState.media;
    
    document.getElementById('track-name').textContent = media.track_name || '未播放';
    document.getElementById('track-artist').textContent = media.track_artist || '--';
    document.getElementById('media-volume').value = media.volume || 50;
    document.getElementById('media-volume-value').textContent = media.volume || 50;
    
    const playBtn = document.getElementById('play-btn');
    const playIcon = playBtn.querySelector('.play-icon');
    const pauseIcon = playBtn.querySelector('.pause-icon');
    
    if (media.playing) {
        playIcon.style.display = 'none';
        pauseIcon.style.display = 'block';
    } else {
        playIcon.style.display = 'block';
        pauseIcon.style.display = 'none';
    }
    
    const vinyl = document.getElementById('vinyl-disc');
    vinyl.classList.toggle('spinning', media.playing);
    
    if (media.track_duration > 0) {
        const progress = (media.track_position || 0) / media.track_duration * 100;
        document.getElementById('progress-fill').style.width = `${progress}%`;
    }
}

function updateProgress() {
    const media = currentState.media;
    if (media.playing && media.track_duration > 0) {
        media.track_position = (media.track_position || 0) + 1;
        if (media.track_position >= media.track_duration) {
            media.track_position = 0;
        }
        const progress = media.track_position / media.track_duration * 100;
        document.getElementById('progress-fill').style.width = `${progress}%`;
    }
}

function updateVehicleUI(options = {}) {
    const vehicle = currentState.vehicle;
    const preferState = !!options.preferState;
    
    // 车辆显示统一使用车机状态，避免与配置界面分叉
    let batteryLevel = vehicle.battery_level || 80;
    let rangeKm = vehicle.range_km || 320;
    
    document.getElementById('battery-level').textContent = `${batteryLevel}%`;
    document.getElementById('range-km').textContent = `${rangeKm}km`;
    
    // 更新胎压显示
    let pressures = vehicle.tire_pressure || [2.4, 2.4, 2.4, 2.4];
    // 确保有4个值
    while (pressures.length < 4) {
        pressures.push(2.4);
    }
    
    // 更新底部状态栏的胎压显示（如果存在）
    const tirePressureDisplay = document.getElementById('tire-pressure-display');
    const tirePressureItem = document.getElementById('tire-pressure-item');
    if (tirePressureDisplay && tirePressureItem) {
        // 计算平均胎压
        const avgPressure = (pressures[0] + pressures[1] + pressures[2] + pressures[3]) / 4;
        
        // 检查是否有异常胎压（低于2.2或高于2.6）
        const hasLow = pressures.some(p => p < 2.2);
        const hasHigh = pressures.some(p => p > 2.6);
        
        // 显示格式：平均胎压，如果有异常则显示详细信息
        if (hasLow || hasHigh) {
            const tireNames = ['左前', '右前', '左后', '右后'];
            const abnormalTires = [];
            pressures.forEach((p, i) => {
                if (p < 2.2) {
                    abnormalTires.push(`${tireNames[i]}${p.toFixed(1)}↓`);
                } else if (p > 2.6) {
                    abnormalTires.push(`${tireNames[i]}${p.toFixed(1)}↑`);
                }
            });
            tirePressureDisplay.textContent = `${avgPressure.toFixed(1)}bar (${abnormalTires.join(',')})`;
            tirePressureItem.classList.add('warning');
        } else {
            tirePressureDisplay.textContent = `${avgPressure.toFixed(1)}bar`;
            tirePressureItem.classList.remove('warning');
        }
        
        // 设置详细提示
        const details = `左前:${pressures[0].toFixed(1)}bar 右前:${pressures[1].toFixed(1)}bar 左后:${pressures[2].toFixed(1)}bar 右后:${pressures[3].toFixed(1)}bar`;
        tirePressureItem.setAttribute('title', `胎压状态 - ${details}`);
    }
    
    // 更新车辆可视化中的胎压显示（始终更新）
    updateTirePressureInVisual(pressures);
    
    // 更新当前位置输入框（只在输入框为空或未聚焦时更新）
    const locationInput = document.getElementById('current-location-input');
    if (locationInput && vehicle.current_location_name) {
        if (document.activeElement !== locationInput && (preferState || !locationInput.value)) {
            locationInput.value = vehicle.current_location_name;
        }
    }
    
    // 同步更新地图
    updateMapFromState();

    // 同步环境配置弹窗中的车辆数据
    if (typeof syncVehicleStateToEnvironmentModal === 'function') {
        syncVehicleStateToEnvironmentModal(vehicle);
    }
}

function updateNavigationUI() {
    const nav = currentState.navigation;
    const navStatus = document.getElementById('nav-status');
    const navText = document.getElementById('nav-text');
    
    if (nav && nav.active && nav.destination) {
        navStatus.classList.add('active');
        // 如果有途经点，显示途经点信息
        let navInfo = `前往 ${nav.destination}`;
        if (nav.waypoints && nav.waypoints.length > 0) {
            const waypointNames = nav.waypoints.map(wp => wp.name || '途经点').join(' → ');
            navInfo = `途经 ${waypointNames} → ${nav.destination}`;
        }
        navText.textContent = `${navInfo} · ${nav.eta_minutes || 0}分钟`;
    } else {
        navStatus.classList.remove('active');
        navText.textContent = '导航未启动';
    }
    
    // 同步更新地图
    updateMapFromState();
}
