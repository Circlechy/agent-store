<template>
  <div :class="['message-wrapper', message.role]">
    <div class="avatar">
      <div class="avatar-icon">
        {{ message.role === 'assistant' ? 'AI' : 'Me' }}
      </div>
    </div>
    <div class="message-content-container">
      <div class="message-meta">
        <span class="role-name">{{ roleLabel }}</span>
        <span class="time">{{ formattedTimestamp }}</span>
      </div>
      <!-- 传统消息显示 -->
      <div v-if="!hasAgentMessages" class="message-bubble">
        <div class="content">
          <div v-if="message.imageUrl" class="image-content">
            <img :src="message.imageUrl" class="message-image" alt="用户上传的图片" />
          </div>
          <div class="text-content" v-if="message.content || $slots.content">
            <slot name="content">{{ message.content }}</slot>
          </div>
        </div>
      </div>

      <!-- 代理消息列表显示 -->
      <div v-else class="agent-messages-container">
        <div class="agents-header">
          <h4>🤖 AI 推理过程</h4>
          <span class="agents-count">{{ agentMessages.length }} 个步骤</span>
        </div>
        <div class="agent-messages-list">
          <AgentMessage
            v-for="agentMsg in agentMessages"
            :key="agentMsg.id"
            :message="agentMsg"
            @copy="handleCopy"
          />
          
          <!-- 显示正在运行的中间节点 -->
          <slot name="intermediate-loading"></slot>
          
          <!-- 显示并发的信息收集任务 -->
          <slot name="concurrent-tasks"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, unref } from "vue";
import { NButton, NCard } from "naive-ui";

import AgentMessage from "./AgentMessage.vue";
import { formatJSON, formatTimestamp } from "../utils/formatter.js";

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['copy']);

const formattedTimestamp = computed(() =>
  formatTimestamp(props.message.timestamp || "")
);

const roleLabel = computed(() => {
  // 如果有 agent，显示 agent 标签；否则显示角色标签
  if (props.message.agent && props.message.agentLabel) {
    return props.message.agentLabel;
  }
  return props.message.role === "assistant" ? "闺点子" : "用户";
});

const bubbleClass = computed(() =>
  props.message.role === "assistant" ? "assistant" : "user"
);

// 代理消息相关 - 使用 unref 确保响应式
const agentMessages = computed(() => {
  const am = props.message.agentMessages;
  return unref(am) || [];
});

const hasAgentMessages = computed(() => {
  const am = agentMessages.value;
  return Array.isArray(am) && am.length > 0;
});

// 处理复制事件
const handleCopy = (message) => {
  emit('copy', message);
};
</script>

<style scoped>
.message-wrapper {
  display: flex;
  gap: 1rem;
  width: 100%;
}

.message-wrapper.user {
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
  margin-top: 1.5rem;
}

.avatar-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.75rem;
}

.assistant .avatar-icon {
  background: var(--primary-light);
  color: var(--primary-color);
}

.user .avatar-icon {
  background: var(--primary-color);
  color: white;
}

.message-content-container {
  display: flex;
  flex-direction: column;
  max-width: 80%;
  gap: 0.35rem;
}

.user .message-content-container {
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.25rem;
}

.role-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.time {
  font-size: 0.7rem;
  color: #cbd5e1;
}

.message-bubble {
  padding: 1rem 1.25rem;
  border-radius: 18px;
  position: relative;
  box-shadow: var(--shadow-sm);
}

.assistant .message-bubble {
  background: white;
  color: var(--text-main);
  border-top-left-radius: 4px;
  border: 1px solid var(--border-color);
}

.user .message-bubble {
  background: var(--primary-color);
  color: white;
  border-top-right-radius: 4px;
}

.text-content {
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 0.9375rem;
}

.image-content {
  margin-bottom: 0.5rem;
}

.image-content:last-child {
  margin-bottom: 0;
}

.message-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  display: block;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 代理消息容器样式 */
.agent-messages-container {
  margin-top: 0.5rem;
}

.agents-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.agents-header h4 {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.agents-count {
  font-size: 0.75rem;
  color: #64748b;
  background: white;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.agent-messages-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
