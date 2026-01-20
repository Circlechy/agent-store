/**
 * 智能座舱模拟器 - 前端交互逻辑 v6
 * 支持多轮对话和上下文记忆
 */

// WebSocket连接
let ws = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 10;

// Leaflet 地图相关
let leafletMap = null;
let currentMarker = null;  // 当前位置标记
let destinationMarker = null;  // 目的地标记
let routePolyline = null;  // 路线
let waypointMarkers = [];  // 途经点标记数组

// ============ 坐标转换函数（百度 BD-09 → WGS84） ============
// 百度地图 API 返回 BD-09 坐标，Leaflet 使用 WGS84 坐标
// 转换公式：BD-09 → GCJ-02 → WGS84

const X_PI = Math.PI * 3000.0 / 180.0;
const PI = Math.PI;
const A = 6378245.0;
const EE = 0.00669342162296594323;

// BD-09 → GCJ-02
function bd09ToGcj02(bdLat, bdLng) {
    const x = bdLng - 0.0065;
    const y = bdLat - 0.006;
    const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * X_PI);
    const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * X_PI);
    const gcjLng = z * Math.cos(theta);
    const gcjLat = z * Math.sin(theta);
    return { lat: gcjLat, lng: gcjLng };
}

// GCJ-02 → WGS84
function gcj02ToWgs84(gcjLat, gcjLng) {
    if (outOfChina(gcjLat, gcjLng)) {
        return { lat: gcjLat, lng: gcjLng };
    }
    let dLat = transformLat(gcjLng - 105.0, gcjLat - 35.0);
    let dLng = transformLng(gcjLng - 105.0, gcjLat - 35.0);
    const radLat = gcjLat / 180.0 * PI;
    let magic = Math.sin(radLat);
    magic = 1 - EE * magic * magic;
    const sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180.0) / ((A * (1 - EE)) / (magic * sqrtMagic) * PI);
    dLng = (dLng * 180.0) / (A / sqrtMagic * Math.cos(radLat) * PI);
    return { lat: gcjLat - dLat, lng: gcjLng - dLng };
}

// BD-09 → WGS84（组合转换）
function bd09ToWgs84(bdLat, bdLng) {
    const gcj = bd09ToGcj02(bdLat, bdLng);
    return gcj02ToWgs84(gcj.lat, gcj.lng);
}

// WGS84 → GCJ-02
function wgs84ToGcj02(wgsLat, wgsLng) {
    if (outOfChina(wgsLat, wgsLng)) {
        return { lat: wgsLat, lng: wgsLng };
    }
    let dLat = transformLat(wgsLng - 105.0, wgsLat - 35.0);
    let dLng = transformLng(wgsLng - 105.0, wgsLat - 35.0);
    const radLat = wgsLat / 180.0 * PI;
    let magic = Math.sin(radLat);
    magic = 1 - EE * magic * magic;
    const sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180.0) / ((A * (1 - EE)) / (magic * sqrtMagic) * PI);
    dLng = (dLng * 180.0) / (A / sqrtMagic * Math.cos(radLat) * PI);
    return { lat: wgsLat + dLat, lng: wgsLng + dLng };
}

// GCJ-02 → BD-09
function gcj02ToBd09(gcjLat, gcjLng) {
    const z = Math.sqrt(gcjLng * gcjLng + gcjLat * gcjLat) + 0.00002 * Math.sin(gcjLat * X_PI);
    const theta = Math.atan2(gcjLat, gcjLng) + 0.000003 * Math.cos(gcjLng * X_PI);
    return { lat: z * Math.sin(theta) + 0.006, lng: z * Math.cos(theta) + 0.0065 };
}

// WGS84 → BD-09（Leaflet点击坐标转换为百度坐标）
function wgs84ToBd09(wgsLat, wgsLng) {
    const gcj = wgs84ToGcj02(wgsLat, wgsLng);
    return gcj02ToBd09(gcj.lat, gcj.lng);
}

function outOfChina(lat, lng) {
    return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
}

function transformLat(x, y) {
    let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
    ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
    return ret;
}

function transformLng(x, y) {
    let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
    ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * PI)) * 2.0 / 3.0;
    ret += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
    return ret;
}
// ============ 坐标转换函数结束 ============

// 当前状态缓存
let currentState = {
    ac: {}, windows: {}, seats: {}, lights: {},
    media: {}, vehicle: {}, navigation: {}, passengers: {}, cameras: {}
};

// 环境配置缓存（需在首次使用前初始化，避免 TDZ）
let environmentConfig = null;

// 乘客信息
let passengers = {
    driver: { id: null, name: '主驾驶员', avatar: null },
    passenger: { id: null, name: '副驾乘客', avatar: null }
};

// 当前编辑的座位
let currentEditingSeat = null;

// 当前选中的座椅
let currentSelectedSeat = null;

// 当前说话者
let currentSpeaker = 'driver';

// 当前附加的图片
let attachedImage = null;

// 当前附加的视频（临时上传ID）
let attachedVideoId = null;
let attachedVideoName = null;

// 会话ID - 从 localStorage 获取或生成新的，只有清空对话时才更换
let sessionId = localStorage.getItem('chatSessionId');
if (!sessionId) {
    sessionId = 'session_' + Date.now();
    localStorage.setItem('chatSessionId', sessionId);
}

// 工具追踪状态
let activeToolTrace = null;
let toolStepCounter = 0;
let toolDetailModal = null;
let activePlanTrace = null;

// TTS自动播报开关
let ttsAutoEnabled = null;
let ttsToggleBusy = false;
let browserTtsAvailable = typeof window !== 'undefined' && 'speechSynthesis' in window;
let ttsPlaybackMode = localStorage.getItem('ttsPlaybackMode') || 'browser_audio';

function normalizeTtsPlaybackMode(value) {
    if (value === 'server' || value === 'browser_audio') return value;
    return 'browser';
}

function getBrowserTtsEnabledFromStorage() {
    const stored = localStorage.getItem('ttsAutoEnabled');
    if (stored === null) return true;
    return stored === 'true';
}

function setBrowserTtsEnabledToStorage(enabled) {
    localStorage.setItem('ttsAutoEnabled', enabled ? 'true' : 'false');
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    initEventListeners();
    initChat();
    initAvatarUpload();
    initTtsPlaybackMode();
    initTtsToggle();
    
    updateTime();
    setInterval(updateTime, 1000);
    setInterval(pollState, 1000);
    setInterval(updateProgress, 1000);
    
    loadPassengerInfo();
    loadChatHistory();
    loadCurrentLocation(); // 加载当前位置
    updateChatTheme(); // 初始化主题色
    
    // 默认选中主驾驶
    setTimeout(() => {
        selectSeat('driver');
    }, 500);
});
