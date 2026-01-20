<template>
  <div class="agent-message-wrapper">
    <div class="agent-header">
      <div class="agent-info">
        <div v-if="!message.isComplete" class="active-dot-wrapper">
          <div class="active-dot"></div>
        </div>
        <span class="agent-label">{{ agentLabel }}</span>
        <span class="message-time">{{ formattedTimestamp }}</span>
      </div>
      <div class="header-right">
        <div v-if="!message.isComplete" class="status-text">处理中...</div>
        <div v-if="showDuration" class="message-duration">
          <span class="duration-icon">⏱️</span>
          <span class="duration-text">{{ formattedDuration }}</span>
        </div>
      </div>
    </div>

    <div class="agent-content">
      <!-- 主要内容区域 -->
      <div class="content-main">
        <div class="text-content">
          <div class="formatted-text">
            {{ formattedContent }}<span v-if="!message.isComplete" class="typing-cursor">|</span>
          </div>
        </div>
      </div>

      <!-- 操作区域 -->
      <div v-if="hasActions" class="content-actions">
        <NButton
          size="small"
          secondary
          @click="copyContent"
        >
          复制内容
        </NButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { NButton } from "naive-ui";
import { formatTimestamp } from "../utils/formatter.js";

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
});

const emit = defineEmits(['copy']);

// 计算属性
const agentLabel = computed(() => props.message.agentLabel || props.message.agent);
const formattedTimestamp = computed(() =>
  formatTimestamp(props.message.timestamp || "")
);

const showDuration = computed(() =>
  props.message.duration && props.message.duration > 0
);

const formattedDuration = computed(() => {
  if (!props.message.duration) return '';
  const duration = props.message.duration;
  if (duration < 1000) return `${duration}ms`;
  return `${(duration / 1000).toFixed(2)}s`;
});

const isJsonContent = computed(() => {
  try {
    JSON.parse(props.message.content);
    return true;
  } catch {
    return false;
  }
});

const formattedJson = computed(() => {
  if (!isJsonContent.value) return props.message.content;
  try {
    return JSON.stringify(JSON.parse(props.message.content), null, 2);
  } catch {
    return props.message.content;
  }
});

const formattedContent = computed(() => {
  if (isJsonContent.value) {
    try {
      const parsed = JSON.parse(props.message.content);
      // 对于JSON内容，显示简化的预览
      if (parsed.title && parsed.thought) {
        return `📝 ${parsed.title}\n💭 ${parsed.thought}`;
      }
      if (parsed.results && Array.isArray(parsed.results)) {
        return `📊 找到 ${parsed.results.length} 个结果`;
      }
      return `📄 ${typeof parsed}`;
    } catch {
      return props.message.content;
    }
  }
  return props.message.content;
});

const hasActions = computed(() => {
  return props.message.content;
});

// 方法
const copyContent = () => {
  const content = props.message.content;

  navigator.clipboard.writeText(content).then(() => {
    emit('copy', '内容已复制到剪贴板');
  }).catch(() => {
    emit('copy', '复制失败');
  });
};
</script>

<style scoped>
.agent-message-wrapper {
  margin: 0.75rem 0;
  padding: 0.875rem;
  background: white;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid var(--bg-color);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.active-dot-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
}

.active-dot {
  width: 8px;
  height: 8px;
  background-color: var(--primary-color);
  border-radius: 50%;
  animation: pulse 1.5s infinite ease-in-out;
}

@keyframes pulse {
  0% { transform: scale(0.8); opacity: 0.5; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.8); opacity: 0.5; }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-text {
  font-size: 0.75rem;
  color: var(--primary-color);
  font-weight: 500;
}

.agent-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.message-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.message-duration {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.duration-icon {
  font-size: 0.875rem;
}

.agent-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.content-main {
  min-height: 2rem;
}

.json-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem;
  background: var(--bg-color);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.json-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.json-icon {
  font-size: 1rem;
}

.json-text {
  font-size: 0.875rem;
  color: var(--text-main);
  font-weight: 500;
}

.text-content {
  line-height: 1.6;
  color: var(--text-main);
}

.formatted-text {
  white-space: pre-wrap;
  font-size: 0.875rem;
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  color: var(--primary-color);
  font-weight: bold;
  margin-left: 2px;
  animation: blink 0.8s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.content-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  padding-top: 0.375rem;
  border-top: 1px solid var(--bg-color);
}

/* 不同代理类型的特殊样式 */
.agent-message-wrapper[data-agent="planner"] {
  border-left: 4px solid var(--primary-color);
}

.agent-message-wrapper[data-agent="tool_select"] {
  border-left: 4px solid var(--primary-color);
}

.agent-message-wrapper[data-agent="answerability"] {
  border-left: 4px solid var(--primary-color);
}

.agent-message-wrapper[data-agent="summarize_findings"] {
  border-left: 4px solid var(--primary-color);
}

.agent-message-wrapper[data-agent="answer"] {
  border-left: 4px solid var(--primary-color);
  background: white;
}

/* 最终答案的特殊样式 */
.agent-message-wrapper[data-agent="answer"] .agent-label {
  color: var(--primary-color);
  font-weight: 700;
}

.agent-message-wrapper[data-agent="answer"] .text-content {
  font-size: 1rem;
  line-height: 1.7;
}
</style>