<template>

  <v-dialog

    :model-value="modelValue"

    @update:model-value="$emit('update:modelValue', $event)"

    fullscreen

    :scrim="false"

    transition="dialog-bottom-transition"

  >

    <v-card class="crew-editor">

      <!-- 标题-->

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



      <!-- 主内容区-->

      <v-container fluid class="pa-6">

        <v-row>

          <!-- 左侧：基本信息和 Agent 成员 -->

          <v-col cols="12" md="6">

            <!-- 基本信息 -->

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

                  class="mb-3"

                />

              </v-card-text>

            </v-card>



            <!-- Agent 成员配置 -->

            <v-card class="mb-4">

              <v-card-title class="d-flex align-center">

                <v-icon icon="mdi-robot" class="mr-2" />

                {{ $t('agent.crews.editor.agents.title') }}

                <v-spacer />

                <v-btn

                  color="primary"

                  size="small"

                  variant="text"

                  @click="addAgent"

                >

                  <v-icon start icon="mdi-plus" />

                  {{ $t('agent.crews.editor.agents.add') }}

                </v-btn>

              </v-card-title>

              <v-card-text>

                <v-alert type="info" variant="tonal" class="mb-3" density="compact">

                  {{ $t('agent.crews.editor.agents.hint') }}

                </v-alert>



                <v-list v-if="formData.agents.length > 0" class="pa-0">

                  <v-list-item

                    v-for="(agent, index) in formData.agents"

                    :key="index"

                    class="px-0"

                  >

                    <template v-slot:prepend>

                      <v-icon icon="mdi-drag" class="drag-handle" />

                    </template>



                    <v-select

                      v-model="formData.agents[index]"

                      :items="availableAgents"

                      :label="$t('agent.crews.editor.agents.selectAgent')"

                      item-title="title"

                      item-value="value"

                      return-object

                      density="compact"

                      hide-details

                      class="mr-2"

                    />



                    <template v-slot:append>

                      <v-btn

                        icon

                        size="small"

                        variant="text"

                        color="error"

                        @click="removeAgent(index)"

                      >

                        <v-icon icon="mdi-delete" />

                      </v-btn>

                    </template>

                  </v-list-item>

                </v-list>



                <v-alert v-else type="warning" variant="tonal" density="compact">

                  {{ $t('agent.crews.editor.agents.noAgents') }}

                </v-alert>

              </v-card-text>

            </v-card>

          </v-col>



          <!-- 右侧：任务列表配-->

          <v-col cols="12" md="6">

            <v-card class="mb-4">

              <v-card-title class="d-flex align-center">

                <v-icon icon="mdi-clipboard-list" class="mr-2" />

                {{ $t('agent.crews.editor.tasks.title') }}

                <v-spacer />

                <v-btn

                  color="primary"

                  size="small"

                  variant="text"

                  @click="addTask"

                >

                  <v-icon start icon="mdi-plus" />

                  {{ $t('agent.crews.editor.tasks.add') }}

                </v-btn>

              </v-card-title>

              <v-card-text>

                <v-alert type="info" variant="tonal" class="mb-3" density="compact">

                  {{ $t('agent.crews.editor.tasks.hint') }}

                </v-alert>



                <v-expansion-panels v-if="formData.tasks.length > 0" multiple>

                  <v-expansion-panel

                    v-for="(task, index) in formData.tasks"

                    :key="index"

                  >

                    <v-expansion-panel-title>

                      <div class="d-flex align-center w-100">

                        <v-icon icon="mdi-drag" class="drag-handle mr-2" />

                        <span class="text-subtitle-1">

                          {{ task.name || $t('agent.crews.editor.tasks.untitled') }} {{ index + 1 }}

                        </span>

                        <v-spacer />

                        <v-btn

                          icon

                          size="small"

                          variant="text"

                          color="error"

                          @click.stop="removeTask(index)"

                        >

                          <v-icon icon="mdi-delete" />

                        </v-btn>

                      </div>

                    </v-expansion-panel-title>

                    <v-expansion-panel-text>

                      <v-text-field

                        v-model="task.name"

                        :label="$t('agent.crews.editor.tasks.taskName')"

                        class="mb-3"

                      />



                      <v-textarea

                        v-model="task.description"

                        :label="$t('agent.crews.editor.tasks.taskDescription')"

                        rows="3"

                        auto-grow

                        class="mb-3"

                      />



                      <v-textarea

                        v-model="task.expected_output"

                        :label="$t('agent.crews.editor.tasks.expectedOutput')"

                        rows="2"

                        auto-grow

                        class="mb-3"

                      />



                      <v-select

                        v-model="task.agent"

                        :items="taskAgentOptions"

                        :label="$t('agent.crews.editor.tasks.assignAgent')"

                        class="mb-3"

                        clearable

                      />



                      <v-select

                        v-model="task.tools"

                        :items="availableTools"

                        :label="$t('agent.crews.editor.tasks.selectTools')"

                        multiple

                        chips

                        closable-chips

                        class="mb-3"

                      />



                      <v-select

                        v-model="task.context"

                        :items="taskDependencyOptions(index)"

                        :label="$t('agent.crews.editor.tasks.dependencies')"

                        multiple

                        chips

                        closable-chips

                        :hint="$t('agent.crews.editor.tasks.dependenciesHint')"

                        persistent-hint

                      />

                    </v-expansion-panel-text>

                  </v-expansion-panel>

                </v-expansion-panels>



                <v-alert v-else type="warning" variant="tonal" density="compact">

                  {{ $t('agent.crews.editor.tasks.noTasks') }}

                </v-alert>

              </v-card-text>

            </v-card>

          </v-col>

        </v-row>



        <!-- 底部：Process 配置和高级选项 -->

        <v-row>

          <v-col cols="12" md="6">

            <!-- Process 配置 -->

            <v-card class="mb-4">

              <v-card-title>

                <v-icon icon="mdi-cog" class="mr-2" />

                {{ $t('agent.crews.editor.process.title') }}

              </v-card-title>

              <v-card-text>

                <v-radio-group v-model="formData.process" class="mb-3">

                  <v-radio

                    value="sequential"

                    :label="$t('agent.crews.editor.process.sequential')"

                  >

                    <template v-slot:label>

                      <div>

                        <div class="text-subtitle-1">{{ $t('agent.crews.editor.process.sequential') }}</div>

                        <div class="text-caption text-grey">{{ $t('agent.crews.editor.process.sequentialHint') }}</div>

                      </div>

                    </template>

                  </v-radio>

                  <v-radio

                    value="hierarchical"

                    :label="$t('agent.crews.editor.process.hierarchical')"

                  >

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

                  class="mb-3"

                />

              </v-card-text>

            </v-card>

          </v-col>



          <v-col cols="12" md="6">

            <!-- 高级配置 -->

            <v-card class="mb-4">

              <v-card-title>

                <v-icon icon="mdi-tune-vertical" class="mr-2" />

                {{ $t('agent.crews.editor.advanced.title') }}

              </v-card-title>

              <v-card-text>

                <!-- Memory 配置 -->

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



                <!-- Cache 配置 -->

                <v-switch

                  v-model="formData.cache.enabled"

                  :label="$t('agent.crews.editor.advanced.enableCache')"

                  color="primary"

                  class="mb-2"

                />



                <v-divider class="my-3" />



                <!-- RPM 配置 -->

                <v-text-field

                  v-model="formData.max_rpm"

                  :label="$t('agent.crews.editor.advanced.maxRPM')"

                  type="number"

                  :min="1"

                  :hint="$t('agent.crews.editor.advanced.maxRPMHint')"

                  persistent-hint

                  class="mb-3"

                />



                <!-- 共享输出 -->

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

        </v-row>

      </v-container>

    </v-card>

  </v-dialog>

</template>



<script setup lang="ts">

import { ref, watch, computed, onMounted } from 'vue';

import axios from 'axios';

import { useI18n } from 'vue-i18n';



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



// 状

const formValid = ref(true);

const saving = ref(false);



// 加载状

const loadingAgents = ref(false);

const loadingTools = ref(false);

const loadingModels = ref(false);



// 可选项

const availableAgents = ref<any[]>([]);

const availableTools = ref<any[]>([]);

const availableModels = ref<any[]>([]);



// 表单数据

const formData = ref({

  name: '',

  description: '',

  agents: [] as any[],

  tasks: [] as any[],

  process: 'sequential',

  manager_llm: '',

  memory: {

    enabled: false,

    max_messages: 20,

  },

  cache: {

    enabled: false,

  },

  max_rpm: 100,

  share_agent_output: false,

});



// 验证规则

const rules = {

  required: (v: string) => !!v || t('agent.crews.editor.validation.required'),

};



// 任务 Agent 选项

const taskAgentOptions = computed(() => {

  return formData.value.agents.map((agent: any) => ({

    title: typeof agent === 'string'  ? agent : agent.name || agent.role,

    value: typeof agent === 'string'  ? agent : agent.name,

  }));

});



// 任务依赖选项

function taskDependencyOptions(currentIndex: number) {

  return formData.value.tasks

    .map((task: any, index: number) => ({

      title: task.name || `${t('agent.crews.editor.tasks.untitled')} ${index + 1}`,

      value: index,

    }))

    .filter((_: any, index: number) => index !== currentIndex);

}



// 加载 Agent 列表

async function loadAgents() {

  loadingAgents.value = true;

  try {

    const response = await axios.get('/api/plug/agent/agents');

    if (response.data.status === 'ok') {

      availableAgents.value = (response.data.data || []).map((agent: any) => ({

        title: agent.name,

        value: agent.name,

        role: agent.role,

      }));

    }

  } catch (error) {

    console.error('Failed to load agents:', error);

  } finally {

    loadingAgents.value = false;

  }

}



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



// 加载模型列表

async function loadModels() {

  loadingModels.value = true;

  try {

    const response = await axios.get('/api/config/provider/list', {

      params: { provider_type: 'chat_completion' }

    });

    if (response.data.status === 'ok') {

      const providers = (response.data.data || [])

        .filter((provider: any) => provider.enable !== false);

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



// 添加 Agent

function addAgent() {

  formData.value.agents.push('');

}



// 移除 Agent

function removeAgent(index: number) {

  formData.value.agents.splice(index, 1);

}



// 添加任务

function addTask() {

  formData.value.tasks.push({

    name: '',

    description: '',

    expected_output: '',

    agent: '',

    tools: [],

    context: [],

  });

}



// 移除任务

function removeTask(index: number) {

  formData.value.tasks.splice(index, 1);

}



// 监听 Crew 变化

watch(() => props.crew, (newCrew) => {

  if (newCrew) {

    formData.value = {

      name: newCrew.name || '',

      description: newCrew.description || '',

      agents: newCrew.agents || [],

      tasks: newCrew.tasks || [],

      process: newCrew.process || 'sequential',

      manager_llm: newCrew.manager_llm || '',

      memory: {

        enabled: newCrew.memory?.enabled || false,

        max_messages: newCrew.memory?.max_messages || 20,

      },

      cache: {

        enabled: newCrew.cache?.enabled || false,

      },

      max_rpm: newCrew.max_rpm || 100,

      share_agent_output: newCrew.share_agent_output || false,

    };

  } else {

    resetForm();

  }

}, { immediate: true });



// 重置表单

function resetForm() {

  formData.value = {

    name: '',

    description: '',

    agents: [],

    tasks: [],

    process: 'sequential',

    manager_llm: '',

    memory: {

      enabled: false,

      max_messages: 20,

    },

    cache: {

      enabled: false,

    },

    max_rpm: 100,

    share_agent_output: false,

  };

}



// 关闭

function handleClose() {

  emit('update:modelValue', false);

}



// 保存

async function handleSave() {

  saving.value = true;

  try {

    await emit('save', formData.value);

  } finally {

    saving.value = false;

  }

}



// 初始

onMounted(() => {

  loadAgents();

  loadTools();

  loadModels();

});

</script>



<style scoped>

.crew-editor {

  background: rgb(var(--v-theme-background));

}



.drag-handle {

  cursor: move;

  opacity: 0.5;

}



.drag-handle:hover {

  opacity: 1;

}



.v-expansion-panel-title {

  padding: 12px 16px;

}



.v-expansion-panel-text :deep(.v-expansion-panel-text__wrapper) {

  padding: 16px;

}

</style>

