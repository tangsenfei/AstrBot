<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <v-card class="crew-editor">
      <v-toolbar color="primary" dark density="prominent">
        <v-btn icon dark @click="handleClose">
          <v-icon icon="mdi-close" />
        </v-btn>
        <v-toolbar-title>
          <v-icon icon="mdi-account-group" class="mr-2" />
          {{ isEditing ? $t('agent.crews.editor.editTitle') : $t('agent.crews.editor.addTitle') }}
        </v-toolbar-title>
        <v-spacer />
        <v-btn variant="outlined" @click="handleClose" class="mr-2">
          {{ $t('common.cancel') }}
        </v-btn>
        <v-btn
          color="white"
          @click="handleSave"
          :loading="saving"
          :disabled="!formValid"
        >
          {{ $t('common.save') }}
        </v-btn>
      </v-toolbar>

      <v-container fluid class="pa-6">
        <v-row>
          <v-col cols="12" md="6">
            <v-card class="mb-4">
              <v-card-title>
                <v-icon icon="mdi-information" class="mr-2" />
                {{ $t('agent.crews.editor.basicInfo') }}
              </v-card-title>
              <v-card-text>
                <v-text-field
                  v-model="formData.name"
                  :label="$t('agent.crews.editor.basic.name')"
                  :rules="[rules.required]"
                  :disabled="isEditing"
                  :hint="$t('agent.crews.editor.basic.nameHint')"
                  persistent-hint
                  class="mb-3"
                />
                <v-textarea
                  v-model="formData.description"
                  :label="$t('agent.crews.editor.basic.description')"
                  :hint="$t('agent.crews.editor.basic.descriptionHint')"
                  persistent-hint
                  rows="3"
                  auto-grow
                />
              </v-card-text>
            </v-card>

            <v-card class="mb-4">
              <v-card-title>
                <v-icon icon="mdi-cog" class="mr-2" />
                {{ $t('agent.crews.editor.process.title') }}
              </v-card-title>
              <v-card-text>
                <v-radio-group v-model="formData.process" class="mb-3">
                  <v-radio value="sequential">
                    <template v-slot:label>
                      <div>
                        <div class="text-subtitle-1">{{ $t('agent.crews.editor.process.sequential') }}</div>
                        <div class="text-caption text-grey">{{ $t('agent.crews.editor.process.sequentialHint') }}</div>
                      </div>
                    </template>
                  </v-radio>
                  <v-radio value="hierarchical">
                    <template v-slot:label>
                      <div>
                        <div class="text-subtitle-1">{{ $t('agent.crews.editor.process.hierarchical') }}</div>
                        <div class="text-caption text-grey">{{ $t('agent.crews.editor.process.hierarchicalHint') }}</div>
                      </div>
                    </template>
                  </v-radio>
                </v-radio-group>
                <v-select
                  v-if="formData.process === 'hierarchical'"
                  v-model="formData.manager_llm"
                  :items="availableModels"
                  :label="$t('agent.crews.editor.process.managerLLM')"
                  :hint="$t('agent.crews.editor.process.managerLLMHint')"
                  persistent-hint
                />
              </v-card-text>
            </v-card>

            <v-card class="mb-4">
              <v-card-title>
                <v-icon icon="mdi-tune-vertical" class="mr-2" />
                {{ $t('agent.crews.editor.advanced.title') }}
              </v-card-title>
              <v-card-text>
                <v-switch
                  v-model="formData.memory.enabled"
                  :label="$t('agent.crews.editor.advanced.enableMemory')"
                  color="primary"
                  class="mb-2"
                />
                <v-text-field
                  v-if="formData.memory.enabled"
                  v-model="formData.memory.max_messages"
                  :label="$t('agent.crews.editor.advanced.maxMessages')"
                  type="number"
                  :min="1"
                  :max="100"
                  class="mb-3"
                />
                <v-divider class="my-3" />
                <v-switch
                  v-model="formData.cache.enabled"
                  :label="$t('agent.crews.editor.advanced.enableCache')"
                  color="primary"
                  class="mb-2"
                />
                <v-divider class="my-3" />
                <v-text-field
                  v-model="formData.max_rpm"
                  :label="$t('agent.crews.editor.advanced.maxRPM')"
                  type="number"
                  :min="1"
                  :hint="$t('agent.crews.editor.advanced.maxRPMHint')"
                  persistent-hint
                  class="mb-3"
                />
                <v-switch
                  v-model="formData.share_agent_output"
                  :label="$t('agent.crews.editor.advanced.shareOutput')"
                  color="primary"
                  class="mb-2"
                />
                <v-alert v-if="formData.share_agent_output" type="info" variant="tonal" density="compact">
                  {{ $t('agent.crews.editor.advanced.shareOutputHint') }}
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card class="mb-4">
              <v-card-title class="d-flex align-center">
                <v-icon icon="mdi-robot" class="mr-2" />
                {{ $t('agent.crews.editor.agents.title') }}
                <v-spacer />
                <v-chip size="small" variant="tonal" color="primary">
                  {{ formData.agents.length }} 个成员
                </v-chip>
              </v-card-title>
              <v-card-text>
                <AgentSelector v-if="modelValue" v-model="formData.agents" />
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import axios from 'axios';
import { useI18n } from 'vue-i18n';
import AgentSelector from '../components/AgentSelector.vue';

const props = defineProps<{
  modelValue: boolean;
  crew: any;
  isEditing: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', crewData: any): void;
}>();

const { t } = useI18n();

const formValid = ref(true);
const saving = ref(false);
const loadingModels = ref(false);

const availableModels = ref<any[]>([]);

const formData = ref({
  name: '',
  description: '',
  agents: [] as string[],
  process: 'sequential',
  manager_llm: '',
  memory: { enabled: false, max_messages: 20 },
  cache: { enabled: false },
  max_rpm: 100,
  share_agent_output: false,
});

const rules = {
  required: (v: string) => !!v || t('agent.crews.editor.validation.required'),
};

async function loadModels() {
  loadingModels.value = true;
  try {
    const response = await axios.get('/api/config/provider/list', {
      params: { provider_type: 'chat_completion' }
    });
    if (response.data.status === 'ok') {
      const providers = (response.data.data || []).filter((p: any) => p.enable !== false);
      const models: any[] = [];
      for (const provider of providers) {
        if (provider.model) {
          models.push({
            title: `${provider.name || provider.id} / ${provider.model}`,
            value: `${provider.id}:${provider.model}`,
          });
        }
      }
      availableModels.value = models;
    }
  } catch (error) {
    console.error('Failed to load providers:', error);
  } finally {
    loadingModels.value = false;
  }
}

watch(() => props.crew, (newCrew) => {
  if (newCrew) {
    formData.value = {
      name: newCrew.name || '',
      description: newCrew.description || '',
      agents: Array.isArray(newCrew.agents) ? newCrew.agents.map((a: any) => typeof a === 'string' ? a : a.value || a.name) : [],
      process: newCrew.process || 'sequential',
      manager_llm: newCrew.manager_llm || '',
      memory: { enabled: newCrew.memory?.enabled || false, max_messages: newCrew.memory?.max_messages || 20 },
      cache: { enabled: newCrew.cache?.enabled || false },
      max_rpm: newCrew.max_rpm || 100,
      share_agent_output: newCrew.share_agent_output || false,
    };
  } else {
    resetForm();
  }
}, { immediate: true });

function resetForm() {
  formData.value = {
    name: '',
    description: '',
    agents: [],
    process: 'sequential',
    manager_llm: '',
    memory: { enabled: false, max_messages: 20 },
    cache: { enabled: false },
    max_rpm: 100,
    share_agent_output: false,
  };
}

function handleClose() {
  emit('update:modelValue', false);
}

async function handleSave() {
  saving.value = true;
  try {
    const crewData = {
      ...formData.value,
    };
    await emit('save', crewData);
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadModels();
});
</script>

<style scoped>
.crew-editor {
  background: rgb(var(--v-theme-background));
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.agent-card {
  padding: 10px 12px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
}

.agent-card:hover {
  border-color: #93c5fd;
  background: #f0f9ff;
}

.agent-card.selected {
  border-color: #3b82f6;
  background: #eff6ff;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.2);
}

.selected-agents {
  padding: 4px 0;
}
</style>
