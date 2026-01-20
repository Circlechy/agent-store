<template>
  <div class="info-collection-panel">
    <!-- 层级 1: 信息收集任务 (面板头部) -->
    <div class="panel-header">
      <span class="title">🔄 闺点子深度搜索中</span>
      <span class="stats">
        <span v-if="runningCount > 0" class="running-count">全力搜索中 {{ runningCount }} | </span>
        已搞定 {{ completedCount }} / 总计 {{ stepsData.length }}
      </span>
    </div>
    
    <!-- 层级 2: N 个 Step -->
    <div class="steps-list">
      <div v-for="step in stepsData" :key="step.title" class="step-container">
        <!-- 步骤头部 -->
        <div class="step-header" :class="`step-${step.status}`">
          <div class="step-info">
            <div class="step-title">{{ step.title }}</div>
            <div class="step-status-tag">
              <span v-if="step.status === 'in_progress'" class="status running">⌛ 进行中</span>
              <span v-else-if="step.status === 'completed'" class="status completed">✓ 已完成</span>
              <span v-else class="status pending">⏳ 等待中</span>
            </div>
          </div>
        </div>
        
        <div class="step-content">
          <!-- 层级 3: 信息收集循环 -->
          <div class="sub-section loop-section" v-if="getRounds(step.agents).length > 0">
            <div class="sub-section-header">
              <span class="icon">🔄</span>
              <span class="label">信息收集循环</span>
            </div>
            
            <!-- 层级 4: N 轮循环 -->
            <div class="rounds-list">
              <div v-for="round in getRounds(step.agents)" :key="round" class="round-block">
                <div class="round-info-bar">
                  开启第 {{ round + 1 }} 轮信息收集
                </div>
                
                <!-- 层级 5: 每轮包含的具体任务 -->
                <div class="round-agents-grid">
                  <div 
                    v-for="agent in getAgentsByRound(step.agents, round)" 
                    :key="agent.agentKey || agent.name" 
                    class="agent-capsule" 
                    :class="`agent-${agent.status}`"
                  >
                    <span class="agent-icon">{{ getAgentIcon(agent.name) }}</span>
                    <span class="agent-label">{{ getAgentLabel(agent.name) }}</span>
                    <span v-if="agent.status === 'running'" class="mini-spinner"></span>
                    <span v-if="agent.status === 'completed'" class="done-check">✓</span>
                    <span v-if="agent.duration" class="duration">
                      {{ formatDuration(agent.duration) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 层级 3: 总结搜索信息 -->
          <div class="sub-section summary-section" v-if="getSummaryAgent(step.agents)">
            <div class="sub-section-header">
              <span class="icon">📊</span>
              <span class="label">总结搜索信息</span>
            </div>
            <div class="summary-item-wrapper">
              <div class="agent-capsule long" :class="`agent-${getSummaryAgent(step.agents).status}`">
                <span class="agent-icon">📊</span>
                <span class="agent-label">总结闺点子发现</span>
                <span v-if="getSummaryAgent(step.agents).status === 'running'" class="mini-spinner"></span>
                <span v-if="getSummaryAgent(step.agents).status === 'completed'" class="done-check">✓</span>
                <span v-if="getSummaryAgent(step.agents).duration" class="duration">
                  {{ formatDuration(getSummaryAgent(step.agents).duration) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  stepsData: {
    type: Array,
    default: () => []
  }
});

const completedCount = computed(() => 
  props.stepsData.filter(s => s.status === 'completed').length
);

const runningCount = computed(() => 
  props.stepsData.filter(s => s.status === 'in_progress').length
);

const getAgentIcon = (agentName) => {
  const iconMap = {
    'tool_select': '🔎',
    'search': '🌐',
    'query_rewrite': '✍️',
    'answerability': '🔍',
    'summarize_findings': '📊'
  };
  return iconMap[agentName] || '🤖';
};

const getAgentLabel = (agentName) => {
  const labelMap = {
    'tool_select': '挑选工具',
    'query_rewrite': '润色思路',
    'search': '搜寻宝贝',
    'answerability': '过滤杂质',
    'summarize_findings': '汇总发现'
  };
  return labelMap[agentName] || agentName;
};

const formatDuration = (ms) => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

const getRounds = (agents) => {
  if (!agents) return [];
  const rounds = agents
    .filter(a => a.round !== null && a.round !== undefined && a.name !== 'summarize_findings')
    .map(a => a.round);
  return [...new Set(rounds)].sort((a, b) => a - b);
};

const getAgentsByRound = (agents, round) => {
  if (!agents) return [];
  return agents.filter(a => a.round === round && a.name !== 'summarize_findings');
};

const getSummaryAgent = (agents) => {
  if (!agents) return null;
  return agents.find(a => a.name === 'summarize_findings');
};
</script>

<style scoped>
.info-collection-panel {
  margin: 1rem 0;
  padding: 1.25rem;
  background: white;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--bg-color);
}

.title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-main);
}

.stats {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  background: var(--bg-color);
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  border: 1px solid var(--border-color);
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.step-container {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-color);
}

.step-header {
  padding: 0.75rem 1rem;
  background: white;
  border-bottom: 1px solid var(--border-color);
}

.step-header.step-in_progress {
  border-left: 4px solid var(--primary-color);
}

.step-header.step-completed {
  border-left: 4px solid var(--primary-color);
}

.step-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.step-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-main);
}

.status {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
}

.status.running { color: var(--primary-color); background: var(--primary-light); }
.status.completed { color: #db2777; background: var(--primary-light); }

.step-content {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* 层级 3 样式 */
.sub-section {
  background: white;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  padding: 0.75rem;
}

.sub-section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

/* 层级 4 样式 */
.round-block {
  margin-bottom: 1rem;
  border: 1px dashed var(--border-color);
  border-radius: 6px;
  padding: 0.5rem;
}

.round-block:last-child { margin-bottom: 0; }

.round-info-bar {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  font-weight: 500;
  display: flex;
  align-items: center;
}

.round-info-bar::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border-color);
  margin-left: 0.5rem;
}

/* 层级 5 样式 */
.round-agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.5rem;
}

.agent-capsule {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.6rem;
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 0.75rem;
  color: var(--text-main);
  transition: all 0.2s;
}

.agent-capsule.long { width: 100%; }

.agent-capsule.agent-running {
  border-color: var(--primary-color);
  background: var(--primary-light);
  color: var(--primary-color);
}

.agent-capsule.agent-completed {
  border-color: var(--primary-color);
  background: var(--primary-light);
  color: var(--primary-color);
}

.agent-label { font-weight: 500; flex: 1; }

.mini-spinner {
  width: 8px;
  height: 8px;
  border: 2px solid var(--primary-color);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.done-check { color: var(--primary-color); font-weight: bold; }

.duration { font-size: 0.7rem; color: var(--text-secondary); }

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
