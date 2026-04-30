<template>
  <v-container fluid class="pa-6">
    <v-card class="mb-6">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-account-group" class="mr-2" />
        {{ t('expertTeam.title') }}
      </v-card-title>
      <v-card-subtitle>
        {{ t('expertTeam.description') }}
      </v-card-subtitle>
    </v-card>

    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-text class="pb-2">
            <v-text-field
              v-model="searchQuery"
              :placeholder="t('expertTeam.search')"
              prepend-inner-icon="mdi-magnify"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              class="mb-3"
              style="max-width: 400px;"
            />
            <v-tabs
              v-model="activeCategory"
              color="primary"
              show-arrows="false"
            >
              <v-tab
                v-for="cat in expertCategories"
                :key="cat.key"
                :value="cat.key"
              >
                <v-icon :icon="cat.icon" start size="small" />
                {{ t(cat.label) }}
                <v-chip
                  v-if="cat.key !== 'all'"
                  size="x-small"
                  class="ml-1"
                  variant="flat"
                  color="primary"
                >
                  {{ getCategoryCount(cat.key) }}
                </v-chip>
              </v-tab>
            </v-tabs>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-text v-if="filteredExperts.length === 0" class="text-center py-8">
            <v-icon icon="mdi-account-search" size="60" color="grey-lighten-1" class="mb-4" />
            <p class="text-grey">{{ t('expertTeam.noResults') }}</p>
          </v-card-text>

          <v-container fluid v-else>
            <v-row>
              <v-col
                v-for="expert in filteredExperts"
                :key="expert.id"
                cols="12"
                sm="6"
                md="4"
                lg="3"
              >
                <ExpertCard
                  :expert="expert"
                  @preview="openPreview"
                  @create="createFromTemplate"
                />
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog v-model="showPreview" max-width="800" scrollable>
      <v-card v-if="previewExpert">
        <v-card-title class="d-flex align-center">
          <v-avatar :color="getCategoryColor(previewExpert.category)" size="40" class="mr-3">
            <v-icon :icon="previewExpert.icon" color="white" size="small" />
          </v-avatar>
          {{ previewExpert.name }}
          <v-spacer />
          <v-btn icon variant="text" @click="showPreview = false">
            <v-icon icon="mdi-close" />
          </v-btn>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <div class="mb-4">
            <div class="text-subtitle-1 font-weight-bold mb-1">{{ t('expertTeam.role') }}</div>
            <p class="text-body-2">{{ previewExpert.role }}</p>
          </div>

          <div class="mb-4">
            <div class="text-subtitle-1 font-weight-bold mb-1">{{ t('expertTeam.goal') }}</div>
            <p class="text-body-2">{{ previewExpert.goal }}</p>
          </div>

          <div class="mb-4">
            <div class="d-flex flex-wrap" style="gap: 4px;">
              <v-chip
                v-for="tag in previewExpert.tags"
                :key="tag"
                size="small"
                variant="outlined"
                color="primary"
              >
                {{ tag }}
              </v-chip>
            </div>
          </div>

          <v-divider class="mb-4" />

          <div class="backstory-content text-body-2" v-html="renderedBackstory" />
        </v-card-text>

        <v-divider />

        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="outlined" @click="showPreview = false">
            {{ t('common.close') }}
          </v-btn>
          <v-btn color="primary" @click="createFromTemplate(previewExpert)">
            <v-icon icon="mdi-plus" start />
            {{ t('expertTeam.createAgent') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <AgentEditor
      v-model="showEditor"
      :agent="editingAgent"
      :is-editing="false"
      @save="handleSaveAgent"
    />
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import ExpertCard from './ExpertCard.vue';
import AgentEditor from '../agents/AgentEditor.vue';
import { expertTemplates, expertCategories, type ExpertTemplate } from './expertTemplates';

const { t } = useI18n();

const activeCategory = ref('all');
const searchQuery = ref('');
const showPreview = ref(false);
const previewExpert = ref<ExpertTemplate | null>(null);
const showEditor = ref(false);
const editingAgent = ref<any>(null);

const categoryColorMap: Record<string, string> = {
  engineering: 'blue',
  product: 'orange',
  design: 'purple',
  marketing: 'green',
  security: 'red',
  finance: 'teal',
  game: 'indigo',
  specialized: 'amber',
};

function getCategoryColor(category: string): string {
  return categoryColorMap[category] || 'grey';
}

function getCategoryCount(category: string): number {
  return expertTemplates.filter(e => e.category === category).length;
}

const filteredExperts = computed(() => {
  let result = expertTemplates;

  if (activeCategory.value !== 'all') {
    result = result.filter(e => e.category === activeCategory.value);
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(e =>
      e.name.toLowerCase().includes(query) ||
      e.role.toLowerCase().includes(query) ||
      e.tags.some(tag => tag.toLowerCase().includes(query))
    );
  }

  return result;
});

const renderedBackstory = computed(() => {
  if (!previewExpert.value) return '';
  let text = previewExpert.value.backstory;

  text = text.replace(/\\`\\`\\`(\w*)\n([\s\S]*?)\\`\\`\\`/g, (_match, lang, code) => {
    const escapedCode = code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    return `<pre class="backstory-code-block${lang ? ` language-${lang}` : ''}"><code>${escapedCode}</code></pre>`;
  });

  const parts = text.split(/(<pre class="backstory-code-block[\s\S]*?<\/pre>)/g);
  text = parts.map((part) => {
    if (part.startsWith('<pre class="backstory-code-block')) return part;
    return part
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }).join('');

  text = text.replace(/^&gt;\s*(.+)$/gm, '<blockquote class="backstory-quote">$1</blockquote>');
  text = text.replace(/<\/blockquote>\n<blockquote class="backstory-quote">/g, '<br>');

  text = text.replace(/\\`([^`\n]+)\\`/g, '<code class="backstory-inline-code">$1</code>');

  text = text.replace(/^### (.+)$/gm, '<h4 class="backstory-h4">$1</h4>');
  text = text.replace(/^## (.+)$/gm, '<h3 class="backstory-h3">$1</h3>');

  text = text.replace(/^(🎭|🎯|⚠️|📋|🔄|💬|🧠|📊|🚀)/gm, '<strong class="backstory-section-title">$1</strong>');

  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  const parts2 = text.split(/(<pre class="backstory-code-block[\s\S]*?<\/pre>)/g);
  text = parts2.map((part) => {
    if (part.startsWith('<pre class="backstory-code-block')) return part;
    return part.replace(/\n/g, '<br>');
  }).join('');

  return text;
});

function openPreview(expert: ExpertTemplate) {
  previewExpert.value = expert;
  showPreview.value = true;
}

function createFromTemplate(expert: ExpertTemplate) {
  showPreview.value = false;
  editingAgent.value = {
    name: '',
    role: expert.role,
    goal: expert.goal,
    backstory: expert.backstory,
    tools: [],
    skills: [],
    knowledge_id: null,
    provider_id: '',
    model_name: '',
    llm_config: {
      provider: '',
      name: '',
      temperature: 0.7,
      maxTokens: 4096,
      topP: 1.0,
    },
    memory_config: {
      enabled: expert.memory?.enabled ?? true,
      type: expert.memory?.type === 'long_term' ? 'long_term' : 'short_term',
      maxMessages: expert.memory?.maxMessages ?? 20,
    },
    planning: expert.planning?.enabled ?? true,
    planning_effort: 'medium',
    max_iter: expert.planning?.maxSteps ?? 6,
    max_rpm: null,
    verbose: false,
    allow_delegation: false,
    enabled: true,
    metadata: {},
  };
  showEditor.value = true;
}

async function handleSaveAgent(agentData: any) {
  try {
    // 转换前端数据结构为后端期望的格式
    const payload = {
      name: agentData.name,
      role: agentData.role,
      goal: agentData.goal,
      backstory: agentData.backstory,
      tools: agentData.tools || [],
      skills: agentData.skills || [],
      knowledge_id: agentData.knowledge_id || agentData.knowledgeBases?.[0] || null,
      provider_id: agentData.provider_id || agentData.model?.provider || '',
      model_name: agentData.model_name || agentData.model?.name || '',
      llm_config: agentData.llm_config || {
        temperature: agentData.model?.temperature ?? 0.7,
        maxTokens: agentData.model?.maxTokens ?? 4096,
        topP: agentData.model?.topP ?? 1.0,
      },
      memory_config: agentData.memory_config || {
        enabled: agentData.memory?.enabled ?? false,
        type: agentData.memory?.type || 'short_term',
        maxMessages: agentData.memory?.maxMessages ?? 20,
      },
      planning: agentData.planning?.enabled ?? agentData.planning ?? false,
      planning_effort: agentData.planning_effort || 'medium',
      max_iter: agentData.planning?.maxSteps ?? agentData.max_iter ?? 5,
      max_rpm: agentData.max_rpm || null,
      verbose: agentData.behavior?.verbose ?? agentData.verbose ?? false,
      allow_delegation: agentData.allow_delegation ?? false,
      enabled: agentData.enabled ?? true,
      metadata: agentData.metadata || {},
    };
    await axios.post('/api/plug/agent/agents/add', payload);
    showEditor.value = false;
  } catch (error: any) {
    console.error('Failed to save agent:', error);
    throw error;
  }
}
</script>

<style scoped>
.v-card {
  border-radius: 12px;
}

.backstory-content {
  line-height: 1.8;
  white-space: normal;
}

.backstory-content :deep(strong) {
  display: inline;
}

.backstory-content :deep(.backstory-code-block) {
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: 'Fira Code', 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre;
  border: 1px solid #313244;
}

.backstory-content :deep(.backstory-code-block code) {
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  background: none;
  padding: 0;
}

.backstory-content :deep(.backstory-quote) {
  border-left: 4px solid rgb(var(--v-theme-primary));
  padding: 8px 16px;
  margin: 8px 0;
  background: rgba(var(--v-theme-primary), 0.05);
  border-radius: 0 8px 8px 0;
  font-style: italic;
  color: rgba(0, 0, 0, 0.7);
}

.backstory-content :deep(.backstory-inline-code) {
  background: rgba(var(--v-theme-primary), 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', 'Courier New', monospace;
  font-size: 0.9em;
  color: rgb(var(--v-theme-primary));
}

.backstory-content :deep(.backstory-section-title) {
  font-size: 1.1em;
  display: inline;
}

.backstory-content :deep(.backstory-h3) {
  font-size: 1.1em;
  margin: 16px 0 8px;
  font-weight: 600;
}

.backstory-content :deep(.backstory-h4) {
  font-size: 1em;
  margin: 12px 0 6px;
  font-weight: 600;
}
</style>
