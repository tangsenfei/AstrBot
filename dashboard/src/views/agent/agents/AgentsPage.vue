<template>

  <v-container fluid class="pa-6">

    <!-- 页面标题 -->
    <v-row>
      <v-col cols="12">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-robot" class="mr-2" />
            {{ t('agent.agents.title') }}
            <v-spacer />
            <v-btn color="primary" @click="openAddEditor" class="mr-2">
              <v-icon start icon="mdi-plus" />
              {{ t('agent.agents.buttons.add') }}
            </v-btn>
            <v-btn variant="outlined" @click="loadAgents" :loading="loading" class="mr-2">
              <v-icon start icon="mdi-refresh" />
              {{ t('agent.agents.buttons.refresh') }}
            </v-btn>
            <v-menu>
              <template v-slot:activator="{ props }">
                <v-btn variant="outlined" v-bind="props">
                  <v-icon start icon="mdi-dots-vertical" />
                  {{ t('agent.agents.buttons.more') }}
                </v-btn>
              </template>
              <v-list>
                <v-list-item @click="showTemplatesDialog = true">
                  <template v-slot:prepend>
                    <v-icon icon="mdi-file-document-multiple" />
                  </template>
                  <v-list-item-title>{{ t('agent.agents.buttons.templates') }}</v-list-item-title>
                </v-list-item>
                <v-list-item @click="importAgents">
                  <template v-slot:prepend>
                    <v-icon icon="mdi-import" />
                  </template>
                  <v-list-item-title>{{ t('agent.agents.buttons.import') }}</v-list-item-title>
                </v-list-item>
                <v-list-item @click="exportAgents">
                  <template v-slot:prepend>
                    <v-icon icon="mdi-export" />
                  </template>
                  <v-list-item-title>{{ t('agent.agents.buttons.export') }}</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </v-card-title>
          <v-card-subtitle>
            {{ t('agent.agents.subtitle') }}
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <!-- 筛选和搜索 -->
    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-text class="pb-2">
            <v-row align="center">
              <v-col cols="12" md="8">
                <v-tabs v-model="activeTab" color="primary">
                  <v-tab value="all">{{ t('agent.agents.tabs.all') }}</v-tab>
                  <v-tab value="builtin">
                    <v-icon icon="mdi-shield-crown" start size="small" />
                    {{ t('agent.agents.tabs.builtin') }}
                  </v-tab>
                  <v-tab value="expert">
                    <v-icon icon="mdi-account-star" start size="small" />
                    {{ t('agent.agents.tabs.expert') }}
                  </v-tab>
                  <v-tab value="custom">
                    <v-icon icon="mdi-pencil" start size="small" />
                    {{ t('agent.agents.tabs.custom') }}
                  </v-tab>
                </v-tabs>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="searchQuery"
                  :placeholder="t('agent.agents.search.placeholder')"
                  prepend-inner-icon="mdi-magnify"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 专家团标签页 -->
    <template v-if="activeTab === 'expert'">
      <v-row>
        <v-col cols="12">
          <v-card>
            <v-card-title class="d-flex align-center">
              <v-icon icon="mdi-account-star" class="mr-2" />
              {{ t('agent.agents.expert.createdExperts') }}
              <v-chip size="small" variant="flat" color="purple" class="ml-2">
                {{ expertAgents.length }}
              </v-chip>
              <v-spacer />
              <v-btn
                variant="outlined"
                color="primary"
                size="small"
                @click="openBatchLlmDialog"
              >
                <v-icon start icon="mdi-cog" size="small" />
                {{ t('agent.agents.expert.batchLlm') }}
              </v-btn>
            </v-card-title>
            <v-card-text>
              <!-- 分类 chip 横向滚动 -->
              <div class="chip-scroll-container mb-4">
                <v-chip-group v-model="selectedExpertCategory" mandatory>
                  <v-chip
                    v-for="cat in expertCategoryList"
                    :key="cat.key"
                    :value="cat.key"
                    variant="outlined"
                    filter
                    size="small"
                  >
                    <v-icon :icon="cat.icon" start size="x-small" />
                    {{ cat.label }}
                    <span v-if="cat.key !== 'all'" class="ml-1 text-grey">({{ getExpertCategoryCount(cat.key) }})</span>
                  </v-chip>
                </v-chip-group>
              </div>
            </v-card-text>
            <v-card-text v-if="loading" class="text-center py-8">
              <v-progress-circular indeterminate color="primary" />
              <p class="mt-4 text-grey">{{ t('common.loading') }}</p>
            </v-card-text>
            <v-card-text v-else-if="filteredExpertAgents.length === 0" class="text-center py-8">
              <v-icon icon="mdi-account-star" size="60" color="grey-lighten-1" class="mb-4" />
              <p class="text-grey">{{ t('agent.agents.expert.noExperts') }}</p>
            </v-card-text>
            <v-container fluid v-else>
              <v-row>
                <v-col
                  v-for="agent in filteredExpertAgents"
                  :key="agent.name"
                  cols="12"
                  sm="6"
                  md="4"
                  lg="3"
                >
                  <AgentCard
                    :agent="agent"
                    @edit="openEditor"
                    @test="openTester"
                    @copy="copyAgent"
                    @delete="deleteAgent"
                    @toggle="toggleAgent"
                    @reset="resetBuiltinAgent"
                    @createFromExpert="createFromExpert"
                    @viewDetail="openAgentDetail"
                  />
                </v-col>
              </v-row>
            </v-container>
          </v-card>
        </v-col>
      </v-row>
    </template>

    <!-- 非专家团标签页：普通智能体列表 -->
    <v-row v-if="activeTab !== 'expert'">
      <v-col cols="12">
        <v-card>
          <v-card-text v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-4 text-grey">{{ t('common.loading') }}</p>
          </v-card-text>

          <v-card-text v-else-if="filteredAgents.length === 0" class="text-center py-8">
            <v-icon icon="mdi-robot" size="60" color="grey-lighten-1" class="mb-4" />
            <p class="text-grey">{{ t('agent.agents.empty') }}</p>
          </v-card-text>

          <v-container fluid v-else>
            <v-row>
              <v-col
                v-for="agent in filteredAgents"
                :key="agent.name"
                cols="12"
                sm="6"
                md="4"
                lg="3"
              >
                <AgentCard
                  :agent="agent"
                  @edit="openEditor"
                  @test="openTester"
                  @copy="copyAgent"
                  @delete="deleteAgent"
                  @toggle="toggleAgent"
                  @reset="resetBuiltinAgent"
                  @viewDetail="openAgentDetail"
                />
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-col>
    </v-row>

    <!-- 智能体编辑器 -->
    <AgentEditor
      v-model="showEditor"
      :agent="editingAgent"
      :is-editing="isEditing"
      @save="handleSaveAgent"
    />

    <!-- 智能体测试器 -->
    <AgentTester
      v-model="showTester"
      :agent="testingAgent"
    />

    <!-- 模板选择对话框 -->
    <v-dialog v-model="showTemplatesDialog" max-width="800">
      <v-card>
        <v-card-title>{{ t('agent.agents.templates.title') }}</v-card-title>
        <v-card-text>
          <v-row>
            <v-col
              v-for="template in templates"
              :key="template.name"
              cols="12"
              sm="6"
              md="4"
            >
              <v-card hover @click="createFromTemplate(template)">
                <v-card-title class="text-subtitle-1">
                  <v-icon :icon="template.icon" class="mr-2" />
                  {{ template.name }}
                </v-card-title>
                <v-card-text>
                  <p class="text-body-2 text-grey">{{ template.description }}</p>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showTemplatesDialog = false">{{ t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 导入对话框 -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ t('agent.agents.import.title') }}</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="importFile"
            :label="t('agent.agents.import.selectFile')"
            accept=".json"
            prepend-icon="mdi-file-json"
            show-size
          />
          <v-alert type="info" variant="tonal" class="mt-4">
            {{ t('agent.agents.import.hint') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">
            {{ t('agent.agents.import.button') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 智能体详情浮窗 -->
    <v-dialog v-model="showDetailDialog" max-width="700">
      <v-card v-if="detailAgent">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-robot" class="mr-2" color="primary" />
          {{ detailAgent.name }}
          <v-chip
            v-if="detailAgent.agent_type === 'builtin'"
            size="small"
            color="amber-darken-2"
            variant="tonal"
            class="ml-2"
          >
            {{ t('agent.agents.type.builtin') }}
          </v-chip>
          <v-chip
            v-if="detailAgent.agent_type === 'expert'"
            size="small"
            color="purple"
            variant="tonal"
            class="ml-2"
          >
            {{ t('agent.agents.type.expert') }}
          </v-chip>
          <v-chip
            :color="detailAgent.enabled ? 'success' : 'grey'"
            size="small"
            class="ml-2"
          >
            {{ detailAgent.enabled ? t('agent.agents.status.enabled') : t('agent.agents.status.disabled') }}
          </v-chip>
          <v-spacer />
          <v-btn icon variant="text" @click="showDetailDialog = false">
            <v-icon icon="mdi-close" />
          </v-btn>
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4" style="max-height: 65vh; overflow-y: auto;">
          <div v-if="detailAgent.soul" class="mb-4">
            <div class="text-subtitle-2 mb-1">{{ t('agent.agents.editor.soul') }}</div>
            <p class="text-body-2">{{ detailAgent.soul }}</p>
          </div>

          <div v-if="detailAgent.provider_id || detailAgent.model_name" class="mb-4">
            <div class="text-subtitle-2 mb-1">模型配置</div>
            <v-chip size="small" variant="tonal" color="info" class="mr-1">
              <v-icon icon="mdi-robot" start size="x-small" />
              {{ detailAgent.provider_id }} / {{ detailAgent.model_name }}
            </v-chip>
          </div>

          <div v-if="detailAgent.tools && detailAgent.tools.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">工具列表</div>
            <v-chip
              v-for="tool in detailAgent.tools"
              :key="tool"
              size="small"
              color="primary"
              variant="tonal"
              class="mr-1 mb-1"
            >
              <v-icon icon="mdi-tools" start size="x-small" />
              {{ tool }}
            </v-chip>
          </div>

          <div v-if="detailAgent.skills && detailAgent.skills.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">技能列表</div>
            <v-chip
              v-for="skill in detailAgent.skills"
              :key="skill"
              size="small"
              color="success"
              variant="tonal"
              class="mr-1 mb-1"
            >
              <v-icon icon="mdi-lightning-bolt" start size="x-small" />
              {{ skill }}
            </v-chip>
          </div>

          <div v-if="detailAgent.knowledge_id" class="mb-4">
            <div class="text-subtitle-2 mb-2">知识库</div>
            <v-chip size="small" color="info" variant="tonal">
              <v-icon icon="mdi-database" start size="x-small" />
              {{ detailAgent.knowledge_id }}
            </v-chip>
          </div>

          <div v-if="detailAgent.planning" class="mb-4">
            <div class="text-subtitle-2 mb-2">Planning 配置</div>
            <v-table density="compact" class="bg-grey-lighten-4">
              <tbody>
                <tr>
                  <td class="text-caption font-weight-medium">启用</td>
                  <td class="text-caption">{{ detailAgent.planning.enabled ? '是' : '否' }}</td>
                </tr>
                <tr v-if="detailAgent.planning.maxSteps">
                  <td class="text-caption font-weight-medium">最大步骤</td>
                  <td class="text-caption">{{ detailAgent.planning.maxSteps }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>

          <div v-if="detailAgent.memory_config && Object.keys(detailAgent.memory_config).length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">Memory 配置</div>
            <v-table density="compact" class="bg-grey-lighten-4">
              <tbody>
                <tr v-for="(value, key) in detailAgent.memory_config" :key="key">
                  <td class="text-caption font-weight-medium">{{ key }}</td>
                  <td class="text-caption">{{ typeof value === 'object' ? JSON.stringify(value) : value }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>

          <div v-if="detailAgent.system_prompt" class="mb-4">
            <div class="text-subtitle-2 mb-1">系统提示词</div>
            <v-alert variant="tonal" color="grey" class="text-body-2" style="white-space: pre-wrap;">
              {{ detailAgent.system_prompt }}
            </v-alert>
          </div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="outlined" @click="showDetailDialog = false">
            {{ t('common.close') }}
          </v-btn>
          <v-btn color="info" @click="showDetailDialog = false; openTester(detailAgent)">
            <v-icon start icon="mdi-chat" />
            对话
          </v-btn>
          <v-btn
            v-if="detailAgent.agent_type === 'custom'"
            color="primary"
            @click="showDetailDialog = false; openEditor(detailAgent)"
          >
            <v-icon start icon="mdi-pencil" />
            编辑
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 确认删除对话框 -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ t('agent.agents.delete.title') }}</v-card-title>
        <v-card-text>
          {{ t('agent.agents.delete.confirm', { name: deletingAgent?.name }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showDeleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" @click="confirmDelete" :loading="deleting">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 重置确认对话框 -->
    <v-dialog v-model="showResetDialog" max-width="450">
      <v-card>
        <v-card-title>
          <v-icon icon="mdi-restore" class="mr-2" color="amber-darken-2" />
          {{ t('agent.agents.reset.title') }}
        </v-card-title>
        <v-card-text>
          <p class="mb-2">
            {{ t('agent.agents.reset.confirm', { name: resettingAgent?.name }) }}
          </p>
          <v-alert type="warning" variant="tonal" density="compact">
            {{ t('agent.agents.reset.warning') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showResetDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="amber-darken-2" @click="confirmReset" :loading="resetting">
            {{ t('agent.agents.reset.confirmButton') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 统一 LLM 配置对话框 -->
    <v-dialog v-model="showBatchLlmDialog" max-width="500">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-cog" class="mr-2" />
          {{ t('agent.agents.expert.batchLlmTitle') }}
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert type="info" variant="tonal" class="mb-4">
            {{ t('agent.agents.expert.batchLlmHint') }}
          </v-alert>
          <v-row>
            <v-col cols="12" sm="6">
              <v-select
                v-model="batchLlmForm.provider_id"
                :label="t('agent.agents.expert.provider')"
                :items="batchProviderOptions"
                item-title="title"
                item-value="value"
                variant="outlined"
                density="compact"
                :placeholder="t('agent.agents.expert.selectProvider')"
                @update:model-value="onBatchProviderChange"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select
                v-model="batchLlmForm.model_name"
                :label="t('agent.agents.expert.model')"
                :items="batchModelOptions"
                item-title="title"
                item-value="value"
                variant="outlined"
                density="compact"
                :placeholder="t('agent.agents.expert.selectModel')"
                :disabled="!batchLlmForm.provider_id"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="outlined" @click="showBatchLlmDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn
            color="primary"
            @click="executeBatchLlm"
            :loading="batchLlmLoading"
            :disabled="!batchLlmForm.provider_id || !batchLlmForm.model_name"
          >
            <v-icon icon="mdi-check" start />
            {{ t('agent.agents.expert.batchLlmApply') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

  </v-container>

</template>

<script setup lang="ts">

import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import AgentCard from './AgentCard.vue';
import AgentEditor from './AgentEditor.vue';
import AgentTester from './AgentTester.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

// 状态
const loading = ref(false);
const agents = ref<any[]>([]);
const activeTab = ref('all');
const searchQuery = ref('');

// 编辑
const showEditor = ref(false);
const editingAgent = ref<any>(null);
const isEditing = ref(false);

// 测试
const showTester = ref(false);
const testingAgent = ref<any>(null);

// 删除
const showDeleteDialog = ref(false);
const deletingAgent = ref<any>(null);
const deleting = ref(false);

// 导入
const showImportDialog = ref(false);
const importFile = ref<File | null>(null);
const importing = ref(false);

// 模板
const showTemplatesDialog = ref(false);
const templates = ref([
  {
    name: t('agent.agents.templates.assistant.name'),
    icon: 'mdi-robot',
    description: t('agent.agents.templates.assistant.description'),
    config: {
      soul: t('agent.agents.templates.assistant.soul'),
      tools: [],
      skills: [],
      knowledgeBases: [],
      planning: { enabled: false, maxSteps: 5 },
      memory: { enabled: true, type: 'short_term', maxMessages: 20 },
    },
  },
  {
    name: t('agent.agents.templates.researcher.name'),
    icon: 'mdi-magnify',
    description: t('agent.agents.templates.researcher.description'),
    config: {
      soul: t('agent.agents.templates.researcher.soul'),
      tools: [],
      skills: [],
      knowledgeBases: [],
      planning: { enabled: true, maxSteps: 10 },
      memory: { enabled: true, type: 'long_term', maxMessages: 50 },
    },
  },
  {
    name: t('agent.agents.templates.coder.name'),
    icon: 'mdi-code-braces',
    description: t('agent.agents.templates.coder.description'),
    config: {
      soul: t('agent.agents.templates.coder.soul'),
      tools: [],
      skills: [],
      knowledgeBases: [],
      planning: { enabled: true, maxSteps: 8 },
      memory: { enabled: true, type: 'short_term', maxMessages: 30 },
    },
  },
]);

// 重置
const resettingAgent = ref<any>(null);
const showResetDialog = ref(false);
const resetting = ref(false);

// 详情
const showDetailDialog = ref(false);
const detailAgent = ref<any>(null);

// 专家团相关
const selectedExpertCategory = ref('all');

// 统一 LLM 配置
const showBatchLlmDialog = ref(false);
const batchLlmLoading = ref(false);
const batchLlmForm = ref({
  provider_id: '',
  model_name: '',
});

const batchProviderOptions = ref<any[]>([]);
const batchModelOptions = ref<any[]>([]);
const batchProvidersMap = ref<Map<string, any>>(new Map());

// 专家分类列表（从后端 API 加载）
const expertCategoryList = ref<any[]>([]);

// 分类颜色映射
const categoryColorMap: Record<string, string> = {
  engineering: 'blue',
  product: 'orange',
  design: 'purple',
  marketing: 'green',
  security: 'red',
  finance: 'teal',
  game: 'indigo',
  sales: 'cyan',
  testing: 'pink',
  support: 'light-blue',
  project: 'brown',
  academic: 'indigo',
  specialized: 'amber',
  paid_media: 'deep-purple',
  spatial: 'blue-grey',
};

function getCategoryColor(category: string): string {
  return categoryColorMap[category] || 'grey';
}

function getCategoryLabel(category: string): string {
  const cat = expertCategoryList.value.find(c => c.key === category);
  return cat ? cat.label : category;
}

function getExpertCategoryCount(category: string): number {
  return expertAgents.value.filter(a => a.metadata?.category === category).length;
}

// 计算属性
const filteredAgents = computed(() => {
  let result = agents.value;

  if (activeTab.value === 'builtin') {
    result = result.filter(agent => (agent.agent_type || 'custom') === 'builtin');
  } else if (activeTab.value === 'custom') {
    result = result.filter(agent => {
      const type = agent.agent_type || 'custom';
      return type === 'custom';
    });
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(agent =>
      agent.name.toLowerCase().includes(query) ||
      (agent.soul && agent.soul.toLowerCase().includes(query))
    );
  }

  return result;
});

// 专家类型智能体列表
const expertAgents = computed(() => {
  let result = agents.value.filter(agent => (agent.agent_type || 'custom') === 'expert');

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(agent =>
      agent.name.toLowerCase().includes(query) ||
      (agent.soul && agent.soul.toLowerCase().includes(query))
    );
  }

  return result;
});

// 按分类筛选后的专家agent
const filteredExpertAgents = computed(() => {
  if (selectedExpertCategory.value === 'all') {
    return expertAgents.value;
  }
  return expertAgents.value.filter(a => a.metadata?.category === selectedExpertCategory.value);
});

// 加载智能体列表
async function loadAgents() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/agents');
    if (response.data.status === 'ok') {
      agents.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load agents:', error);
  } finally {
    loading.value = false;
  }
}

async function loadExpertCategories() {
  try {
    const response = await axios.get('/api/plug/agent/experts/categories');
    if (response.data.status === 'ok') {
      expertCategoryList.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load expert categories:', error);
  }
}

// 加载 Provider 列表
async function loadProviders() {
  try {
    const response = await axios.get('/api/config/provider/list', {
      params: { provider_type: 'chat_completion' }
    });
    if (response.data.status === 'ok') {
      const providers = (response.data.data || [])
        .filter((provider: any) => provider.enable !== false);

      batchProviderOptions.value = providers.map((provider: any) => ({
        title: provider.name || provider.id,
        value: provider.id,
      }));

      batchProvidersMap.value.clear();
      providers.forEach((provider: any) => {
        batchProvidersMap.value.set(provider.id, provider);
      });
    }
  } catch (error) {
    console.error('Failed to load providers:', error);
  }
}

function onBatchProviderChange(providerId: string) {
  batchLlmForm.value.model_name = '';
  batchModelOptions.value = [];

  const provider = batchProvidersMap.value.get(providerId);
  if (provider && provider.model) {
    const models = Array.isArray(provider.model) ? provider.model : [provider.model];
    batchModelOptions.value = models.map((m: string) => ({
      title: m,
      value: m,
    }));
  }
}

// 打开添加编辑器
function openAddEditor() {
  editingAgent.value = null;
  isEditing.value = false;
  showEditor.value = true;
}

// 打开编辑器
function openEditor(agent: any) {
  editingAgent.value = { ...agent };
  isEditing.value = true;
  showEditor.value = true;
}

// 打开测试器
function openTester(agent: any) {
  testingAgent.value = agent;
  showTester.value = true;
}

// 打开智能体详情
async function openAgentDetail(agent: any) {
  detailAgent.value = agent;
  showDetailDialog.value = true;

  try {
    const agentId = agent.id || agent.name;
    const response = await axios.get(`/api/plug/agent/agents/${encodeURIComponent(agentId)}`);
    if (response.data.status === 'ok' && response.data.data) {
      detailAgent.value = { ...agent, ...response.data.data };
    }
  } catch (error) {
    console.error('Failed to load agent detail:', error);
  }
}

// 复制智能体
async function copyAgent(agent: any) {
  const newAgent = {
    ...agent,
    name: `${agent.name}_copy`,
  };
  delete (newAgent as any).id;

  try {
    await axios.post('/api/plug/agent/agents/add', newAgent);
    await loadAgents();
  } catch (error: any) {
    console.error('Failed to copy agent:', error);
    alert(error.response?.data?.message || t('agent.agents.messages.copyError'));
  }
}

// 删除智能体
function deleteAgent(agent: any) {
  deletingAgent.value = agent;
  showDeleteDialog.value = true;
}

// 确认删除
async function confirmDelete() {
  if (!deletingAgent.value) return;

  deleting.value = true;
  try {
    await axios.post('/api/plug/agent/agents/delete', {
      id: deletingAgent.value.id,
    });
    agents.value = agents.value.filter(a => a.id !== deletingAgent.value.id);
    showDeleteDialog.value = false;
    deletingAgent.value = null;
  } catch (error: any) {
    console.error('Failed to delete agent:', error);
    alert(error.response?.data?.message || t('agent.agents.messages.deleteError'));
  } finally {
    deleting.value = false;
  }
}

// 切换智能体状态
async function toggleAgent(agent: any) {
  try {
    await axios.post('/api/plug/agent/agents/toggle', {
      id: agent.id,
    });
  } catch (error) {
    console.error('Failed to toggle agent:', error);
    agent.enabled = !agent.enabled;
  }
}

// 重置智能体
function resetBuiltinAgent(agent: any) {
  resettingAgent.value = agent;
  showResetDialog.value = true;
}

async function confirmReset() {
  if (!resettingAgent.value) return;
  resetting.value = true;
  try {
    const response = await axios.post('/api/plug/agent/agents/reset-builtin', {
      id: resettingAgent.value.id,
    });
    if (response.data.status === 'ok') {
      const resetAgent = response.data.data;
      const idx = agents.value.findIndex(a => a.id === resetAgent.id);
      if (idx !== -1) {
        agents.value[idx] = resetAgent;
      }
      showResetDialog.value = false;
      resettingAgent.value = null;
    } else {
      alert(response.data.message || t('agent.agents.reset.failed'));
    }
  } catch (error: any) {
    console.error('Failed to reset builtin agent:', error);
    alert(error.response?.data?.message || t('agent.agents.reset.failed'));
  } finally {
    resetting.value = false;
  }
}

// 保存智能体
async function handleSaveAgent(agentData: any) {
  try {
    if (isEditing.value) {
      await axios.post('/api/plug/agent/agents/update', agentData);
    } else {
      await axios.post('/api/plug/agent/agents/add', agentData);
    }
    showEditor.value = false;
    await loadAgents();
  } catch (error: any) {
    console.error('Failed to save agent:', error);
    throw error;
  }
}

// 从模板创建
async function createFromTemplate(template: any) {
  editingAgent.value = {
    name: '',
    ...template.config,
    model: {
      provider: '',
      name: '',
      temperature: 0.7,
      maxTokens: 4096,
      topP: 1.0,
    },
    behavior: {
      maxRetries: 3,
      timeout: 60,
      verbose: false,
    },
    enabled: true,
  };
  isEditing.value = false;
  showTemplatesDialog.value = false;
  showEditor.value = true;
}

// 以专家为模板创建自定义agent
async function createFromExpert(agent: any) {
  try {
    const response = await axios.post('/api/plug/agent/agents/create-from-expert', {
      id: agent.id,
    });
    if (response.data.status === 'ok') {
      await loadAgents();
    } else {
      alert(response.data.message || t('agent.agents.expert.createFailed'));
    }
  } catch (error: any) {
    console.error('Failed to create from expert:', error);
    alert(error.response?.data?.message || t('agent.agents.expert.createFailed'));
  }
}

// 导入智能体
function importAgents() {
  importFile.value = null;
  showImportDialog.value = true;
}

async function executeImport() {
  if (!importFile.value) return;

  importing.value = true;
  try {
    const text = await importFile.value.text();
    const data = JSON.parse(text);

    await axios.post('/api/plug/agent/agents/import', { agents: data });
    showImportDialog.value = false;
    await loadAgents();
  } catch (error: any) {
    console.error('Failed to import agents:', error);
    alert(error.response?.data?.message || t('agent.agents.messages.importError'));
  } finally {
    importing.value = false;
  }
}

// 导出智能体
function exportAgents() {
  const data = JSON.stringify(agents.value, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `agents_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// 打开统一 LLM 配置对话框
function openBatchLlmDialog() {
  batchLlmForm.value = {
    provider_id: '',
    model_name: '',
  };
  showBatchLlmDialog.value = true;
}

// 执行统一 LLM 配置
async function executeBatchLlm() {
  batchLlmLoading.value = true;
  try {
    const response = await axios.post('/api/plug/agent/experts/batch-llm', {
      provider_id: batchLlmForm.value.provider_id,
      model_name: batchLlmForm.value.model_name,
    });
    if (response.data.status === 'ok') {
      showBatchLlmDialog.value = false;
      await loadAgents();
    } else {
      alert(response.data.message || t('agent.agents.expert.batchLlmFailed'));
    }
  } catch (error: any) {
    console.error('Failed to batch update LLM:', error);
    alert(error.response?.data?.message || t('agent.agents.expert.batchLlmFailed'));
  } finally {
    batchLlmLoading.value = false;
  }
}

onMounted(async () => {
  loadAgents();
  loadProviders();
  await loadExpertCategories();
});

</script>

<style scoped>
.v-card {
  border-radius: 12px;
}

.chip-scroll-container {
  overflow-x: auto;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
}

.chip-scroll-container :deep(.v-chip-group) {
  flex-wrap: nowrap;
}

.agent-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
}

.agent-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.description-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}
</style>
