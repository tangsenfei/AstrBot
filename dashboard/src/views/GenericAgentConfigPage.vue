<template>
  <div class="ga-config-page">
    <header class="identity-band">
      <div class="identity-main">
        <div class="agent-mark">
          <v-icon icon="mdi-desktop-classic" size="30" />
        </div>
        <div>
          <div class="eyebrow">OS Agent</div>
          <h1>GenericAgent 配置</h1>
          <p>作为 NiceBot 内置 OS 操作专家运行，统一管理模型、工具权限、技能审核和集成状态。</p>
        </div>
      </div>
      <div class="identity-signals">
        <v-chip color="primary" variant="tonal" size="small">
          <v-icon start size="15" icon="mdi-lan-pending" />单队列
        </v-chip>
        <v-chip :color="status?.llm_configured ? 'success' : 'warning'" variant="tonal" size="small">
          {{ status?.llm_configured ? '模型已配置' : '待配置模型' }}
        </v-chip>
        <v-chip :color="status?.source_exists ? 'success' : 'error'" variant="tonal" size="small">
          {{ status?.source_exists ? '源码已接入' : '源码缺失' }}
        </v-chip>
        <v-chip :color="llmHealthColor(status?.llm_health)" variant="tonal" size="small">
          {{ llmHealthLabel(status?.llm_health) }}
        </v-chip>
        <v-btn icon="mdi-refresh" variant="text" size="small" :loading="loading" @click="loadAll" />
      </div>
    </header>

    <v-alert v-if="errorText" class="mb-4" type="error" variant="tonal" closable @click:close="errorText = ''">
      {{ errorText }}
    </v-alert>
    <v-alert v-if="successText" class="mb-4" type="success" variant="tonal" closable @click:close="successText = ''">
      {{ successText }}
    </v-alert>

    <section class="status-strip">
      <div class="status-cell">
        <span>上游 commit</span>
        <strong>{{ status?.source_commit || '未检测' }}</strong>
      </div>
      <div class="status-cell">
        <span>运行目录</span>
        <strong>{{ status?.runtime_exists ? '已创建' : '首次运行创建' }}</strong>
      </div>
      <div class="status-cell">
        <span>当前 Provider</span>
        <strong>{{ providerLabel(llmForm.provider_id) || '未选择' }}</strong>
      </div>
      <div class="status-cell">
        <span>当前模型</span>
        <strong>{{ llmForm.model || '未选择' }}</strong>
      </div>
      <div class="status-cell">
        <span>模型健康</span>
        <strong>{{ llmHealthLabel(status?.llm_health) }}</strong>
        <small v-if="status?.last_llm_error">{{ status.last_llm_error }}</small>
      </div>
    </section>

    <section class="config-grid">
      <article class="panel llm-panel">
        <div class="panel-heading">
          <div>
            <h2>LLM Provider</h2>
            <p>只选择 NiceBot 已配置 Provider 和模型，运行时由后端生成 GenericAgent 所需配置。</p>
          </div>
          <v-btn color="primary" variant="flat" :loading="savingConfig" @click="saveConfig">
            保存模型
          </v-btn>
        </div>

        <div class="llm-form">
          <v-select
            v-model="llmForm.provider_id"
            :items="providerOptions"
            item-title="title"
            item-value="value"
            label="Provider"
            variant="outlined"
            density="comfortable"
            :loading="loadingProviders"
            hide-details="auto"
            @update:model-value="onProviderChange"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props" :subtitle="item.raw.subtitle" />
            </template>
          </v-select>

          <v-combobox
            v-model="llmForm.model"
            :items="modelOptions"
            item-title="title"
            item-value="value"
            :return-object="false"
            label="模型"
            variant="outlined"
            density="comfortable"
            :loading="loadingModels"
            :disabled="!llmForm.provider_id"
            hide-details="auto"
          />

          <v-select
            v-model="llmForm.reasoning_effort"
            :items="reasoningOptions"
            label="推理强度"
            variant="outlined"
            density="comfortable"
            hide-details="auto"
          />

          <v-text-field
            v-model.number="llmForm.max_tokens"
            label="最大输出 token"
            type="number"
            variant="outlined"
            density="comfortable"
            hide-details="auto"
          />

          <div class="temperature-row">
            <div>
              <strong>温度</strong>
              <span>{{ llmForm.temperature.toFixed(1) }}</span>
            </div>
            <v-slider
              v-model="llmForm.temperature"
              color="primary"
              min="0"
              max="2"
              step="0.1"
              hide-details
            />
          </div>
        </div>
      </article>

      <article class="panel integration-panel">
        <div class="panel-heading compact">
          <div>
            <h2>集成状态</h2>
            <p>路径和运行参数由 NiceBot 接入层固定管理。</p>
          </div>
        </div>
        <div class="integration-list">
          <div>
            <span>源码目录</span>
            <code>{{ status?.source_path || config.source_path || '-' }}</code>
          </div>
          <div>
            <span>运行目录</span>
            <code>{{ status?.runtime_path || config.runtime_path || '-' }}</code>
          </div>
          <div>
            <span>默认工作目录</span>
            <code>{{ config.default_workspace_path || '-' }}</code>
          </div>
          <div>
            <span>停止策略</span>
            <strong>软停止 {{ config.soft_stop_seconds || 10 }}s 后强制终止</strong>
          </div>
          <div>
            <span>Provider 代理</span>
            <strong>{{ status?.provider_proxy_configured ? '已配置' : '未配置' }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>工具权限</h2>
          <p>GenericAgent 自行选择工具，但实际可见范围由这里的全局开关决定。</p>
        </div>
        <v-btn color="primary" variant="tonal" :loading="savingTools" @click="saveTools">
          保存工具
        </v-btn>
      </div>

      <div class="tool-groups">
        <article v-for="group in toolGroups" :key="group.key" class="tool-group">
          <div class="tool-group-title">
            <v-icon :icon="group.icon" size="18" />
            <span>{{ group.title }}</span>
          </div>
          <div class="tool-list">
            <div v-for="tool in group.tools" :key="tool.tool_name" class="tool-row">
              <div>
                <div class="tool-name-row">
                  <strong>{{ tool.tool_name }}</strong>
                  <v-chip :color="riskColor(tool.tool_name)" size="x-small" variant="tonal">
                    {{ riskLabel(tool.tool_name) }}
                  </v-chip>
                </div>
                <p>{{ toolCopy(tool) }}</p>
              </div>
              <v-switch v-model="tool.enabled" color="primary" density="compact" hide-details />
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>技能审核</h2>
          <p>GenericAgent 沉淀出的经验先进入审核区，通过后同步到 NiceBot 技能库。</p>
        </div>
        <v-chip variant="tonal" color="primary" size="small">
          待审核 {{ reviewCount('pending') }}
        </v-chip>
      </div>

      <v-tabs v-model="reviewTab" density="compact" class="review-tabs">
        <v-tab v-for="tab in reviewTabs" :key="tab.value" :value="tab.value">
          {{ tab.label }} {{ reviewCount(tab.value) }}
        </v-tab>
      </v-tabs>

      <div v-if="filteredReviews.length" class="review-list">
        <article v-for="review in filteredReviews" :key="review.id" class="review-row">
          <div class="review-copy">
            <div class="review-title">
              <strong>{{ review.title }}</strong>
              <v-chip :color="reviewStatusColor(review.status)" size="x-small" variant="tonal">
                {{ reviewStatusLabel(review.status) }}
              </v-chip>
            </div>
            <p>{{ review.description || review.source_path || 'GenericAgent 生成的技能候选' }}</p>
            <div class="review-meta">
              <span>{{ formatDate(review.created_at) }}</span>
              <span v-if="review.synced_skill_id">NiceBot Skill: {{ review.synced_skill_id }}</span>
              <span v-if="review.source_path">{{ review.source_path }}</span>
            </div>
          </div>
          <div v-if="review.status === 'pending'" class="review-actions">
            <v-btn
              color="primary"
              variant="flat"
              size="small"
              :loading="reviewActionId === review.id"
              @click="approveReview(review)"
            >
              批准同步
            </v-btn>
            <v-btn
              color="error"
              variant="tonal"
              size="small"
              :loading="reviewActionId === review.id"
              @click="rejectReview(review)"
            >
              拒绝
            </v-btn>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">
        {{ reviewTab === 'pending' ? '暂无待审核技能' : '当前分类暂无技能记录' }}
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import axios from 'axios';

type IntegrationStatus = {
  source_path?: string;
  runtime_path?: string;
  source_exists?: boolean;
  runtime_exists?: boolean;
  source_commit?: string;
  runtime_ready?: boolean;
  llm_configured?: boolean;
  llm_provider_id?: string;
  llm_model?: string;
  llm_health?: string;
  last_llm_error?: string;
  provider_proxy_configured?: boolean;
};

type GenericAgentConfig = {
  source_path?: string;
  runtime_path?: string;
  default_workspace_path?: string;
  llm_config?: Record<string, any>;
  max_run_seconds?: number;
  soft_stop_seconds?: number;
  integration_status?: IntegrationStatus;
};

type ProviderOption = {
  title: string;
  value: string;
  subtitle?: string;
  raw: Record<string, any>;
};

type SelectOption = {
  title: string;
  value: string;
};

type ToolPolicy = {
  tool_name: string;
  enabled: boolean;
  description?: string;
};

type SkillReview = {
  id: string;
  run_id?: string;
  title: string;
  description?: string;
  content?: string;
  source_path?: string;
  status: string;
  synced_skill_id?: string;
  created_at?: string;
  reviewed_at?: string;
};

const config = reactive<GenericAgentConfig>({});
const tools = ref<ToolPolicy[]>([]);
const reviews = ref<SkillReview[]>([]);
const providerOptions = ref<ProviderOption[]>([]);
const modelOptions = ref<SelectOption[]>([]);
const providersMap = ref<Map<string, ProviderOption>>(new Map());

const loading = ref(false);
const loadingProviders = ref(false);
const loadingModels = ref(false);
const savingConfig = ref(false);
const savingTools = ref(false);
const reviewActionId = ref('');
const errorText = ref('');
const successText = ref('');
const reviewTab = ref('pending');

const llmForm = reactive({
  provider_id: '',
  model: '',
  reasoning_effort: 'medium',
  temperature: 0.7,
  max_tokens: 4096,
});

const reasoningOptions = [
  { title: '低', value: 'low' },
  { title: '中', value: 'medium' },
  { title: '高', value: 'high' },
  { title: '极高', value: 'xhigh' },
];

const reviewTabs = [
  { label: '待审核', value: 'pending' },
  { label: '已同步', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
];

const toolMeta: Record<string, { group: string; copy: string; risk: 'low' | 'medium' | 'high' }> = {
  file_read: { group: 'read', copy: '读取指定工作区内的文件内容，用于理解上下文。', risk: 'low' },
  web_scan: { group: 'read', copy: '读取浏览器页面结构和文本，用于网页观察。', risk: 'medium' },
  file_write: { group: 'write', copy: '创建或覆盖文件，适合生成交付物。', risk: 'high' },
  file_patch: { group: 'write', copy: '对已有文件做局部补丁式修改。', risk: 'high' },
  code_run: { group: 'execute', copy: '执行本机命令或脚本，所有输出进入审计。', risk: 'high' },
  web_execute_js: { group: 'browser', copy: '在浏览器上下文执行 JavaScript 操作页面。', risk: 'high' },
  ask_user: { group: 'memory', copy: '请求人工输入或确认，当前默认不会弹权限确认。', risk: 'low' },
  update_working_checkpoint: { group: 'memory', copy: '更新短期工作检查点，帮助任务恢复上下文。', risk: 'low' },
  start_long_term_update: { group: 'memory', copy: '沉淀长期记忆或技能候选，进入审核区。', risk: 'medium' },
};

const groupDefs = [
  { key: 'read', title: '读取与观察', icon: 'mdi-eye-outline' },
  { key: 'write', title: '文件写入', icon: 'mdi-file-edit-outline' },
  { key: 'execute', title: '命令执行', icon: 'mdi-console-line' },
  { key: 'browser', title: '浏览器操作', icon: 'mdi-web' },
  { key: 'memory', title: '记忆与技能', icon: 'mdi-lightbulb-on-outline' },
  { key: 'other', title: '其他工具', icon: 'mdi-tools' },
];

const status = computed(() => config.integration_status || {});
const filteredReviews = computed(() => reviews.value.filter((review) => review.status === reviewTab.value));
const toolGroups = computed(() =>
  groupDefs
    .map((group) => ({
      ...group,
      tools: tools.value.filter((tool) => (toolMeta[tool.tool_name]?.group || 'other') === group.key),
    }))
    .filter((group) => group.tools.length),
);

onMounted(loadAll);

async function loadAll() {
  loading.value = true;
  errorText.value = '';
  try {
    await Promise.all([loadConfig(), loadTools(), loadReviews(), loadProviders()]);
    if (llmForm.provider_id) await loadModels(false);
  } catch (error: any) {
    showError(error, '加载 GenericAgent 配置失败');
  } finally {
    loading.value = false;
  }
}

async function loadConfig() {
  const response = await axios.get('/api/plug/generic-agent/config');
  const data = response.data?.data || {};
  Object.assign(config, data);
  const llm = data.llm_config || {};
  llmForm.provider_id = llm.provider_id || data.integration_status?.llm_provider_id || '';
  llmForm.model = scalarText(llm.model || data.integration_status?.llm_model || '');
  llmForm.reasoning_effort = llm.reasoning_effort || 'medium';
  llmForm.temperature = Number(llm.temperature ?? 0.7);
  llmForm.max_tokens = Number(llm.max_tokens || 4096);
}

async function loadProviders() {
  loadingProviders.value = true;
  try {
    const response = await axios.get('/api/config/provider/list', {
      params: { provider_type: 'chat_completion' },
    });
    const providers = Array.isArray(response.data?.data) ? response.data.data : [];
    const options: ProviderOption[] = providers
      .filter((provider: any) => provider.enable !== false)
      .map((provider: any) => {
        const modelText = Array.isArray(provider.model) ? provider.model.join(', ') : provider.model || provider.model_name || '';
        return {
          title: provider.name || provider.id,
          value: provider.id,
          subtitle: modelText ? `默认模型 ${modelText}` : provider.provider || '',
          raw: provider,
        };
      });
    providerOptions.value = options;
    providersMap.value = new Map(options.map((item) => [item.value, item]));
  } catch (error: any) {
    showError(error, '加载 Provider 列表失败');
  } finally {
    loadingProviders.value = false;
  }
}

async function loadModels(clearModel = true) {
  if (!llmForm.provider_id) return;
  loadingModels.value = true;
  if (clearModel) llmForm.model = '';
  try {
    const response = await axios.get('/api/config/provider/model_list', {
      params: { provider_id: llmForm.provider_id },
    });
    const models = response.data?.data?.models || [];
    modelOptions.value = modelList(models);
  } catch (error) {
    const provider = providersMap.value.get(llmForm.provider_id)?.raw || {};
    modelOptions.value = modelList(provider.model || provider.model_name || []);
  } finally {
    loadingModels.value = false;
  }
}

async function loadTools() {
  const response = await axios.get('/api/plug/generic-agent/tools');
  const data = response.data?.data;
  tools.value = Array.isArray(data) ? data.map((item) => ({ ...item })) : [];
}

async function loadReviews() {
  const response = await axios.get('/api/plug/generic-agent/skill-reviews');
  const data = response.data?.data;
  reviews.value = Array.isArray(data) ? data : [];
}

async function saveConfig() {
  const model = scalarText(llmForm.model);
  if (!llmForm.provider_id || !model) {
    errorText.value = '请先选择 Provider 和模型。';
    return;
  }
  savingConfig.value = true;
  try {
    await axios.post('/api/plug/generic-agent/config', {
      llm_config: cleanPayload({
        provider_id: llmForm.provider_id,
        model,
        api_mode: 'chat_completions',
        reasoning_effort: llmForm.reasoning_effort,
        temperature: llmForm.temperature,
        max_tokens: llmForm.max_tokens,
      }),
    });
    successText.value = 'GenericAgent 模型配置已保存。';
    await loadConfig();
  } catch (error: any) {
    showError(error, '保存 GenericAgent 配置失败');
  } finally {
    savingConfig.value = false;
  }
}

async function saveTools() {
  savingTools.value = true;
  try {
    await axios.patch('/api/plug/generic-agent/tools', { tools: tools.value });
    successText.value = '工具权限已保存。';
    await loadTools();
  } catch (error: any) {
    showError(error, '保存工具权限失败');
  } finally {
    savingTools.value = false;
  }
}

async function approveReview(review: SkillReview) {
  reviewActionId.value = review.id;
  try {
    await axios.post(`/api/plug/generic-agent/skill-reviews/${review.id}/approve`);
    successText.value = '技能已同步到 NiceBot 技能库。';
    await loadReviews();
  } catch (error: any) {
    showError(error, '批准技能审核失败');
  } finally {
    reviewActionId.value = '';
  }
}

async function rejectReview(review: SkillReview) {
  reviewActionId.value = review.id;
  try {
    await axios.post(`/api/plug/generic-agent/skill-reviews/${review.id}/reject`);
    successText.value = '技能候选已拒绝。';
    await loadReviews();
  } catch (error: any) {
    showError(error, '拒绝技能审核失败');
  } finally {
    reviewActionId.value = '';
  }
}

function onProviderChange() {
  loadModels(true);
}

function modelList(value: any): SelectOption[] {
  const values = Array.isArray(value) ? value : value ? [value] : [];
  return [...new Set(values.filter(Boolean).map(String))].map((item) => ({ title: item, value: item }));
}

function cleanPayload(payload: Record<string, any>) {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== '' && value !== null && value !== undefined));
}

function scalarText(value: any) {
  if (value && typeof value === 'object') {
    return String(value.value || value.title || '').trim();
  }
  return String(value || '').trim();
}

function providerLabel(providerId: string) {
  return providerOptions.value.find((item) => item.value === providerId)?.title || providerId;
}

function toolCopy(tool: ToolPolicy) {
  return toolMeta[tool.tool_name]?.copy || tool.description || 'GenericAgent 扩展工具';
}

function riskLabel(toolName: string) {
  const risk = toolMeta[toolName]?.risk || 'medium';
  return risk === 'high' ? '高风险' : risk === 'medium' ? '中风险' : '低风险';
}

function riskColor(toolName: string) {
  const risk = toolMeta[toolName]?.risk || 'medium';
  return risk === 'high' ? 'error' : risk === 'medium' ? 'warning' : 'success';
}

function reviewCount(statusValue: string) {
  return reviews.value.filter((review) => review.status === statusValue).length;
}

function reviewStatusLabel(statusValue: string) {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已同步',
    rejected: '已拒绝',
  };
  return map[statusValue] || statusValue;
}

function reviewStatusColor(statusValue: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'grey',
  };
  return map[statusValue] || 'grey';
}

function llmHealthLabel(value?: string) {
  const map: Record<string, string> = {
    missing: '待配置模型',
    configured: '配置完整',
    unhealthy: '最近连接失败',
  };
  return map[value || ''] || '未知状态';
}

function llmHealthColor(value?: string) {
  const map: Record<string, string> = {
    missing: 'warning',
    configured: 'success',
    unhealthy: 'error',
  };
  return map[value || ''] || 'grey';
}

function formatDate(value?: string) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function showError(error: any, fallback: string) {
  errorText.value = error?.response?.data?.message || error?.response?.data?.error || error?.message || fallback;
}
</script>

<style scoped>
.ga-config-page {
  min-height: 100%;
  padding: 24px;
  background: rgb(var(--v-theme-background));
}

.identity-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 0 18px;
}

.identity-main {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.agent-mark {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
  border: 1px solid rgba(var(--v-theme-primary), 0.18);
  border-radius: 8px;
}

.eyebrow {
  color: rgb(var(--v-theme-primary));
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
  letter-spacing: 0;
}

h1 {
  font-size: 2rem;
  line-height: 1.15;
}

h2 {
  font-size: 1.12rem;
}

.identity-main p,
.panel-heading p,
.tool-row p,
.review-copy p,
.status-cell span,
.integration-list span,
.review-meta {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.identity-signals {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.status-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-cell,
.panel {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.status-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 12px 14px;
}

.status-cell strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cell small {
  overflow: hidden;
  color: rgba(var(--v-theme-error), 0.82);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.55fr);
  gap: 16px;
  margin-bottom: 16px;
}

.panel {
  padding: 18px;
  margin-bottom: 16px;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-heading.compact {
  margin-bottom: 12px;
}

.llm-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.temperature-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  align-items: center;
  gap: 18px;
  padding: 8px 0;
}

.temperature-row div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.integration-list {
  display: grid;
  gap: 12px;
}

.integration-list div {
  display: grid;
  gap: 4px;
}

.integration-list code {
  overflow-wrap: anywhere;
  color: rgba(var(--v-theme-on-surface), 0.74);
  white-space: normal;
}

.tool-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.tool-group {
  border: 1px solid rgba(var(--v-border-color), 0.24);
  border-radius: 8px;
  overflow: hidden;
}

.tool-group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-weight: 700;
  background: rgba(var(--v-theme-on-surface), 0.035);
}

.tool-list,
.review-list {
  display: grid;
}

.tool-row,
.review-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 12px;
  border-top: 1px solid rgba(var(--v-border-color), 0.16);
}

.tool-row:first-child {
  border-top: 0;
}

.tool-name-row,
.review-title,
.review-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tool-row p,
.review-copy p {
  margin-top: 4px;
  font-size: 0.86rem;
}

.review-tabs {
  margin-bottom: 8px;
}

.review-copy {
  min-width: 0;
}

.review-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 0.78rem;
}

.review-meta span {
  overflow-wrap: anywhere;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

@media (max-width: 1200px) {
  .tool-groups,
  .status-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .ga-config-page {
    padding: 16px;
  }

  .identity-band,
  .panel-heading,
  .review-row {
    align-items: stretch;
    flex-direction: column;
  }

  .config-grid,
  .llm-form,
  .tool-groups,
  .status-strip {
    grid-template-columns: 1fr;
  }

  .temperature-row {
    grid-template-columns: 1fr;
  }
}
</style>
