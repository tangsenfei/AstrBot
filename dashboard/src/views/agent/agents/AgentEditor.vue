<template>

  <v-navigation-drawer

    :model-value="modelValue"

    @update:model-value="$emit('update:modelValue', $event)"

    location="right"

    temporary

    width="800"

    class="agent-editor-drawer"

  >

    <v-card flat class="h-100 d-flex flex-column">

      <!-- 标题 -->

      <v-card-title class="d-flex align-center pa-4 border-b">

        <v-icon icon="mdi-robot" class="mr-2" />

        {{ isEditing ? $t('agent.agents.editor.editTitle') : $t('agent.agents.editor.addTitle') }}

        <v-spacer />

        <v-btn icon variant="text" @click="$emit('update:modelValue', false)">

          <v-icon icon="mdi-close" />

        </v-btn>

      </v-card-title>



      <!-- 标签-->

      <v-tabs v-model="activeTab" color="primary" class="border-b">

        <v-tab value="basic">{{ $t('agent.agents.editor.tabs.basic') }}</v-tab>

        <v-tab value="abilities">{{ $t('agent.agents.editor.tabs.abilities') }}</v-tab>

        <v-tab value="model">{{ $t('agent.agents.editor.tabs.model') }}</v-tab>

        <v-tab value="advanced">{{ $t('agent.agents.editor.tabs.advanced') }}</v-tab>

      </v-tabs>



      <!-- 表单内容 -->

      <v-card-text class="flex-grow-1 overflow-y-auto pa-4">

        <v-form ref="formRef" v-model="formValid">

          <v-window v-model="activeTab">

            <!-- 基本信息 -->

            <v-window-item value="basic">

              <v-text-field

                v-model="formData.name"

                :label="$t('agent.agents.editor.basic.name')"

                :rules="[rules.required]"

                :disabled="isEditing"

                :hint="$t('agent.agents.editor.basic.nameHint')"

                persistent-hint

                class="mb-3"

              />



              <v-text-field

                v-model="formData.role"

                :label="$t('agent.agents.editor.basic.role')"

                :rules="[rules.required]"

                :hint="$t('agent.agents.editor.basic.roleHint')"

                persistent-hint

                class="mb-3"

              />



              <v-textarea

                v-model="formData.goal"

                :label="$t('agent.agents.editor.basic.goal')"

                :hint="$t('agent.agents.editor.basic.goalHint')"

                persistent-hint

                rows="3"

                auto-grow

                class="mb-3"

              />



              <v-textarea

                v-model="formData.backstory"

                :label="$t('agent.agents.editor.basic.backstory')"

                :hint="$t('agent.agents.editor.basic.backstoryHint')"

                persistent-hint

                rows="4"

                auto-grow

                class="mb-3"

              />

            </v-window-item>



            <!-- 能力配置 -->

            <v-window-item value="abilities">

              <!-- 工具选择 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.abilities.tools') }}

              </div>

              <v-alert type="info" variant="tonal" class="mb-3" density="compact">

                {{ $t('agent.agents.editor.abilities.toolsHint') }}

              </v-alert>

              <v-select

                v-model="formData.tools"

                :items="availableTools"

                :label="$t('agent.agents.editor.abilities.selectTools')"

                multiple

                chips

                closable-chips

                :loading="loadingTools"

                class="mb-4"

              />



              <!-- 技能选择 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.abilities.skills') }}

              </div>

              <v-alert type="info" variant="tonal" class="mb-3" density="compact">

                {{ $t('agent.agents.editor.abilities.skillsHint') }}

              </v-alert>

              <v-select

                v-model="formData.skills"

                :items="availableSkills"

                :label="$t('agent.agents.editor.abilities.selectSkills')"

                multiple

                chips

                closable-chips

                :loading="loadingSkills"

                class="mb-4"

              />



              <!-- 知识库选择 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.abilities.knowledgeBases') }}

              </div>

              <v-alert type="info" variant="tonal" class="mb-3" density="compact">

                {{ $t('agent.agents.editor.abilities.knowledgeBasesHint') }}

              </v-alert>

              <v-select

                v-model="formData.knowledgeBases"

                :items="availableKnowledgeBases"

                :label="$t('agent.agents.editor.abilities.selectKnowledgeBases')"

                multiple

                chips

                closable-chips

                :loading="loadingKnowledgeBases"

                class="mb-4"

              />

            </v-window-item>



            <!-- 模型配置 -->

            <v-window-item value="model">

              <!-- 提供商选择 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.model.provider') }}

              </div>

              <v-select

                v-model="formData.model.provider"

                :items="providerOptions"

                :label="$t('agent.agents.editor.model.selectProvider')"

                :rules="[rules.required]"

                :loading="loadingProviders"

                class="mb-4"

                @update:model-value="loadModels"

              />



              <!-- 模型选择 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.model.model') }}

              </div>

              <v-select

                v-model="formData.model.name"

                :items="modelOptions"

                :label="$t('agent.agents.editor.model.selectModel')"

                :rules="[rules.required]"

                :loading="loadingModels"

                :disabled="!formData.model.provider"

                class="mb-4"

              />



              <v-divider class="my-4" />



              <!-- 参数调优 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.model.parameters') }}

              </div>



              <v-slider

                v-model="formData.model.temperature"

                :label="$t('agent.agents.editor.model.temperature')"

                :min="0"

                :max="2"

                :step="0.1"

                thumb-label

                class="mb-3"

              >

                <template v-slot:append>

                  <v-text-field

                    v-model="formData.model.temperature"

                    type="number"

                    style="width: 60px"

                    density="compact"

                    hide-details

                    variant="outlined"

                  />

                </template>

              </v-slider>



              <v-slider

                v-model="formData.model.maxTokens"

                :label="$t('agent.agents.editor.model.maxTokens')"

                :min="100"

                :max="32000"

                :step="100"

                thumb-label

                class="mb-3"

              >

                <template v-slot:append>

                  <v-text-field

                    v-model="formData.model.maxTokens"

                    type="number"

                    style="width: 80px"

                    density="compact"

                    hide-details

                    variant="outlined"

                  />

                </template>

              </v-slider>



              <v-slider

                v-model="formData.model.topP"

                :label="$t('agent.agents.editor.model.topP')"

                :min="0"

                :max="1"

                :step="0.05"

                thumb-label

                class="mb-3"

              >

                <template v-slot:append>

                  <v-text-field

                    v-model="formData.model.topP"

                    type="number"

                    style="width: 60px"

                    density="compact"

                    hide-details

                    variant="outlined"

                  />

                </template>

              </v-slider>

            </v-window-item>



            <!-- 高级配置 -->

            <v-window-item value="advanced">

              <!-- Planning 配置 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.advanced.planning') }}

              </div>

              <v-switch

                v-model="formData.planning.enabled"

                :label="$t('agent.agents.editor.advanced.enablePlanning')"

                color="primary"

                class="mb-2"

              />

              <v-alert v-if="formData.planning.enabled" type="info" variant="tonal" class="mb-3" density="compact">

                {{ $t('agent.agents.editor.advanced.planningHint') }}

              </v-alert>



              <v-text-field

                v-if="formData.planning.enabled"

                v-model="formData.planning.maxSteps"

                :label="$t('agent.agents.editor.advanced.maxSteps')"

                type="number"

                :min="1"

                :max="20"

                class="mb-4"

              />



              <v-divider class="my-4" />



              <!-- Memory 配置 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.advanced.memory') }}

              </div>

              <v-switch

                v-model="formData.memory.enabled"

                :label="$t('agent.agents.editor.advanced.enableMemory')"

                color="primary"

                class="mb-2"

              />

              <v-alert v-if="formData.memory.enabled" type="info" variant="tonal" class="mb-3" density="compact">

                {{ $t('agent.agents.editor.advanced.memoryHint') }}

              </v-alert>



              <v-select

                v-if="formData.memory.enabled"

                v-model="formData.memory.type"

                :items="memoryTypeOptions"

                :label="$t('agent.agents.editor.advanced.memoryType')"

                class="mb-3"

              />



              <v-text-field

                v-if="formData.memory.enabled"

                v-model="formData.memory.maxMessages"

                :label="$t('agent.agents.editor.advanced.maxMessages')"

                type="number"

                :min="1"

                :max="100"

                class="mb-4"

              />



              <v-divider class="my-4" />



              <!-- 行为参数 -->

              <div class="text-subtitle-1 font-weight-medium mb-3">

                {{ $t('agent.agents.editor.advanced.behavior') }}

              </div>



              <v-slider

                v-model="formData.behavior.maxRetries"

                :label="$t('agent.agents.editor.advanced.maxRetries')"

                :min="0"

                :max="5"

                :step="1"

                thumb-label

                class="mb-3"

              />



              <v-slider

                v-model="formData.behavior.timeout"

                :label="$t('agent.agents.editor.advanced.timeout')"

                :min="10"

                :max="300"

                :step="10"

                thumb-label

                class="mb-3"

              >

                <template v-slot:append>

                  <span class="text-caption">{{ $t('agent.agents.editor.advanced.seconds') }}</span>

                </template>

              </v-slider>



              <v-switch

                v-model="formData.behavior.verbose"

                :label="$t('agent.agents.editor.advanced.verbose')"

                color="primary"

                class="mb-2"

              />

            </v-window-item>

          </v-window>

        </v-form>

      </v-card-text>



      <!-- 操作按钮 -->

      <v-card-actions class="pa-4 border-t">

        <v-spacer />

        <v-btn variant="outlined" @click="$emit('update:modelValue', false)">

          {{ $t('common.cancel') }}

        </v-btn>

        <v-btn

          color="primary"

          @click="handleSave"

          :loading="saving"

          :disabled="!formValid"

        >

          {{ $t('common.save') }}

        </v-btn>

      </v-card-actions>

    </v-card>

  </v-navigation-drawer>

</template>



<script setup lang="ts">

import { ref, watch, onMounted } from 'vue';

import axios from 'axios';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  modelValue: boolean;

  agent: any;

  isEditing: boolean;

}>();



const emit = defineEmits<{

  (e: 'update:modelValue', value: boolean): void;

  (e: 'save', agentData: any): void;

}>();



const { t } = useI18n();



// 状

const formRef = ref();

const formValid = ref(false);

const saving = ref(false);

const activeTab = ref('basic');



// 加载状

const loadingTools = ref(false);

const loadingSkills = ref(false);

const loadingKnowledgeBases = ref(false);

const loadingProviders = ref(false);

const loadingModels = ref(false);



// 可选项

const availableTools = ref<any[]>([]);

const availableSkills = ref<any[]>([]);

const availableKnowledgeBases = ref<any[]>([]);

const providerOptions = ref<any[]>([]);

const modelOptions = ref<any[]>([]);



// 表单数据

const formData = ref({

  id: '',

  name: '',

  role: '',

  goal: '',

  backstory: '',

  tools: [] as string[],

  skills: [] as string[],

  knowledgeBases: [] as string[],

  knowledge_id: null as string | null,

  provider_id: '',

  model_name: '',

  model: {

    provider: '',

    name: '',

    temperature: 0.7,

    maxTokens: 4096,

    topP: 1.0,

  },

  planning: {

    enabled: false,

    maxSteps: 5,

  },

  memory: {

    enabled: false,

    type: 'short_term',

    maxMessages: 20,

  },

  behavior: {

    maxRetries: 3,

    timeout: 60,

    verbose: false,

  },

  enabled: true,

});



// 验证规则

const rules = {

  required: (v: string) => !!v || t('agent.agents.editor.validation.required'),

};



// 选项

const memoryTypeOptions = [

  { title: t('agent.agents.editor.advanced.memoryTypes.shortTerm'), value: 'short_term' },

  { title: t('agent.agents.editor.advanced.memoryTypes.longTerm'), value: 'long_term' },

];



// 加载工具列表

async function loadTools() {

  loadingTools.value = true;

  try {

    const response = await axios.get('/api/plug/agent/tools');

    if (response.data.status === 'ok') {

      availableTools.value = (response.data.data || []).map((tool: any) => ({

        title: tool.name,

        value: tool.name,

      }));

    }

  } catch (error) {

    console.error('Failed to load tools:', error);

  } finally {

    loadingTools.value = false;

  }

}



// 加载技能列

async function loadSkills() {

  loadingSkills.value = true;

  try {

    const response = await axios.get('/api/plug/agent/skills');

    if (response.data.status === 'ok') {

      availableSkills.value = (response.data.data || []).map((skill: any) => ({
        title: skill.name,
        value: skill.id,
      }));

    }

  } catch (error) {

    console.error('Failed to load skills:', error);

  } finally {

    loadingSkills.value = false;

  }

}



// 加载知识库列

async function loadKnowledgeBases() {

  loadingKnowledgeBases.value = true;

  try {

    const response = await axios.get('/api/plug/agent/knowledge');

    if (response.data.status === 'ok') {

      availableKnowledgeBases.value = (response.data.data || []).map((kb: any) => ({

        title: kb.name,

        value: kb.name,

      }));

    }

  } catch (error) {

    console.error('Failed to load knowledge bases:', error);

  } finally {

    loadingKnowledgeBases.value = false;

  }

}



// 加载提供商列

async function loadProviders() {

  loadingProviders.value = true;

  try {

    const response = await axios.get('/api/config/provider/list', {

      params: { provider_type: 'chat_completion' }

    });

    if (response.data.status === 'ok') {

      const providers = (response.data.data || [])

        .filter((provider: any) => provider.enable !== false);

      

      // 填充提供商选项

      providerOptions.value = providers.map((provider: any) => ({

        title: provider.name || provider.id,

        value: provider.id,

      }));

      

      // 填充提供商详情映

      providersMap.value.clear();

      providers.forEach((provider: any) => {

        providersMap.value.set(provider.id, provider);

      });

    }

  } catch (error) {

    console.error('Failed to load providers:', error);

  } finally {

    loadingProviders.value = false;

  }

}



// 存储提供商详

const providersMap = ref<Map<string, any>>(new Map());



// 加载模型列表

async function loadModels() {

  if (!formData.value.model.provider) return;



  loadingModels.value = true;

  modelOptions.value = [];

  try {

    // 从已加载的提供商列表中获取模型信

    const provider = providersMap.value.get(formData.value.model.provider);

    if (provider && provider.model) {

      modelOptions.value = [{

        title: provider.model,

        value: provider.model,

      }];

    }

  } catch (error) {

    console.error('Failed to load models:', error);

  } finally {

    loadingModels.value = false;

  }

}



// 监听智能体变

watch(() => props.agent, (newAgent) => {

  if (newAgent) {

    formData.value = {

      id: newAgent.id || '',

      name: newAgent.name || '',

      role: newAgent.role || '',

      goal: newAgent.goal || '',

      backstory: newAgent.backstory || '',

      tools: newAgent.tools || [],

      skills: newAgent.skills || [],

      knowledgeBases: newAgent.knowledgeBases || [],

      knowledge_id: newAgent.knowledge_id || null,

      provider_id: newAgent.provider_id || '',

      model_name: newAgent.model_name || '',

      model: {

        provider: newAgent.model?.provider || newAgent.provider_id || '',

        name: newAgent.model?.name || newAgent.model_name || '',

        temperature: newAgent.model?.temperature || 0.7,

        maxTokens: newAgent.model?.maxTokens || 4096,

        topP: newAgent.model?.topP || 1.0,

      },

      planning: {

        enabled: newAgent.planning?.enabled || false,

        maxSteps: newAgent.planning?.maxSteps || 5,

      },

      memory: {

        enabled: newAgent.memory?.enabled || false,

        type: newAgent.memory?.type || 'short_term',

        maxMessages: newAgent.memory?.maxMessages || 20,

      },

      behavior: {

        maxRetries: newAgent.behavior?.maxRetries || 3,

        timeout: newAgent.behavior?.timeout || 60,

        verbose: newAgent.behavior?.verbose || false,

      },

      enabled: newAgent.enabled ?? true,

    };



    // 加载对应提供商的模型列表

    if (formData.value.model.provider) {

      loadModels();

    }

  } else {

    resetForm();

  }

}, { immediate: true });



// 重置表单

function resetForm() {

  formData.value = {

    id: '',

    name: '',

    role: '',

    goal: '',

    backstory: '',

    tools: [],

    skills: [],

    knowledgeBases: [],

    knowledge_id: null,

    provider_id: '',

    model_name: '',

    model: {

      provider: '',

      name: '',

      temperature: 0.7,

      maxTokens: 4096,

      topP: 1.0,

    },

    planning: {

      enabled: false,

      maxSteps: 5,

    },

    memory: {

      enabled: false,

      type: 'short_term',

      maxMessages: 20,

    },

    behavior: {

      maxRetries: 3,

      timeout: 60,

      verbose: false,

    },

    enabled: true,

  };

  activeTab.value = 'basic';

}



// 保存

async function handleSave() {

  const { valid } = await formRef.value?.validate();

  if (!valid) return;



  saving.value = true;

  try {

    // 构建保存数据，转换模型字段

    const saveData = {

      ...formData.value,

      provider_id: formData.value.model.provider,

      model_name: formData.value.model.name,

      llm_config: {

        temperature: formData.value.model.temperature,

        max_tokens: formData.value.model.maxTokens,

        top_p: formData.value.model.topP,

      },

    };

    await emit('save', saveData);

  } finally {

    saving.value = false;

  }

}



// 初始

onMounted(() => {

  loadTools();

  loadSkills();

  loadKnowledgeBases();

  loadProviders();

});

</script>



<style scoped>

.agent-editor-drawer {

  z-index: 1000;

}



.agent-editor-drawer .v-card {

  border-radius: 0;

}

</style>

