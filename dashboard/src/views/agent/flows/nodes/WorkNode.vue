<template>
  <div class="work-node" :class="[toneClass, { selected }]">
    <div class="node-header">
      <v-icon :icon="meta.icon" :color="meta.color" size="18" />
      <span class="node-title">{{ data.label || meta.title }}</span>
      <v-chip size="x-small" variant="tonal" :color="meta.chipColor" class="ml-auto">
        {{ stageLabel }}
      </v-chip>
    </div>

    <div class="node-body">
      <div class="summary">{{ promptSummary }}</div>

      <div class="info-grid">
        <div v-if="agentSummary" class="info-item">
          <span class="label">Agent</span>
          <span class="value">{{ agentSummary }}</span>
        </div>
        <div v-if="hitlSummary" class="info-item">
          <span class="label">HITL</span>
          <span class="value">{{ hitlSummary }}</span>
        </div>
        <div v-if="branchSummary" class="info-item">
          <span class="label">分支</span>
          <span class="value">{{ branchSummary }}</span>
        </div>
      </div>

      <div v-if="modeStrategies.length" class="mode-row">
        <div
          v-for="mode in modeStrategies"
          :key="mode.value"
          class="mode-card"
          :class="mode.value"
        >
          <span class="mode-name">{{ mode.label }}</span>
          <span class="mode-text">{{ mode.text }}</span>
        </div>
      </div>
    </div>

    <Handle type="target" :position="Position.Left" class="handle-target" />
    <Handle type="source" :position="Position.Right" class="handle-source" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Handle, Position } from '@vue-flow/core';

const props = defineProps<{
  data: any;
  selected: boolean;
  type?: string;
}>();

const config = computed(() => props.data?.config || {});

const meta = computed(() => {
  const type = props.type || config.value.node_type;
  const map: Record<string, any> = {
    agent_task: {
      title: 'Agent 任务',
      icon: 'mdi-account-cog-outline',
      color: '#2563eb',
      chipColor: 'primary',
      tone: 'agent',
    },
    hitl: {
      title: 'HITL',
      icon: 'mdi-account-question-outline',
      color: '#d97706',
      chipColor: 'warning',
      tone: 'hitl',
    },
    review: {
      title: '审查',
      icon: 'mdi-clipboard-check-outline',
      color: '#0f766e',
      chipColor: 'teal',
      tone: 'review',
    },
    deliverable: {
      title: '交付物',
      icon: 'mdi-package-variant-closed',
      color: '#15803d',
      chipColor: 'success',
      tone: 'deliverable',
    },
    router: {
      title: '分支策略',
      icon: 'mdi-source-branch',
      color: '#7c3aed',
      chipColor: 'deep-purple',
      tone: 'router',
    },
    sub_flow: {
      title: '子流程',
      icon: 'mdi-subdirectory-arrow-right',
      color: '#4f46e5',
      chipColor: 'indigo',
      tone: 'sub-flow',
    },
  };
  return map[type] || map.agent_task;
});

const toneClass = computed(() => `tone-${meta.value.tone}`);
const stageLabel = computed(() => config.value.work_stage || config.value.builtin_stage || meta.value.title);

const promptSummary = computed(() => {
  return truncate(
    props.data?.summary ||
    config.value.prompt ||
    config.value.output ||
    config.value.artifact_type ||
    '按当前配置执行该 Work 阶段。',
    78,
  );
});

const agentSummary = computed(() => {
  const agentIds = [
    config.value.agent_id,
    config.value.default_agent_id,
    config.value.reviewer_id,
    config.value.reporter_id,
    config.value.assistant_id,
    config.value.research_agent_id,
  ].filter(Boolean);
  return agentIds.length ? truncate(agentIds.join(' / '), 46) : '';
});

const hitlSummary = computed(() => {
  if (!config.value.template_id && config.value.repeat_until_clear === undefined && config.value.default_enabled === undefined) {
    return '';
  }
  const parts = [];
  if (config.value.template_id) parts.push(config.value.template_id);
  if (config.value.repeat_until_clear) parts.push('多轮明确');
  if (config.value.default_enabled !== undefined) parts.push(config.value.default_enabled ? '默认启用' : '默认关闭');
  return truncate(parts.join(' · '), 48);
});

const branchSummary = computed(() => {
  const key = config.value.optional_config_key || config.value.max_rework_config_key;
  if (!key) return '';
  return truncate(key, 48);
});

const modeStrategies = computed(() => {
  const strategy = config.value.task_mode_strategy || config.value.modes;
  if (!strategy || typeof strategy !== 'object') return [];
  const textOf = (item: any) => typeof item === 'object' ? item.description || item.label || '' : item;
  return [
    { value: 'quick', label: '快速', text: textOf(strategy.quick) },
    { value: 'normal', label: '常规', text: textOf(strategy.normal) },
    { value: 'deep', label: '深度', text: textOf(strategy.deep) },
  ].filter((item) => item.text).map((item) => ({
    ...item,
    text: truncate(item.text, 24),
  }));
});

function truncate(value: any, length: number): string {
  const text = String(value || '');
  return text.length > length ? `${text.slice(0, length - 1)}...` : text;
}
</script>

<style scoped>
.work-node {
  width: 250px;
  min-height: 132px;
  background: #ffffff;
  border: 2px solid #cbd5e1;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.1);
  overflow: hidden;
}

.work-node.selected {
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.22), 0 10px 24px rgba(15, 23, 42, 0.14);
}

.tone-agent {
  border-color: #2563eb;
}

.tone-hitl {
  border-color: #d97706;
}

.tone-review {
  border-color: #0f766e;
}

.tone-deliverable {
  border-color: #15803d;
}

.tone-router {
  border-color: #7c3aed;
}

.tone-sub-flow {
  border-color: #4f46e5;
}

.node-header {
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.node-title {
  min-width: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-body {
  padding: 10px;
}

.summary {
  min-height: 34px;
  color: #334155;
  font-size: 12px;
  line-height: 1.4;
}

.info-grid {
  margin-top: 8px;
  display: grid;
  gap: 5px;
}

.info-item {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.label {
  color: #64748b;
  font-weight: 600;
}

.value {
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-row {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.mode-card {
  min-height: 48px;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  padding: 5px;
  background: #eff6ff;
}

.mode-card.quick {
  background: #ecfdf5;
  border-color: #bbf7d0;
}

.mode-card.normal {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.mode-card.deep {
  background: #f5f3ff;
  border-color: #ddd6fe;
}

.mode-name {
  display: block;
  color: #0f172a;
  font-size: 11px;
  font-weight: 700;
}

.mode-text {
  display: block;
  margin-top: 2px;
  color: #475569;
  font-size: 10px;
  line-height: 1.25;
}

.handle-target {
  left: -6px;
}

.handle-source {
  right: -6px;
}
</style>
