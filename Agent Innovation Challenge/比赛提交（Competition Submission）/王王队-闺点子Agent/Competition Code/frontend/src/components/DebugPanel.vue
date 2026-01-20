<template>
  <div v-if="visible" class="debug-panel">
    <div class="header">
      <div>
        <span class="title">调试模式</span>
        <span class="status">连接：{{ connectionState }} · 重连：{{ reconnectAttempts }}</span>
      </div>
      <div class="actions">
        <NButton size="tiny" ghost @click="clearLogs">清空日志</NButton>
        <NButton size="tiny" text @click="$emit('update:visible', false)">关闭</NButton>
      </div>
    </div>
    <div ref="logListRef" class="log-list">
      <div v-for="log in logs" :key="log.id" class="log-row">
        <div class="log-meta">
          <span class="log-type">{{ log.type }}</span>
          <span class="log-time">{{ log.timestamp }}</span>
        </div>
        <p class="log-message">{{ log.message }}</p>
        <pre v-if="log.data">{{ typeof log.data === 'object' ? JSON.stringify(log.data, null, 2) : log.data }}</pre>
      </div>
      <p v-if="!logs.length" class="empty">暂无调试日志</p>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";
import { NButton } from "naive-ui";

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  logs: {
    type: Array,
    default: () => []
  },
  connectionState: {
    type: String,
    default: "未连接"
  },
  reconnectAttempts: {
    type: Number,
    default: 0
  }
});

const emit = defineEmits(["clear", "update:visible"]);

const logListRef = ref(null);

watch(
  () => props.logs.length,
  async () => {
    await nextTick();
    if (logListRef.value) {
      logListRef.value.scrollTop = logListRef.value.scrollHeight;
    }
  }
);

const clearLogs = () => {
  emit("clear");
};
</script>

<style scoped>
.debug-panel {
  width: 380px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(12px);
  color: #e2e8f0;
  border-radius: 20px;
  padding: 1.25rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  position: fixed;
  top: 1.5rem;
  right: 1.5rem;
  bottom: 1.5rem;
  z-index: 100;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.title {
  font-weight: 700;
  font-size: 1rem;
  color: #fff;
}

.status {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-left: 0.5rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.log-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-right: 0.5rem;
}

.log-row {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 0.75rem;
  font-size: 0.8125rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.log-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.35rem;
}

.log-type {
  font-weight: 700;
  text-transform: uppercase;
  color: #3b82f6;
  font-size: 0.7rem;
}

.log-time {
  color: #64748b;
  font-size: 0.7rem;
}

.log-message {
  margin: 0;
  color: #cbd5e1;
  line-height: 1.4;
}

.log-row pre {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  font-size: 0.75rem;
  color: #10b981;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.empty {
  text-align: center;
  color: #64748b;
  margin-top: 2rem;
  font-style: italic;
}
</style>
