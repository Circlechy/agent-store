const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  apiVersion: "v1",
  sse: {
    reconnectInterval: 3000,
    maxReconnectAttempts: 3
  },
  validation: {
    minQueryLength: 1,
    maxQueryLength: 500,
    forbiddenChars: /[<>"']/g
  },
  storageKeys: {
    chatHistory: "deepsearch_chat_history",
    debugMode: "deepsearch_debug_mode"
  }
};

export default config;
