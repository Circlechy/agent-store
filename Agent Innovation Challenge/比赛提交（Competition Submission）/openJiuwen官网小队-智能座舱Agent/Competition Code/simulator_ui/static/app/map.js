// ============ Leaflet 地图 ============

// 地图初始化重试计数
let mapInitRetryCount = 0;
const MAX_MAP_INIT_RETRY = 20;

// 初始化 Leaflet 地图
function initLeafletMap() {
    console.log('[地图] 尝试初始化... (尝试次数:', mapInitRetryCount + 1, ')');
    
    // 检查 Leaflet 是否已加载
    if (typeof L === 'undefined') {
        console.warn('[地图] Leaflet 库尚未加载');
        if (mapInitRetryCount < MAX_MAP_INIT_RETRY) {
            mapInitRetryCount++;
            setTimeout(initLeafletMap, 300);
        } else {
            console.error('[地图] Leaflet 加载超时，请检查网络');
            showMapError('地图库加载失败，请检查网络连接');
        }
        return;
    }
    
    const mapContainer = document.getElementById('baidu-map-container');
    if (!mapContainer) {
        console.warn('[地图] 容器未找到');
        if (mapInitRetryCount < MAX_MAP_INIT_RETRY) {
            mapInitRetryCount++;
            setTimeout(initLeafletMap, 300);
        }
        return;
    }
    
    // 检查容器是否可见
    const rect = mapContainer.getBoundingClientRect();
    console.log('[地图] 容器尺寸:', rect.width, 'x', rect.height);
    
    if (rect.width < 50 || rect.height < 50) {
        console.warn('[地图] 容器尺寸过小，稍后重试');
        if (mapInitRetryCount < MAX_MAP_INIT_RETRY) {
            mapInitRetryCount++;
            setTimeout(initLeafletMap, 300);
        }
        return;
    }
    
    // 如果已经初始化，先销毁
    if (leafletMap) {
        try {
            leafletMap.remove();
        } catch (e) {}
        leafletMap = null;
    }
    
    try {
        console.log('[地图] 创建 Leaflet 实例...');
        
        // 创建地图实例，默认中心点为杭州
        leafletMap = L.map('baidu-map-container', {
            center: [30.2741, 120.1551],  // 杭州
            zoom: 12,
            zoomControl: false,
            attributionControl: true
        });
        
        // 使用多个备用瓦片源
        const tileLayers = [
            // 高德地图瓦片（国内最稳定）
            {
                url: 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
                options: { subdomains: '1234', maxZoom: 18 }
            },
            // OpenStreetMap
            {
                url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                options: { maxZoom: 19 }
            },
            // CartoDB Dark（暗色主题）
            {
                url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
                options: { subdomains: 'abcd', maxZoom: 19 }
            }
        ];
        
        // 使用高德地图瓦片（国内访问最稳定）
        const tileLayer = L.tileLayer(tileLayers[0].url, {
            ...tileLayers[0].options,
            attribution: '&copy; 高德地图'
        });
        
        tileLayer.on('tileerror', function(e) {
            console.warn('[地图] 瓦片加载失败:', e);
        });
        
        tileLayer.addTo(leafletMap);
        
        // 添加点击事件 - 模拟移动到该位置
        leafletMap.on('click', function(e) {
            console.log('[地图] 点击位置 (GCJ-02 高德瓦片):', e.latlng);
            // 将高德瓦片返回的 GCJ-02 坐标转换为 BD-09（百度坐标）发送给后端
            const bd = gcj02ToBd09(e.latlng.lat, e.latlng.lng);
            console.log('[地图] 转换为百度坐标 (BD-09):', bd.lat, bd.lng);
            simulateMoveToLocation(bd.lat, bd.lng);
        });
        
        // 强制刷新地图尺寸
        setTimeout(() => {
            leafletMap.invalidateSize();
            console.log('[地图] 尺寸已刷新');
        }, 100);
        
        console.log('[地图] ✓ Leaflet 地图初始化成功!');
        
        // 更新地图显示
        setTimeout(() => {
            updateMapFromState();
            // 再次刷新确保正确显示
            if (leafletMap) leafletMap.invalidateSize();
        }, 500);
        
    } catch (error) {
        console.error('[地图] 初始化失败:', error);
        showMapError('地图初始化失败: ' + error.message);
    }
}

// 显示地图错误信息
function showMapError(message) {
    const mapContainer = document.getElementById('baidu-map-container');
    if (mapContainer) {
        mapContainer.innerHTML = `
            <div style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #718096;
                text-align: center;
                padding: 20px;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">🗺️</div>
                <div style="font-size: 14px;">${message}</div>
                <button onclick="initLeafletMap()" style="
                    margin-top: 16px;
                    padding: 8px 16px;
                    background: #4299e1;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    cursor: pointer;
                ">重试</button>
            </div>
        `;
    }
}

// 页面加载完成后初始化地图
window.addEventListener('load', function() {
    console.log('[地图] 页面加载完成，开始初始化地图');
    setTimeout(initLeafletMap, 500);
});

// 更新地图显示
function updateMapFromState() {
    const vehicle = currentState.vehicle || {};
    const nav = currentState.navigation || {};
    
    // 先更新信息面板（即使地图未初始化）
    updateMapInfoPanel();
    
    if (!leafletMap) {
        return;
    }
    
    // 更新当前位置
    if (vehicle.current_location_coords) {
        const [lat, lng] = vehicle.current_location_coords.split(',').map(Number);
        if (!isNaN(lat) && !isNaN(lng)) {
            updateCurrentLocationMarker(lat, lng, vehicle.current_location_name);
        }
    }
    
    // 更新导航目的地和途经点
    if (nav.active && nav.destination_coords) {
        const [lat, lng] = nav.destination_coords.split(',').map(Number);
        if (!isNaN(lat) && !isNaN(lng)) {
            updateDestinationMarker(lat, lng, nav.destination);
            
            // 更新途经点标记
            updateWaypointMarkers(nav.waypoints || []);
            
            // 绘制路线（包含途经点和真实路线坐标）
            if (vehicle.current_location_coords) {
                drawRouteWithWaypoints(
                    vehicle.current_location_coords, 
                    nav.destination_coords, 
                    nav.waypoints || [],
                    nav.route_points || []  // 真实路线坐标点
                );
            }
        }
    } else {
        // 清除目的地标记和路线
        if (destinationMarker) {
            leafletMap.removeLayer(destinationMarker);
            destinationMarker = null;
        }
        if (routePolyline) {
            leafletMap.removeLayer(routePolyline);
            routePolyline = null;
        }
        // 清除途经点标记
        clearWaypointMarkers();
    }
}

// 当前位置/目的地图标（延迟初始化，避免 Leaflet 未加载）
let currentLocationIcon = null;
let destinationIcon = null;

function ensureMapIcons() {
    if (typeof L === 'undefined') {
        return false;
    }
    if (!currentLocationIcon) {
        currentLocationIcon = L.divIcon({
            className: 'current-location-marker',
            html: `<div style="
                width: 24px; height: 24px; 
                background: #0bc5ea; 
                border: 3px solid white; 
                border-radius: 50%; 
                box-shadow: 0 2px 8px rgba(11,197,234,0.5);
            "><div style="
                width: 8px; height: 8px; 
                background: white; 
                border-radius: 50%; 
                position: absolute; 
                top: 50%; left: 50%; 
                transform: translate(-50%, -50%);
            "></div></div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });
    }
    if (!destinationIcon) {
        destinationIcon = L.divIcon({
            className: 'destination-marker',
            html: `<div style="
                width: 32px; height: 40px;
                position: relative;
            ">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">
                    <path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 24 16 24s16-12 16-24C32 7.2 24.8 0 16 0z" fill="#fc8181"/>
                    <circle cx="16" cy="14" r="6" fill="white"/>
                </svg>
            </div>`,
            iconSize: [32, 40],
            iconAnchor: [16, 40]
        });
    }
    return true;
}

// 创建途经点图标（带序号）
function createWaypointIcon(index) {
    if (typeof L === 'undefined') {
        return null;
    }
    return L.divIcon({
        className: 'waypoint-marker',
        html: `<div style="
            width: 28px; height: 36px;
            position: relative;
        ">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
                <path d="M14 0C6.3 0 0 6.3 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.3 21.7 0 14 0z" fill="#f6ad55"/>
                <circle cx="14" cy="12" r="10" fill="white"/>
            </svg>
            <span style="
                position: absolute;
                top: 6px;
                left: 50%;
                transform: translateX(-50%);
                font-size: 12px;
                font-weight: bold;
                color: #f6ad55;
            ">${index + 1}</span>
        </div>`,
        iconSize: [28, 36],
        iconAnchor: [14, 36]
    });
}

// 更新当前位置标记
function updateCurrentLocationMarker(lat, lng, name, isBaiduCoords = true) {
    if (!leafletMap) return;
    if (!ensureMapIcons()) return;
    
    // 移除旧标记
    if (currentMarker) {
        leafletMap.removeLayer(currentMarker);
    }
    
    // 如果是百度坐标，转换为 GCJ-02 供高德瓦片显示
    let displayLat = lat, displayLng = lng;
    if (isBaiduCoords) {
        const gcj = bd09ToGcj02(lat, lng);
        displayLat = gcj.lat;
        displayLng = gcj.lng;
    }
    
    // 创建新标记
    currentMarker = L.marker([displayLat, displayLng], { icon: currentLocationIcon })
        .addTo(leafletMap)
        .bindTooltip(name || '当前位置', {
            permanent: false,
            direction: 'top',
            className: 'map-tooltip'
        });
}

// 更新目的地标记
function updateDestinationMarker(lat, lng, name, isBaiduCoords = true) {
    if (!leafletMap) return;
    if (!ensureMapIcons()) return;
    
    // 移除旧标记
    if (destinationMarker) {
        leafletMap.removeLayer(destinationMarker);
    }
    
    // 如果是百度坐标，转换为 GCJ-02 供高德瓦片显示
    let displayLat = lat, displayLng = lng;
    if (isBaiduCoords) {
        const gcj = bd09ToGcj02(lat, lng);
        displayLat = gcj.lat;
        displayLng = gcj.lng;
    }
    
    // 创建新标记
    destinationMarker = L.marker([displayLat, displayLng], { icon: destinationIcon })
        .addTo(leafletMap)
        .bindTooltip(name || '目的地', {
            permanent: false,
            direction: 'top',
            className: 'map-tooltip destination'
        });
}

// 绘制路线（简单版，无途经点）
function drawRoute(originCoords, destCoords) {
    drawRouteWithWaypoints(originCoords, destCoords, [], []);
}

// 绘制路线（支持途经点和真实路线坐标）
// routePoints: 真实路线坐标点数组 [[lat, lng], [lat, lng], ...]
function drawRouteWithWaypoints(originCoords, destCoords, waypoints, realRoutePoints) {
    if (!leafletMap) return;
    
    // 移除旧路线
    if (routePolyline) {
        leafletMap.removeLayer(routePolyline);
    }
    
    let routePoints = [];
    let isRealRoute = false;
    
    // 优先使用真实路线坐标点（街道级导航）
    if (realRoutePoints && realRoutePoints.length > 2) {
        // 转换百度坐标(BD-09)为GCJ-02供高德瓦片显示
        realRoutePoints.forEach(point => {
            if (Array.isArray(point) && point.length === 2) {
                const gcj = bd09ToGcj02(point[0], point[1]);
                routePoints.push([gcj.lat, gcj.lng]);
            }
        });
        isRealRoute = true;
        console.log(`使用真实路线坐标点绘制路线，共 ${routePoints.length} 个点（已转换为GCJ-02）`);
    } else {
        // 回退到直线连接（起点 -> 途经点 -> 终点）
        const [originLat, originLng] = originCoords.split(',').map(Number);
        const [destLat, destLng] = destCoords.split(',').map(Number);
        
        // 转换起点坐标（BD-09 → GCJ-02）
        const gcjOrigin = bd09ToGcj02(originLat, originLng);
        routePoints = [[gcjOrigin.lat, gcjOrigin.lng]];
        
        // 添加途经点（转换坐标）
        if (waypoints && waypoints.length > 0) {
            waypoints.forEach(wp => {
                if (wp.coords) {
                    const [wpLat, wpLng] = wp.coords.split(',').map(Number);
                    if (!isNaN(wpLat) && !isNaN(wpLng)) {
                        const gcjWp = bd09ToGcj02(wpLat, wpLng);
                        routePoints.push([gcjWp.lat, gcjWp.lng]);
                    }
                }
            });
        }
        
        // 添加终点（转换坐标）
        const gcjDest = bd09ToGcj02(destLat, destLng);
        routePoints.push([gcjDest.lat, gcjDest.lng]);
        console.log(`使用直线连接绘制路线，共 ${routePoints.length} 个点（已转换为GCJ-02）`);
    }
    
    // 绘制路线（真实路线用实线，直线用虚线）
    routePolyline = L.polyline(routePoints, {
        color: isRealRoute ? '#3b82f6' : '#4299e1',
        weight: isRealRoute ? 5 : 4,
        opacity: 0.85,
        dashArray: isRealRoute ? null : '10, 10'  // 真实路线用实线
    }).addTo(leafletMap);
    
    // 调整视野以显示整条路线
    leafletMap.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });
}

// 清除途经点标记
function clearWaypointMarkers() {
    if (!leafletMap) return;
    
    waypointMarkers.forEach(marker => {
        leafletMap.removeLayer(marker);
    });
    waypointMarkers = [];
}

// 更新途经点标记
function updateWaypointMarkers(waypoints) {
    if (!leafletMap) return;
    
    // 先清除旧的途经点标记
    clearWaypointMarkers();
    
    // 添加新的途经点标记
    if (waypoints && waypoints.length > 0) {
        waypoints.forEach((wp, index) => {
            if (wp.coords) {
                const [lat, lng] = wp.coords.split(',').map(Number);
                if (!isNaN(lat) && !isNaN(lng)) {
                    // 转换百度坐标(BD-09)为GCJ-02供高德瓦片显示
                    const gcj = bd09ToGcj02(lat, lng);
                    const marker = L.marker([gcj.lat, gcj.lng], { icon: createWaypointIcon(index) })
                        .addTo(leafletMap)
                        .bindTooltip(wp.name || `途经点${index + 1}`, {
                            permanent: false,
                            direction: 'top',
                            className: 'map-tooltip waypoint'
                        });
                    waypointMarkers.push(marker);
                }
            }
        });
    }
}

// 更新地图信息面板
function updateMapInfoPanel() {
    const vehicle = currentState.vehicle || {};
    const nav = currentState.navigation || {};
    
    const currentLocEl = document.getElementById('map-current-location');
    const destEl = document.getElementById('map-destination');
    const distEl = document.getElementById('map-distance');
    const etaEl = document.getElementById('map-eta');
    const arriveWaypointBtn = document.getElementById('arrive-waypoint-btn');
    
    if (currentLocEl) {
        currentLocEl.textContent = vehicle.current_location_name || '未设置';
    }
    if (destEl) {
        // 如果有途经点，显示途经点 → 目的地
        if (nav.active) {
            if (nav.waypoints && nav.waypoints.length > 0) {
                const waypointNames = nav.waypoints.map(wp => wp.name || '途经点').join(' → ');
                destEl.textContent = `${waypointNames} → ${nav.destination || '目的地'}`;
            } else {
                destEl.textContent = nav.destination || '未设置';
            }
        } else {
            destEl.textContent = '未设置';
        }
    }
    if (distEl) {
        distEl.textContent = nav.active && nav.distance_km ? `${nav.distance_km}km` : '--';
    }
    if (etaEl) {
        etaEl.textContent = nav.active && nav.eta_minutes ? `${nav.eta_minutes}分钟` : '--';
    }
    
    // 显示/隐藏"到达途经点"按钮（只在有途经点时显示）
    if (arriveWaypointBtn) {
        const hasWaypoints = nav.active && nav.waypoints && nav.waypoints.length > 0;
        arriveWaypointBtn.style.display = hasWaypoints ? 'inline-block' : 'none';
        if (hasWaypoints) {
            const nextWaypointName = nav.waypoints[0].name || '途经点';
            arriveWaypointBtn.title = `到达 ${nextWaypointName}`;
        }
    }
    
    // 高亮地图面板（如果正在导航）
    const mapPanel = document.getElementById('nav-map-panel');
    if (mapPanel) {
        mapPanel.classList.toggle('navigating', nav.active);
    }
}

// 模拟移动到某个位置
async function simulateMoveToLocation(lat, lng) {
    const coords = `${lat},${lng}`;
    
    try {
        // 先逆地理编码获取地址名称
        const response = await fetch('/api/location/reverse-geocode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coords: coords })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`📍 已移动到: ${data.location_name}`, 'success');
            
            // 更新输入框
            const input = document.getElementById('current-location-input');
            if (input) {
                input.value = data.location_name;
            }
            
            // 更新地图标记
            updateCurrentLocationMarker(lat, lng, data.location_name);
            
            // 更新状态
            currentState.vehicle.current_location_name = data.location_name;
            currentState.vehicle.current_location_coords = coords;
            
            // 如果后端返回了导航更新信息（包含重新计算的 route_points）
            if (data.navigation_updated && data.navigation) {
                currentState.navigation.eta_minutes = data.navigation.eta_minutes;
                currentState.navigation.distance_km = data.navigation.distance_km;
                // 更新 route_points（车道级导航）
                if (data.navigation.route_points) {
                    currentState.navigation.route_points = data.navigation.route_points;
                }
                showToast(`🧭 导航已更新: ${data.navigation.distance_km}km, ${data.navigation.eta_minutes}分钟`, 'info');
            }
            
            // 如果正在导航，使用 drawRouteWithWaypoints 重绘路线（保持车道级导航）
            const nav = currentState.navigation;
            if (nav && nav.active && nav.destination_coords) {
                drawRouteWithWaypoints(
                    coords, 
                    nav.destination_coords, 
                    nav.waypoints || [],
                    nav.route_points || []  // 使用后端重新计算后的 route_points
                );
            }
            
            updateMapInfoPanel();
        } else {
            // 即使没有地址名称，也更新位置
            const locationName = `位置(${lat.toFixed(4)},${lng.toFixed(4)})`;
            showToast(`📍 已移动到: ${locationName}`, 'success');
            updateCurrentLocationMarker(lat, lng, locationName);
        }
    } catch (error) {
        console.error('模拟移动失败:', error);
        showToast('移动失败: ' + error.message, 'error');
    }
}

// 地图控制函数
function zoomIn() {
    if (leafletMap) {
        leafletMap.zoomIn();
    }
}

function zoomOut() {
    if (leafletMap) {
        leafletMap.zoomOut();
    }
}

function centerOnCurrentLocation() {
    if (!leafletMap) return;
    
    const vehicle = currentState.vehicle || {};
    if (vehicle.current_location_coords) {
        const [lat, lng] = vehicle.current_location_coords.split(',').map(Number);
        // 转换百度坐标(BD-09)为GCJ-02供高德瓦片显示
        const gcj = bd09ToGcj02(lat, lng);
        leafletMap.panTo([gcj.lat, gcj.lng]);
        showToast('已定位到当前位置', 'info');
    } else {
        showToast('当前位置未设置', 'info');
    }
}

function toggleMapPanel() {
    const panel = document.getElementById('nav-map-panel');
    if (panel) {
        panel.classList.toggle('collapsed');
    }
}
