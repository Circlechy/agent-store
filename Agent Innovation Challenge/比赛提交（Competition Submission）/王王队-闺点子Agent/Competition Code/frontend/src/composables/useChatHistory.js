import { ref, watch } from "vue";

import config from "../config/app.config.js";

const storageKey = config.storageKeys.chatHistory;

const isBrowser = typeof window !== "undefined";

// 将 messages 定义在外部，实现简单的单例模式，确保数据一致性
const globalMessages = ref([]);

export function useChatHistory() {
  const messages = globalMessages;

  const loadFromStorage = () => {
    if (!isBrowser) {
      return;
    }
    const payload = window.localStorage.getItem(storageKey);
    if (!payload) {
      return;
    }
    try {
      messages.value = JSON.parse(payload);
    } catch (error) {
      messages.value = [];
    }
  };

  const saveToStorage = () => {
    if (!isBrowser) {
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(messages.value));
  };

  // 深度监听消息变化，自动持久化
  watch(messages, () => {
    saveToStorage();
  }, { deep: true });

  const addMessage = (role, content, rawData = null, agentMessages = null, agent = null, imageUrl = null) => {
    const message = {
      id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      role,
      content,
      timestamp: new Date().toISOString(),
      rawData,
      imageUrl
    };
    
    // 如果提供了 agent，添加到消息中（用于 entry、planner、answer 等顶级消息）
    if (agent) {
      message.agent = agent;
    }
    
    // 如果提供了 agentMessages，添加到消息中（用于显示多个子消息）
    if (agentMessages !== null) {
      message.agentMessages = Array.isArray(agentMessages) ? [...agentMessages] : [...(agentMessages.value || [])];
    }
    
    messages.value.push(message);
    // watch 会处理 saveToStorage
    return message;
  };

  const clearMessages = () => {
    messages.value = [];
    if (isBrowser) {
      window.localStorage.removeItem(storageKey);
    }
  };

  const replaceLastAssistantMessage = (content, rawData, agentMessages = null) => {
    const lastIndex = [...messages.value].reverse().findIndex((item) => item.role === "assistant");
    if (lastIndex === -1) {
      const message = addMessage("assistant", content || "", rawData || []);
      if (agentMessages !== null) {
        message.agentMessages = Array.isArray(agentMessages) ? [...agentMessages] : [...(agentMessages.value || [])];
      }
      return message;
    }
    
    // 找到真实索引
    const realIndex = messages.value.length - 1 - lastIndex;
    const last = messages.value[realIndex];
    
    // 创建新对象以触发响应式更新
    const updated = {
      ...last,
      content: content !== null ? content : last.content,
      rawData: rawData !== null ? rawData : last.rawData,
      agentMessages: agentMessages !== null 
        ? (Array.isArray(agentMessages) ? [...agentMessages] : [...(agentMessages.value || [])])
        : last.agentMessages
    };
    
    // 替换整个消息对象
    messages.value[realIndex] = updated;
    // 强制触发数组的响应式更新
    messages.value = [...messages.value];
    return updated;
  };

  // 初始加载
  if (messages.value.length === 0) {
    loadFromStorage();
  }

  return {
    messages,
    addMessage,
    clearMessages,
    replaceLastAssistantMessage,
    loadFromStorage,
    saveToStorage
  };
}
