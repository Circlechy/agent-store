// ============ 环境感知配置 ============

// 打开环境配置弹窗
async function openEnvironmentModal() {
    document.getElementById('environment-modal').style.display = 'flex';
    await loadEnvironmentConfig();
    await loadEnvironmentAlerts();
}

// 关闭环境配置弹窗
async function closeEnvironmentModal() {
    await saveEnvironmentModalState();
    document.getElementById('environment-modal').style.display = 'none';
    await refreshEnvironmentAndState();
}

async function refreshEnvironmentAndState() {
    try {
        await loadEnvironmentConfig();
        await loadEnvironmentAlerts();
        const response = await fetch('/api/state');
        if (response.ok) {
            currentState = await response.json();
            updateAllUI({ preferState: true });
        }
    } catch (error) {
        console.error('刷新环境配置失败:', error);
    }
}

async function saveEnvironmentModalState() {
    try {
        const config = collectEnvironmentModalConfig();
        const response = await fetch('/api/environment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) return;
        const data = await response.json();
        if (data.success) {
            environmentConfig = data.config;
            updateEnvStatusButton(data.config);
            await loadEnvironmentAlerts();
            syncEnvironmentToUI(data.config);
            updateVehicleUI();
        }
    } catch (error) {
        console.error('保存环境配置失败:', error);
        showToast('保存失败: ' + error.message, 'error');
    }
}

function collectEnvironmentModalConfig() {
    const getNumber = (id, fallback = 0) => {
        const el = document.getElementById(id);
        if (!el) return fallback;
        const value = el.value;
        if (value === '' || value === null || value === undefined) return fallback;
        const num = Number(value);
        return Number.isFinite(num) ? num : fallback;
    };

    const getChecked = (id, fallback = false) => {
        const el = document.getElementById(id);
        return el ? !!el.checked : fallback;
    };

    const getValue = (id, fallback = '') => {
        const el = document.getElementById(id);
        return el ? (el.value || fallback) : fallback;
    };

    const userLocations = {};
    const locationsContainer = document.getElementById('env-locations-list');
    if (locationsContainer) {
        const rows = locationsContainer.querySelectorAll('.env-location-row');
        rows.forEach(row => {
            const nameInput = row.querySelector('.env-location-name');
            const addressInput = row.querySelector('.env-location-address');
            const name = (nameInput?.value || '').trim();
            const address = (addressInput?.value || '').trim();
            if (name) {
                userLocations[name] = address || null;
            }
        });
    }

    return {
        enabled: getChecked('env-enabled', true),
        weather: {
            condition: getValue('env-weather-condition', 'sunny'),
            temperature: getNumber('env-weather-temp', 20),
            humidity: getNumber('env-weather-humidity', 50),
            air_quality_index: getNumber('env-weather-aqi', 50),
            visibility: getNumber('env-weather-visibility', 10)
        },
        vehicle: {
            battery: {
                level_percent: getNumber('env-battery-level', 80),
                range_km: getNumber('env-battery-range', 320),
                low_battery_warning: getChecked('env-battery-warning', false)
            },
            tire_pressure: {
                front_left: getNumber('env-tire-fl', 2.4),
                front_right: getNumber('env-tire-fr', 2.4),
                rear_left: getNumber('env-tire-rl', 2.4),
                rear_right: getNumber('env-tire-rr', 2.4),
                warning: getChecked('env-tire-warning', false)
            },
            engine_oil: {
                quality: getValue('env-oil-quality', '良好'),
                next_change_km: getNumber('env-oil-next', 5000)
            },
            washer_fluid: {
                level_percent: getNumber('env-washer', 80)
            },
            lights: {
                taillight_right: getValue('env-taillight-rr', '正常')
            }
        },
        safety: {
            seatbelt_driver: getChecked('env-seatbelt-driver', true),
            seatbelt_passenger: getChecked('env-seatbelt-passenger', true),
            door_ajar: getChecked('env-door-ajar', false)
        },
        road_conditions: {
            surface: getValue('env-road-surface', 'dry'),
            congestion_level: getValue('env-road-congestion', 'free'),
            speed_camera_ahead: getChecked('env-speed-camera', false)
        },
        user_locations: userLocations
    };
}

// 加载环境配置
async function loadEnvironmentConfig() {
    try {
        const response = await fetch('/api/environment');
        const config = await response.json();
        environmentConfig = config;
        
        if (config.enabled !== undefined) {
            document.getElementById('env-enabled').checked = config.enabled;
        }
        
        // 天气配置
        if (config.weather) {
            const w = config.weather;
            if (w.condition) document.getElementById('env-weather-condition').value = w.condition;
            if (w.temperature !== undefined) document.getElementById('env-weather-temp').value = w.temperature;
            if (w.humidity !== undefined) {
                document.getElementById('env-weather-humidity').value = w.humidity;
                document.getElementById('humidity-value').textContent = w.humidity + '%';
            }
            if (w.air_quality_index !== undefined) document.getElementById('env-weather-aqi').value = w.air_quality_index;
            if (w.visibility !== undefined) document.getElementById('env-weather-visibility').value = w.visibility;
        }
        
        // 车辆配置 - 电池
        if (config.vehicle?.battery) {
            const b = config.vehicle.battery;
            if (b.level_percent !== undefined) {
                document.getElementById('env-battery-level').value = b.level_percent;
                document.getElementById('battery-level-value').textContent = b.level_percent + '%';
            }
            if (b.range_km !== undefined) document.getElementById('env-battery-range').value = b.range_km;
            if (b.low_battery_warning !== undefined) document.getElementById('env-battery-warning').checked = b.low_battery_warning;
        }
        
        // 车辆配置 - 胎压
        if (config.vehicle?.tire_pressure) {
            const t = config.vehicle.tire_pressure;
            if (t.front_left !== undefined) document.getElementById('env-tire-fl').value = t.front_left;
            if (t.front_right !== undefined) document.getElementById('env-tire-fr').value = t.front_right;
            if (t.rear_left !== undefined) document.getElementById('env-tire-rl').value = t.rear_left;
            if (t.rear_right !== undefined) document.getElementById('env-tire-rr').value = t.rear_right;
            if (t.warning !== undefined) document.getElementById('env-tire-warning').checked = t.warning;
        }
        
        // 车辆配置 - 机油
        if (config.vehicle?.engine_oil) {
            const o = config.vehicle.engine_oil;
            if (o.quality) document.getElementById('env-oil-quality').value = o.quality;
            if (o.next_change_km !== undefined) document.getElementById('env-oil-next').value = o.next_change_km;
        }
        
        // 车辆配置 - 玻璃水
        if (config.vehicle?.washer_fluid) {
            const wf = config.vehicle.washer_fluid;
            if (wf.level_percent !== undefined) {
                document.getElementById('env-washer').value = wf.level_percent;
                document.getElementById('washer-value').textContent = wf.level_percent + '%';
            }
        }
        
        // 车辆配置 - 车灯
        if (config.vehicle?.lights) {
            const l = config.vehicle.lights;
            if (l.taillight_right) document.getElementById('env-taillight-rr').value = l.taillight_right;
        }
        
        // 安全配置
        if (config.safety) {
            const s = config.safety;
            if (s.seatbelt_driver !== undefined) document.getElementById('env-seatbelt-driver').checked = s.seatbelt_driver;
            if (s.seatbelt_passenger !== undefined) document.getElementById('env-seatbelt-passenger').checked = s.seatbelt_passenger;
            if (s.door_ajar !== undefined) document.getElementById('env-door-ajar').checked = s.door_ajar;
        }
        
        // 道路配置
        if (config.road_conditions) {
            const r = config.road_conditions;
            if (r.surface) document.getElementById('env-road-surface').value = r.surface;
            if (r.congestion_level) document.getElementById('env-road-congestion').value = r.congestion_level;
            if (r.speed_camera_ahead !== undefined) document.getElementById('env-speed-camera').checked = r.speed_camera_ahead;
        }

        // 常用地点配置
        renderUserLocations(config.user_locations || {});
        
        // 更新底部状态按钮
        updateEnvStatusButton(config);
        
    } catch (error) {
        console.error('加载环境配置失败:', error);
    }
}

// 加载环境提醒
async function loadEnvironmentAlerts() {
    try {
        const response = await fetch('/api/environment/alerts');
        const data = await response.json();
        
        const alertsList = document.getElementById('env-alerts-list');
        const alertCount = document.getElementById('alert-count');
        const alertBadge = document.getElementById('env-alert-badge');
        
        alertCount.textContent = data.count;
        
        if (data.count > 0) {
            alertBadge.textContent = data.count;
            alertBadge.style.display = 'flex';
        } else {
            alertBadge.style.display = 'none';
        }
        
        if (data.alerts && data.alerts.length > 0) {
            const severityIcons = {
                'critical': '🚨',
                'warning': '⚠️',
                'info': '💡',
                'suggestion': '🌟'
            };
            
            alertsList.innerHTML = data.alerts.map(alert => `
                <div class="alert-item ${alert.severity}">
                    <span class="alert-icon">${severityIcons[alert.severity] || '📢'}</span>
                    <div class="alert-content">
                        <div class="alert-title">${alert.title}</div>
                        <div class="alert-message">${alert.message}</div>
                    </div>
                </div>
            `).join('');
        } else {
            alertsList.innerHTML = `
                <div class="no-alerts">
                    <div class="emoji">✅</div>
                    <div>一切正常，无需提醒</div>
                </div>
            `;
        }
    } catch (error) {
        console.error('加载环境提醒失败:', error);
    }
}

// 更新底部环境状态按钮
function updateEnvStatusButton(config) {
    const statusText = document.getElementById('env-status-text');
    const envIcon = document.querySelector('.env-config-btn .env-icon');
    
    if (!config || !config.enabled) {
        statusText.textContent = '已禁用';
        envIcon.textContent = '⚙️';
        return;
    }
    
    // 根据天气设置图标
    const weatherIcons = {
        'sunny': '☀️',
        'cloudy': '⛅',
        'overcast': '☁️',
        'rainy': '🌧️',
        'heavy_rain': '⛈️',
        'thunderstorm': '🌩️',
        'snowy': '🌨️',
        'foggy': '🌫️',
        'hazy': '😷'
    };
    
    const condition = config.weather?.condition || 'sunny';
    envIcon.textContent = weatherIcons[condition] || '🌤️';
    
    // 显示温度
    const temp = config.weather?.temperature;
    if (temp !== undefined) {
        statusText.textContent = `${temp}°C`;
    } else {
        statusText.textContent = '正常';
    }
}

function renderUserLocations(locations) {
    const container = document.getElementById('env-locations-list');
    if (!container) return;
    container.innerHTML = '';
    const entries = Object.entries(locations || {}).filter(([_, value]) => value !== null && value !== undefined);
    if (entries.length === 0) {
        addUserLocationRow();
        return;
    }
    entries.forEach(([name, info]) => {
        let address = '';
        if (typeof info === 'string') {
            address = info;
        } else if (info && typeof info === 'object') {
            address = info.address || info.name || '';
        }
        addUserLocationRow(name, address);
    });
}

function addUserLocationRow(name = '', address = '') {
    const container = document.getElementById('env-locations-list');
    if (!container) return;
    const row = document.createElement('div');
    row.className = 'env-row env-location-row';
    row.dataset.name = name || '';
    row.innerHTML = `
        <input type="text" class="env-location-input env-location-name" placeholder="如：家/公司" value="${name}">
        <input type="text" class="env-location-input env-location-address" placeholder="地点名称或地址" value="${address}">
        <button class="env-location-remove" type="button">删除</button>
    `;
    const nameInput = row.querySelector('.env-location-name');
    const addressInput = row.querySelector('.env-location-address');
    const removeBtn = row.querySelector('.env-location-remove');

    const handleChange = () => handleUserLocationRowChange(row);
    nameInput.addEventListener('change', handleChange);
    addressInput.addEventListener('change', handleChange);
    nameInput.addEventListener('blur', handleChange);
    addressInput.addEventListener('blur', handleChange);

    removeBtn.addEventListener('click', async () => {
        const currentName = (nameInput.value || row.dataset.name || '').trim();
        if (currentName) {
            await updateEnvConfig('user_locations', currentName, null);
        }
        row.remove();
    });

    container.appendChild(row);
}

async function handleUserLocationRowChange(row) {
    const nameInput = row.querySelector('.env-location-name');
    const addressInput = row.querySelector('.env-location-address');
    if (!nameInput || !addressInput) return;
    const newName = nameInput.value.trim();
    const address = addressInput.value.trim();
    const oldName = (row.dataset.name || '').trim();

    if (!newName) {
        if (oldName) {
            await updateEnvConfig('user_locations', oldName, null);
            row.dataset.name = '';
        }
        return;
    }

    if (oldName && oldName !== newName) {
        await updateEnvConfig('user_locations', oldName, null);
    }

    if (address) {
        await updateEnvConfig('user_locations', newName, address);
    } else {
        await updateEnvConfig('user_locations', newName, null);
    }
    row.dataset.name = newName;
}

// 更新环境配置
async function updateEnvConfig(path, key, value) {
    try {
        // 构建更新对象
        let updates = {};
        if (!path) {
            updates = { [key]: value };
        } else {
            const pathParts = path.split('.');
            if (pathParts.length === 1) {
                updates[path] = { [key]: value };
            } else if (pathParts.length === 2) {
                updates[pathParts[0]] = { [pathParts[1]]: { [key]: value } };
            }
        }
        
        const response = await fetch('/api/environment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        
        const data = await response.json();
        
        if (data.success) {
            environmentConfig = data.config;
            updateEnvStatusButton(data.config);
            // 重新加载提醒
            await loadEnvironmentAlerts();
            
            // 同步到车辆状态显示
            syncEnvironmentToUI(data.config);
            
            // 更新车辆UI（确保电量、里程等显示正确）
            updateVehicleUI();
        }
    } catch (error) {
        console.error('更新环境配置失败:', error);
        showToast('更新失败: ' + error.message, 'error');
    }
}

// 切换环境感知开关
async function toggleEnvironment() {
    const enabled = document.getElementById('env-enabled').checked;
    await updateEnvConfig('', 'enabled', enabled);
}

// 切换配置区块折叠
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const header = section.previousElementSibling;
    
    section.classList.toggle('collapsed');
    header.classList.toggle('collapsed');
}

// 重置环境配置到默认值
async function resetEnvironmentConfig() {
    if (!confirm('确定要重置所有环境配置到默认值吗？')) return;
    
    try {
        const defaultConfig = {
            enabled: true,
            weather: {
                condition: 'sunny',
                temperature: 20,
                humidity: 50,
                air_quality_index: 50,
                visibility: 10
            },
            vehicle: {
                battery: {
                    level_percent: 80,
                    range_km: 320,
                    low_battery_warning: false
                },
                tire_pressure: {
                    front_left: 2.4,
                    front_right: 2.4,
                    rear_left: 2.4,
                    rear_right: 2.4,
                    warning: false
                },
                engine_oil: {
                    quality: '良好',
                    next_change_km: 5000
                },
                washer_fluid: {
                    level_percent: 80
                },
                lights: {
                    taillight_right: '正常'
                }
            },
            safety: {
                seatbelt_driver: true,
                seatbelt_passenger: true,
                door_ajar: false
            },
            road_conditions: {
                surface: 'dry',
                congestion_level: 'free',
                speed_camera_ahead: false
            }
        };
        
        const response = await fetch('/api/environment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(defaultConfig)
        });
        
        if (response.ok) {
            showToast('配置已重置', 'success');
            await loadEnvironmentConfig();
            await loadEnvironmentAlerts();
            // 更新车辆UI（确保电量、里程等显示正确）
            updateVehicleUI();
        }
    } catch (error) {
        showToast('重置失败: ' + error.message, 'error');
    }
}

// 同步环境配置到UI组件
function syncEnvironmentToUI(config) {
    if (!config || !config.enabled) return;
    
    // 同步电池显示
    if (config.vehicle?.battery) {
        const batteryLevel = config.vehicle.battery.level_percent;
        const rangeKm = config.vehicle.battery.range_km;
        
        const batteryEl = document.getElementById('battery-level');
        const rangeEl = document.getElementById('range-km');
        
        if (batteryEl && batteryLevel !== undefined) {
            batteryEl.textContent = batteryLevel + '%';
        }
        if (rangeEl && rangeKm !== undefined) {
            rangeEl.textContent = rangeKm + 'km';
        }
    }
    
    // 同步胎压显示
    if (config.vehicle?.tire_pressure) {
        const tp = config.vehicle.tire_pressure;
        
        // 更新车辆俯视图上的胎压标签
        if (tp.front_left !== undefined) {
            const el = document.getElementById('tire-value-fl');
            if (el) el.textContent = tp.front_left.toFixed(1);
        }
        if (tp.front_right !== undefined) {
            const el = document.getElementById('tire-value-fr');
            if (el) el.textContent = tp.front_right.toFixed(1);
        }
        if (tp.rear_left !== undefined) {
            const el = document.getElementById('tire-value-rl');
            if (el) el.textContent = tp.rear_left.toFixed(1);
        }
        if (tp.rear_right !== undefined) {
            const el = document.getElementById('tire-value-rr');
            if (el) el.textContent = tp.rear_right.toFixed(1);
        }
        
        // 更新底部胎压显示
        const avgPressure = ((tp.front_left || 2.4) + (tp.front_right || 2.4) + 
                           (tp.rear_left || 2.4) + (tp.rear_right || 2.4)) / 4;
        const tpDisplay = document.getElementById('tire-pressure-display');
        if (tpDisplay) {
            tpDisplay.textContent = avgPressure.toFixed(1) + 'bar';
        }
        
        // 高亮异常胎压
        const minPressure = tp.normal_range_min || 2.2;
        const maxPressure = tp.normal_range_max || 2.6;
        
        ['fl', 'fr', 'rl', 'rr'].forEach(pos => {
            const key = {fl: 'front_left', fr: 'front_right', rl: 'rear_left', rr: 'rear_right'}[pos];
            const pressure = tp[key];
            const label = document.getElementById(`tire-label-${pos}`);
            if (label && pressure !== undefined) {
                if (pressure < minPressure || pressure > maxPressure) {
                    label.classList.add('warning');
                } else {
                    label.classList.remove('warning');
                }
            }
        });
    }
}

// 页面加载时初始化环境配置
async function initEnvironment() {
    try {
        const response = await fetch('/api/environment');
        const config = await response.json();
        environmentConfig = config;
        updateEnvStatusButton(config);
        
        // 加载提醒数量
        const alertsResponse = await fetch('/api/environment/alerts');
        const alertsData = await alertsResponse.json();
        const alertBadge = document.getElementById('env-alert-badge');
        if (alertsData.count > 0) {
            alertBadge.textContent = alertsData.count;
            alertBadge.style.display = 'flex';
        }
        
        // 同步到UI - 使用环境配置更新车辆状态显示
        syncEnvironmentToUI(config);
        
        // 🔥 重要：环境配置加载后重新更新车辆UI，确保电量、里程等显示正确
        updateVehicleUI();
        
        console.log('[环境配置] 已加载并同步到UI', config.enabled ? '(已启用)' : '(已禁用)');
    } catch (error) {
        console.error('初始化环境配置失败:', error);
    }
}

// 在 DOMContentLoaded 事件中调用
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initEnvironment, 1000); // 延迟1秒，确保其他组件已加载

    const clearChatModal = document.getElementById('clear-chat-modal');
    if (clearChatModal) {
        clearChatModal.addEventListener('click', (event) => {
            if (event.target === clearChatModal) {
                closeClearChatModal();
            }
        });
    }
});
