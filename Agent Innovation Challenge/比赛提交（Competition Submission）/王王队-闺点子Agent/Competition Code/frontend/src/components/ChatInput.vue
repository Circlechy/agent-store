<template>
  <div class="input-card" :class="{ 'has-file': fileList.length > 0 }">
    <div class="input-wrapper">
      <!-- 模式切换入口 -->
      <div class="mode-switch">
        <span 
          class="mode-item" 
          :class="{ active: inputMode === 'screenshot' }" 
          @click="inputMode = 'screenshot'"
        >
          截屏分析
        </span>
        <span class="mode-divider">|</span>
        <span 
          class="mode-item" 
          :class="{ active: inputMode === 'upload' }" 
          @click="inputMode = 'upload'"
        >
          手动上传
        </span>
      </div>

      <!-- 截屏模式 -->
      <div v-if="inputMode === 'screenshot'" class="screenshot-area">
        <NButton 
          type="primary" 
          size="large" 
          round 
          class="analyze-btn" 
          :disabled="disabled"
          @click="handleAnalyze"
        >
          <template #icon>
            <span class="btn-icon">💖</span>
          </template>
          呼叫闺点子
        </NButton>
        <div class="mode-hint">点击按钮，闺点子将自动为你出谋划策</div>
      </div>

      <!-- 上传模式 -->
      <NUpload
        v-if="inputMode === 'upload'"
        v-model:file-list="fileList"
        list-type="image"
        :max="1"
        accept="image/*"
        :default-upload="false"
        @change="handleFileChange"
        class="custom-upload"
      >
        <NUploadDragger v-if="fileList.length === 0">
          <div class="upload-placeholder">
            <div class="upload-icon">🖼️</div>
            <div class="upload-text">点击或拖拽图片进行深度搜索</div>
            <div class="upload-hint">支持 JPG, PNG, WEBP</div>
          </div>
        </NUploadDragger>
      </NUpload>
      
      <div class="input-actions" v-if="inputMode === 'upload' && fileList.length > 0">
        <NButton 
          :disabled="disabled" 
          type="primary" 
          @click="send"
          circle
          size="large"
          class="send-btn"
        >
          <template #icon>
            <div class="send-icon">↑</div>
          </template>
        </NButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { NButton, NUpload, NUploadDragger } from "naive-ui";

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(["send", "analyze"]);

const inputMode = ref("screenshot"); // 默认为截屏模式
const fileList = ref([]);

const handleFileChange = ({ fileList: newFileList }) => {
  fileList.value = newFileList;
};

const send = () => {
  if (fileList.value.length === 0 || props.disabled) {
    return;
  }
  // 发送第一个文件对象
  emit("send", fileList.value[0].file);
  fileList.value = [];
};

const handleAnalyze = () => {
  if (props.disabled) return;
  emit("analyze");
};
</script>

<style scoped>
.input-card {
  background: white;
  border-radius: 20px;
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-color);
  transition: all 0.3s ease;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  width: 100%;
}

.mode-switch {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.mode-item {
  cursor: pointer;
  transition: all 0.2s;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
}

.mode-item:hover {
  color: var(--primary-color);
  background: var(--primary-light);
}

.mode-item.active {
  color: var(--primary-color);
  font-weight: 600;
  background: var(--primary-light);
}

.mode-divider {
  color: var(--border-color);
}

.screenshot-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0;
}

.analyze-btn {
  padding: 0 2.5rem;
  height: 48px;
  font-size: 1.1rem;
  font-weight: 600;
  background: var(--primary-color);
  border: none;
  color: white;
}

.analyze-btn:hover {
  background: var(--primary-hover);
}

.analyze-btn .btn-icon {
  margin-right: 0.5rem;
  font-size: 1.2rem;
}

.mode-hint {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-align: center;
}

.custom-upload {
  width: 100%;
}

.upload-placeholder {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.upload-icon {
  font-size: 2.5rem;
}

.upload-text {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-main);
}

.upload-hint {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.send-btn {
  width: 48px;
  height: 48px;
  background: var(--primary-color);
  border: none;
  transition: transform 0.2s ease;
}

.send-btn:not(:disabled):hover {
  transform: translateY(-2px);
  background: var(--primary-hover);
}

.send-icon {
  font-size: 1.5rem;
  font-weight: bold;
}

:deep(.n-upload-trigger) {
  width: 100%;
}

:deep(.n-upload-dragger) {
  border: 2px dashed var(--border-color);
  background-color: var(--bg-color);
  transition: border-color 0.3s ease;
}

:deep(.n-upload-dragger:hover) {
  border-color: var(--primary-color);
}
</style>
