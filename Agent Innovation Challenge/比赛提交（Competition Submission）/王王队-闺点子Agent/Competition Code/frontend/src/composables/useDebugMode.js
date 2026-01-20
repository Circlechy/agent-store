import { ref } from "vue";

import config from "../config/app.config.js";

const storageKey = config.storageKeys.debugMode;
const isBrowser = typeof window !== "undefined";

export function useDebugMode() {
  const isDebugMode = ref(false);
  const debugLogs = ref([]);

  const loadState = () => {
    if (!isBrowser) {
      return;
    }
    const raw = window.localStorage.getItem(storageKey);
    if (raw === "true") {
      isDebugMode.value = true;
    }
  };

  const saveState = () => {
    if (!isBrowser) {
      return;
    }
    window.localStorage.setItem(storageKey, isDebugMode.value ? "true" : "false");
  };

  const toggleDebugMode = () => {
    isDebugMode.value = !isDebugMode.value;
    saveState();
  };

  let logIdCounter = 0;

  const addLog = (type, message, data = null) => {
    logIdCounter += 1;
    debugLogs.value.push({
      id: `${Date.now()}-${logIdCounter}`,
      timestamp: new Date().toISOString(),
      type,
      message,
      data
    });
    if (debugLogs.value.length > 100) {
      debugLogs.value.shift();
    }
  };

  const clearLogs = () => {
    debugLogs.value = [];
  };

  loadState();

  return {
    isDebugMode,
    debugLogs,
    toggleDebugMode,
    addLog,
    clearLogs
  };
}
