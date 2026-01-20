<template>
  <div class="chat-container">
    <div class="chat-view">
      <header class="chat-header">
        <div class="header-content">
          <div class="logo-area">
            <h1>闺点子</h1>
            <div class="status-badge" :class="{ active: isHealthy || isConnected }">
              <span class="dot"></span>
              {{ isConnected ? "正在搜索..." : (isHealthy ? "闺点子已就绪" : "等待闺点子...") }}
            </div>
          </div>
          <p class="subtitle">在购物海洋中为你导航，避开陷阱，找到真正适合你的宝贝。</p>
        </div>
        <div class="header-actions">
          <NButton size="medium" @click="clearConversation" secondary strong round>
            清空对话
          </NButton>
        </div>
      </header>

      <main ref="messageContainer" class="message-list" @scroll="onScroll">
        <div v-if="!messages.length" class="welcome-panel">
          <div class="welcome-card">
            <h2>👋 欢迎体验闺点子</h2>
            <p>在这里你可以看到闺点子如何一步步在购物海洋中为你导航，避开陷阱，找到真正适合你的宝贝。</p>
          </div>
        </div>
        
        <!-- 用户消息和AI推理过程 -->
        <template v-for="(msg, index) in messages" :key="msg.id">
          <!-- 显示用户消息 -->
          <ChatMessage v-if="msg.role === 'user'" :message="msg" />
          
          <!-- 显示 AI Top-Level 消息（entry、planner、answer）-->
          <template v-else-if="msg.role === 'assistant' && msg.agent">
            <!-- 图片意图识别 节点 -->
            <ChatMessage
              v-if="msg.agent === 'image_intent_recognition'"
              :message="msg"
            >
              <template #content>
                <div v-if="parseRecognitionContent(msg.content)" class="recognition-display">
                  <div v-if="parseRecognitionContent(msg.content).need_query === false" class="recognition-no-query">
                    抱歉，闺点子没看懂你想要的东西呢
                  </div>
                  <template v-else>
                    <div class="recognition-text-line">
                      识别到你正在浏览：<span class="recognition-keyword">{{ parseRecognitionContent(msg.content).search_keyword }}</span>
                    </div>
                    <div class="recognition-text-line">
                      猜你想问：<span class="recognition-generated-query">{{ parseRecognitionContent(msg.content).generated_query }}</span>
                    </div>
                  </template>
                </div>
                <div v-else>{{ '正在分析图片意图...' }}</div>
              </template>
            </ChatMessage>

            <!-- Entry 节点 -->
            <ChatMessage
              v-if="msg.agent === 'entry'"
              :message="msg"
            >
              <template #content>
                {{ msg.content || '闺点子出谋划策中...' }}
              </template>
            </ChatMessage>
            
            <!-- Planner 节点 -->
            <ChatMessage
              v-else-if="msg.agent === 'planner'"
              :message="msg"
            >
              <template #content>
                <div class="planner-display">
                  <div class="planner-title">{{ parsePlannerContent(msg.content)?.title || '搜索计划' }}</div>
                  <div class="planner-thought" v-if="parsePlannerContent(msg.content)?.thought">
                    {{ parsePlannerContent(msg.content).thought }}
                  </div>
                  <div class="planner-steps">
                    <div v-for="(step, sIdx) in parsePlannerContent(msg.content)?.steps" :key="sIdx" class="planner-step-item">
                      <div class="step-dot">{{ sIdx + 1 }}</div>
                      <div class="step-content">
                        <div class="step-title">{{ step.title }}</div>
                        <div class="step-desc">{{ step.description }}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </ChatMessage>
            
            <!-- Answer 节点 -->
            <template v-else-if="msg.agent === 'answer'">
              <ChatMessage :message="msg">
                <template #content>
                  <div v-if="parseAnswerContent(msg.content)" class="answer-display">
                    <!-- 原始问题 -->
                    <div class="answer-section query-section">
                      <div class="section-tag">我猜你想问</div>
                      <div class="query-text">{{ parseAnswerContent(msg.content).query }}</div>
                    </div>

                    <!-- 事实依据 -->
                    <div class="answer-section basis-section" v-if="parseAnswerContent(msg.content).basis.length > 0">
                      <div class="section-tag">根据</div>
                      <div class="basis-list">
                        <div v-for="(item, bIdx) in parseAnswerContent(msg.content).basis" :key="bIdx" class="basis-item">
                          <span class="item-num">{{ bIdx + 1 }}</span>
                          <div class="item-text" v-html="formatRichText(item)"></div>
                        </div>
                      </div>
                    </div>

                    <!-- 最终结论 -->
                    <div class="answer-section final-section">
                      <div class="section-tag conclusion-tag">回答</div>
                      <div class="conclusion-list">
                        <div v-for="(item, aIdx) in parseAnswerContent(msg.content).answer" :key="aIdx" class="conclusion-item">
                          <div class="item-text" v-html="formatRichText(item)"></div>
                        </div>
                      </div>
                    </div>

                    <!-- 迁移后的 ShowImage 图片展示区域 -->
                    <div class="answer-section image-section" v-if="getRelatedImages(index) && getRelatedImages(index).length > 0">
                      <div class="section-tag">闺点子show图</div>
                      <div class="image-grid">
                        <div v-for="(imgItem, idx) in getRelatedImages(index)" :key="idx" class="image-item">
                           <div class="image-wrapper">
                             <NImage :src="getApiUrl(imgItem.url || imgItem)" alt="闺点子show图" class="recommend-image" object-fit="cover" />
                             <div v-if="imgItem.source" class="image-source-tag">{{ imgItem.source }}</div>
                           </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else>
                    {{ msg.content }}
                    <!-- 纯文本模式下也尝试显示图片 -->
                    <div class="show-image-display" v-if="getRelatedImages(index) && getRelatedImages(index).length > 0" style="margin-top: 1rem;">
                      <div class="image-grid">
                        <div v-for="(imgItem, idx) in getRelatedImages(index)" :key="idx" class="image-item">
                           <div class="image-wrapper">
                             <NImage :src="getApiUrl(imgItem.url || imgItem)" alt="闺点子show图" class="recommend-image" object-fit="cover" />
                             <div v-if="imgItem.source" class="image-source-tag">{{ imgItem.source }}</div>
                           </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </ChatMessage>
            </template>

            <!-- InfoCollectionPanel 节点 (中间过程) -->
            <template v-else-if="msg.agent === 'info_collector'">
              <InfoCollectionPanel
                :steps-data="msg.stepsData"
              />
            </template>
          </template>
        </template>
        
        <div v-if="isSearching" class="loading-state">
          <LoadingIndicator />
          <span>{{ searchingStatusText }}</span>
        </div>
      </main>

      <footer class="chat-footer">
        <ChatInput 
          :disabled="isSearching" 
          @send="handleSend" 
          @analyze="handleAnalyze"
        />
      </footer>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch, nextTick, computed } from "vue";
import { useMessage, NButton, NImage } from "naive-ui";

import ChatInput from "../components/ChatInput.vue";
import ChatMessage from "../components/ChatMessage.vue";
import AgentMessage from "../components/AgentMessage.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import InfoCollectionPanel from "../components/InfoCollectionPanel.vue";

import { useChatHistory } from "../composables/useChatHistory.js";
import { useSSE } from "../composables/useSSE.js";
import { validateQuery } from "../utils/validation.js";
import { checkHealth, getApiUrl } from "../utils/api.js";
import { StreamMessageProcessor, MessageDisplayFilter } from "../utils/streamMessageProcessor.js";

const message = useMessage();
const { messages, addMessage, replaceLastAssistantMessage, clearMessages } = useChatHistory();
const { isConnected, isSearching, reconnectAttempts, startSearch, stopSearch } = useSSE();

const isHealthy = ref(false);
const messageContainer = ref(null);
const userAtBottom = ref(true);
const streamProcessor = new StreamMessageProcessor();
const messageFilter = new MessageDisplayFilter();

/**
 * 动态计算搜索进度文案
 */
const searchingStatusText = computed(() => {
  if (!isSearching.value) return "";
  
  // 从后往前查找当前正在进行的任务节点
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i];
    if (msg.role !== 'assistant') continue;
    
    const agent = msg.agent;
    
    if (agent === 'image_intent_recognition') return "图片意图识别中...";
    if (agent === 'entry') return "问题分析中...";
    if (agent === 'planner') return "规划搜索中...";
    if (agent === 'info_collector' || messageFilter.isIntermediateAgent(agent)) {
      return "信息搜集中...";
    }
    if (agent === 'answer') return "生成答案中...";
  }
  
  return "深度搜索中...";
});

const parsePlannerContent = (content) => {
  if (!content) return null;
  try {
    let cleanContent = content.trim();
    if (typeof cleanContent === 'string' && cleanContent.startsWith('```')) {
      cleanContent = cleanContent.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '').trim();
    }
    return typeof cleanContent === 'string' ? JSON.parse(cleanContent) : cleanContent;
  } catch (e) {
    console.warn('⚠️ 无法解析 planner 内容:', e);
    return null;
  }
};

const parseRecognitionContent = (content) => {
  if (!content) return null;
  
  // 1. 优先尝试正则表达式提取（支持流式输出中的不完整 JSON）
  const keywordMatch = content.match(/"search_keyword":\s*"([^"]*)"?/);
  const queryMatch = content.match(/"generated_query":\s*"([^"]*)"?/);
  const needQueryMatch = content.match(/"need_query":\s*(true|false|"[^"]*")/i);
  
  let needQuery = true;
  if (needQueryMatch) {
    const val = needQueryMatch[1].replace(/"/g, '').toLowerCase();
    if (val === 'false') needQuery = false;
  }
  
  if (keywordMatch || queryMatch) {
    return {
      search_keyword: (keywordMatch ? keywordMatch[1] : '').replace(/\\"/g, '"') || '识别中...',
      generated_query: (queryMatch ? queryMatch[1] : '').replace(/\\"/g, '"') || '正在生成建议...',
      need_query: needQuery
    };
  }

  // 2. 备选方案：全量 JSON 解析
  try {
    // 处理可能存在的 Markdown 代码块包裹
    let cleanContent = content.trim();
    if (cleanContent.startsWith('```')) {
      cleanContent = cleanContent.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '').trim();
    }
    
    const parsed = typeof cleanContent === 'string' ? JSON.parse(cleanContent) : cleanContent;
    
    // 解析 need_query
    let parsedNeedQuery = parsed.need_query;
    if (parsedNeedQuery === 'False' || parsedNeedQuery === false || parsedNeedQuery === 'false') {
        parsedNeedQuery = false;
    } else {
        parsedNeedQuery = true;
    }

    return {
      search_keyword: parsed.extracted_info?.search_keyword || parsed.search_keyword || '未知关键词',
      generated_query: parsed.generated_query || '暂无推荐查询',
      need_query: parsedNeedQuery
    };
  } catch (e) {
    return null;
  }
};

const parseShowImageContent = (content) => {
  if (!content) return null;
  try {
    let cleanContent = content.trim();
    if (cleanContent.startsWith('```')) {
      cleanContent = cleanContent.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '').trim();
    }
    const parsed = typeof cleanContent === 'string' ? JSON.parse(cleanContent) : cleanContent;
    return Array.isArray(parsed) ? parsed : null;
  } catch (e) {
    return null;
  }
};

const parseAnswerContent = (content) => {
  if (!content || typeof content !== 'string') return null;
  
  const result = {
    query: '',
    basis: [],
    answer: []
  };

  // 改进的正则：支持中英文标题，支持半角和全角冒号，支持可选的 "- " 前缀
  // 使用 split 分割出大板块
  const sections = content.split(/(?:^|\n)\s*(?:-\s*)?(QUERY|BASIS|ANSWER|我猜你想问|根据|回答)[:：]\s*(?:\n|$)/m);
  
  for (let i = 1; i < sections.length; i += 2) {
    const title = sections[i];
    const body = sections[i + 1]?.trim() || '';
    
    let type = '';
    if (title === 'QUERY' || title === '我猜你想问') type = 'query';
    if (title === 'BASIS' || title === '根据') type = 'basis';
    if (title === 'ANSWER' || title === '回答') type = 'answer';
    
    if (type === 'query') {
      result.query = body;
    } else if (type === 'basis' || type === 'answer') {
      // 更加稳健的项目提取逻辑：
      // 匹配所有以 "数字." 开头的行，并提取其后的内容
      // 使用全局匹配 + 多行模式
      const itemRegex = /(?:^|\n)\s*\d+\.\s+([\s\S]*?)(?=\n\s*\d+\.\s+|$)/g;
      let items = [];
      let match;
      
      while ((match = itemRegex.exec(body)) !== null) {
        items.push(match[1].trim());
      }
      
      // 如果 body 不为空但没匹配到数字列表（可能是非列表格式），则整块作为一项
      if (items.length === 0 && body) {
        items = [body];
      }
      
      result[type] = items;
    }
  }
  
  if (!result.query && result.basis.length === 0 && result.answer.length === 0) return null;
  return result;
};

const getRelatedImages = (index) => {
  // 从当前索引向后查找
  for (let i = index + 1; i < messages.value.length; i++) {
    const msg = messages.value[i];
    // 如果遇到 show_image 节点，返回其内容
    if (msg.agent === 'show_image') {
      return parseShowImageContent(msg.content);
    }
    // 如果遇到新的用户提问或新的回答，停止查找（防止跨轮次匹配）
    if (msg.role === 'user' || msg.agent === 'answer' || msg.agent === 'entry') {
      break;
    }
  }
  return null;
};

const formatRichText = (text) => {
  if (!text) return '';
  // 处理 [标题: 链接] 格式
  return text
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="source-link">$1</a>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
};

const scrollToBottom = () => {
  const container = messageContainer.value;
  if (!container || !userAtBottom.value) {
    return;
  }
  container.scrollTop = container.scrollHeight;
};

const onScroll = () => {
  const container = messageContainer.value;
  if (!container) {
    return;
  }
  const threshold = 80;
  const distance =
    container.scrollHeight - container.scrollTop - container.clientHeight;
  userAtBottom.value = distance <= threshold;
};

// 监视整个 messages 数组及其深层变化
watch(messages, () => {
  scrollToBottom();
}, { deep: true });

// 专门监视正在进行的搜索内容变化，确保滚动
watch(isSearching, (searching) => {
  if (searching) {
    // 开始搜索时确保滚动到最底
    nextTick(() => {
      userAtBottom.value = true;
      scrollToBottom();
    });
  }
});

const handleSend = (file) => {
  if (!file) {
    message.warning("请先上传图片");
    return;
  }

  // 创建本地预览 URL
  const imageUrl = URL.createObjectURL(file);

  // 添加用户消息
  addMessage("user", ``, null, null, null, imageUrl);
  
  // 重置状态
  streamProcessor.reset();
  
  let currentInfoCollectorId = null;

  const onChunk = (chunk) => {
    // 处理后端发送的元数据（如图片 URL）
    if (chunk && chunk.event === 'metadata' && chunk.image_url) {
      console.log('🖼️ 收到图片元数据:', chunk.image_url);
      const baseUrl = getApiUrl('').replace('/api/v1', '').replace(/\/$/, '');
      const fullImageUrl = `${baseUrl}${chunk.image_url}`;
      
      // 查找最后一条用户消息并更新其图片预览
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].role === 'user') {
          // 使用对象展开确保响应式触发
          // 收到图片后，清空"闺点子收图中..."的提示语
          messages.value[i] = { ...messages.value[i], imageUrl: fullImageUrl, content: '' };
          messages.value = [...messages.value];
          break;
        }
      }
      return;
    }

    // 使用流式消息处理器处理chunk
    const processedMessage = streamProcessor.processChunk(chunk);

    if (processedMessage) {
      const agent = processedMessage.agent;
      
      // 只处理需要显示的 top-level 消息
      if (messageFilter.shouldDisplay(agent)) {
        // 检查是否已经存在该 ID 的消息
        let existingIndex = -1;
        for (let i = 0; i < messages.value.length; i++) {
          if (messages.value[i].id === processedMessage.id) {
            existingIndex = i;
            break;
          }
        }
        
        if (existingIndex === -1) {
          // 新消息，添加到列表
          const newMsg = {
            id: processedMessage.id,
            role: processedMessage.role,
            content: processedMessage.content,
            timestamp: processedMessage.timestamp,
            agent: processedMessage.agent,
            agentLabel: processedMessage.agentLabel,
            agentColor: processedMessage.agentColor,
            bgColor: processedMessage.bgColor,
            showRaw: processedMessage.showRaw,
            rawData: processedMessage.rawData,
            isComplete: processedMessage.isComplete,
            duration: processedMessage.duration
          };
          messages.value.push(newMsg);
        } else {
          // 已有消息，更新内容
          messages.value[existingIndex].content = processedMessage.content;
          messages.value[existingIndex].rawData = processedMessage.rawData;
          messages.value[existingIndex].isComplete = processedMessage.isComplete;
          messages.value[existingIndex].duration = processedMessage.duration;
          messages.value = [...messages.value];
        }
      }
      
      // 处理中间节点
      if (messageFilter.isIntermediateAgent(agent)) {
        if (!currentInfoCollectorId) {
          currentInfoCollectorId = `info_collector-${Date.now()}`;
          messages.value.push({
            id: currentInfoCollectorId,
            role: 'assistant',
            agent: 'info_collector',
            stepsData: streamProcessor.getStepsData(),
            timestamp: new Date().toISOString()
          });
        } else {
          const idx = messages.value.findIndex(m => m.id === currentInfoCollectorId);
          if (idx !== -1) {
            messages.value[idx].stepsData = streamProcessor.getStepsData();
            messages.value = [...messages.value];
          }
        }
      }
    }
  };

  const onComplete = () => {
    message.success("图片搜索已完成");
  };

  const onError = (err) => {
    message.error(err?.message || "搜索过程中发生错误");
  };

  startSearch({
    file,
    onChunk,
    onComplete,
    onError
  });
};

const handleAnalyze = () => {
  // 添加用户消息，提示正在截屏分析
  addMessage("user", "闺点子收图中...");
  
  // 重置状态
  streamProcessor.reset();
  
  let currentInfoCollectorId = null;

  const onChunk = (chunk) => {
    // 处理后端发送的元数据（如图片 URL）
    if (chunk && chunk.event === 'metadata' && chunk.image_url) {
      console.log('🖼️ 收到图片元数据:', chunk.image_url);
      const baseUrl = getApiUrl('').replace('/api/v1', '').replace(/\/$/, '');
      const fullImageUrl = `${baseUrl}${chunk.image_url}`;
      
      // 查找最后一条用户消息并更新其图片预览
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].role === 'user') {
          // 使用对象展开确保响应式触发
          // 收到图片后，清空"闺点子收图中..."的提示语
          messages.value[i] = { ...messages.value[i], imageUrl: fullImageUrl, content: '' };
          messages.value = [...messages.value];
          break;
        }
      }
      return;
    }

    // 使用流式消息处理器处理chunk
    const processedMessage = streamProcessor.processChunk(chunk);

    if (processedMessage) {
      const agent = processedMessage.agent;
      
      // 只处理需要显示的 top-level 消息
      if (messageFilter.shouldDisplay(agent)) {
        // 检查是否已经存在该 ID 的消息
        let existingIndex = -1;
        for (let i = 0; i < messages.value.length; i++) {
          if (messages.value[i].id === processedMessage.id) {
            existingIndex = i;
            break;
          }
        }
        
        if (existingIndex === -1) {
          // 新消息，添加到列表
          const newMsg = {
            id: processedMessage.id,
            role: processedMessage.role,
            content: processedMessage.content,
            timestamp: processedMessage.timestamp,
            agent: processedMessage.agent,
            agentLabel: processedMessage.agentLabel,
            agentColor: processedMessage.agentColor,
            bgColor: processedMessage.bgColor,
            showRaw: processedMessage.showRaw,
            rawData: processedMessage.rawData,
            isComplete: processedMessage.isComplete,
            duration: processedMessage.duration
          };
          messages.value.push(newMsg);
        } else {
          // 已有消息，更新内容
          messages.value[existingIndex].content = processedMessage.content;
          messages.value[existingIndex].rawData = processedMessage.rawData;
          messages.value[existingIndex].isComplete = processedMessage.isComplete;
          messages.value[existingIndex].duration = processedMessage.duration;
          messages.value = [...messages.value];
        }
      }
      
      // 处理中间节点
      if (messageFilter.isIntermediateAgent(agent)) {
        if (!currentInfoCollectorId) {
          currentInfoCollectorId = `info_collector-${Date.now()}`;
          messages.value.push({
            id: currentInfoCollectorId,
            role: 'assistant',
            agent: 'info_collector',
            stepsData: streamProcessor.getStepsData(),
            timestamp: new Date().toISOString()
          });
        } else {
          const idx = messages.value.findIndex(m => m.id === currentInfoCollectorId);
          if (idx !== -1) {
            messages.value[idx].stepsData = streamProcessor.getStepsData();
            messages.value = [...messages.value];
          }
        }
      }
    }
  };

  const onComplete = () => {
    message.success("截屏分析已完成");
  };

  const onError = (err) => {
    message.error(err?.message || "截屏分析过程中发生错误");
  };

  startSearch({
    action: 'screenshot',
    onChunk,
    onComplete,
    onError
  });
};

const clearConversation = () => {
  stopSearch();
  clearMessages();
};

onMounted(async () => {
  try {
    await checkHealth();
    isHealthy.value = true;
  } catch (error) {
    isHealthy.value = false;
    message.error("后端健康检查失败，请确保服务已启动");
  }
});
</script>

<style scoped>
.chat-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  background: var(--bg-color);
}

.chat-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1000px;
  height: 100%;
  padding: 0 1.5rem;
  position: relative;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.chat-header h1 {
  font-size: 1.5rem;
  font-weight: 800;
  background: linear-gradient(90deg, var(--primary-color) 0%, #f472b6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.025em;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.6rem;
  background: white;
  border-radius: 20px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
  border: 1px solid var(--border-color);
}

.status-badge.active .dot {
  background: var(--primary-color);
  box-shadow: 0 0 8px rgba(219, 39, 119, 0.3);
}

.status-badge .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

.subtitle {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.message-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 0.5rem;
  overflow-y: auto;
  scrollbar-width: thin;
}

.welcome-panel {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.welcome-card {
  text-align: center;
  padding: 3rem;
  background: white;
  border-radius: 24px;
  box-shadow: var(--shadow-md);
  max-width: 500px;
  border: 1px solid var(--border-color);
}

.welcome-card h2 {
  margin-bottom: 1rem;
  color: var(--text-main);
}

.welcome-card p {
  color: var(--text-secondary);
  line-height: 1.6;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.5rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
}

.chat-footer {
  padding: 1.5rem 0 2rem;
  background: transparent;
}

/* 规划师美化显示 */
.planner-display {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.planner-title {
  font-weight: 700;
  font-size: 1rem;
  color: var(--text-main);
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 0.5rem;
  margin-bottom: 0.25rem;
}

.planner-thought {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-style: italic;
  line-height: 1.5;
  background: var(--bg-color);
  padding: 0.75rem;
  border-radius: 8px;
  border-left: 3px solid var(--primary-color);
}

.planner-steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.planner-step-item {
  display: flex;
  gap: 0.75rem;
  background: white;
  padding: 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.planner-step-item:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-sm);
}

.step-dot {
  width: 24px;
  height: 24px;
  background: var(--primary-light);
  color: var(--primary-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.step-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.step-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-main);
}

.step-desc {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* 识别结果美化显示 */
.recognition-display {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem 0;
}

.recognition-no-query {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-main);
  padding: 0.25rem 0;
  font-weight: 500;
}

.recognition-text-line {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-main);
}

.recognition-keyword {
  font-weight: 700;
  color: var(--primary-color);
}

.recognition-generated-query {
  font-weight: 700;
  color: var(--primary-color);
  background: var(--primary-light);
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  display: inline-block;
  margin-top: 0.25rem;
}

/* 最终答案美化显示 */
.answer-display {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 0.5rem 0;
}

.answer-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  position: relative;
}

.section-tag {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.section-tag::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-color);
}

.query-text {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.4;
}

.basis-list, .conclusion-list {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.basis-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  background: white;
  border-radius: 10px;
  font-size: 0.875rem;
  line-height: 1.6;
  border: 1px solid var(--border-color);
}

.item-num {
  font-weight: 800;
  color: var(--primary-color);
  font-family: serif;
}

.conclusion-item {
  padding: 1rem;
  background: white;
  border-radius: 12px;
  border-left: 4px solid var(--primary-color);
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
}

.conclusion-tag {
  color: var(--primary-color);
}

:deep(.source-link) {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.4rem;
  margin: 0 0.2rem;
  background: var(--primary-light);
  color: var(--primary-color);
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.2s;
}

:deep(.source-link:hover) {
  background: var(--primary-color);
  color: white;
}

.show-image-display {
  width: 100%;
}

.image-grid {
  display: flex;
  overflow-x: auto;
  gap: 1.25rem;
  padding: 0.5rem 0.25rem 1rem;
  /* 开启横向滚动条显示 */
  scrollbar-width: thin; 
  scrollbar-color: var(--primary-light) transparent;
}

/* 美化横向滚动条样式 */
.image-grid::-webkit-scrollbar {
  height: 6px; /* 横向滚动条高度 */
  display: block;
}

.image-grid::-webkit-scrollbar-track {
  background: transparent;
}

.image-grid::-webkit-scrollbar-thumb {
  background: var(--primary-light);
  border-radius: 10px;
  transition: background 0.3s;
}

.image-grid::-webkit-scrollbar-thumb:hover {
  background: var(--primary-color);
}

.image-item {
  flex: 0 0 160px; /* 固定宽度以支持横向滚动 */
  border-radius: 12px;
  overflow: hidden;
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid var(--border-color);
}

.image-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--primary-light);
}

.image-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4; /* 适合手机截屏的比例 */
  overflow: hidden;
}

.recommend-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top; /* 确保截屏顶部（通常是状态栏或核心标题）可见 */
  transition: transform 0.5s ease;
  cursor: pointer;
}

.image-item:hover .recommend-image {
  transform: scale(1.08);
}

.image-source-tag {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 4px 10px;
  font-size: 10px;
  font-weight: 700;
  color: white;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  border-radius: 20px;
  pointer-events: none;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid rgba(255, 255, 255, 0.2);
  z-index: 1;
}
</style>
