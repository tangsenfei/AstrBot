<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <v-card class="roundtable-editor">
      <!-- 标题栏 -->
      <v-toolbar color="primary" dark density="prominent">
        <v-btn icon dark @click="handleClose">
          <v-icon icon="mdi-close" />
        </v-btn>
        <v-toolbar-title>
          <v-icon icon="mdi-table-chair" class="mr-2" />
          {{ isEditing ? $t('agent.roundtables.editor.editTitle') : $t('agent.roundtables.editor.addTitle') }}
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

      <!-- 主内容区 -->
      <v-container fluid class="pa-6">
        <v-form ref="formRef" v-model="formValid">
          <v-row>
            <!-- 左侧：基本信息和参会者 -->
            <v-col cols="12" md="6">
              <!-- 基本信息 -->
              <v-card class="mb-4">
                <v-card-title>
                  <v-icon icon="mdi-information" class="mr-2" />
                  {{ $t('agent.roundtables.editor.basicInfo') }}
                </v-card-title>
                <v-card-text>
                  <v-text-field
                    v-model="formData.name"
                    :label="$t('agent.roundtables.editor.basic.name')"
                    :rules="[rules.required]"
                    :disabled="isEditing"
                    :hint="$t('agent.roundtables.editor.basic.nameHint')"
                    persistent-hint
                    class="mb-3"
                  />

                  <v-text-field
                    v-model="formData.topic"
                    :label="$t('agent.roundtables.editor.basic.topic')"
                    :rules="[rules.required]"
                    :hint="$t('agent.roundtables.editor.basic.topicHint')"
                    persistent-hint
                    class="mb-3"
                  />

                  <v-textarea
                    v-model="formData.deliverable"
                    :label="$t('agent.roundtables.editor.basic.deliverable')"
                    :hint="$t('agent.roundtables.editor.basic.deliverableHint')"
                    persistent-hint
                    rows="3"
                    auto-grow
                    class="mb-3"
                  />
                </v-card-text>
              </v-card>

              <!-- 参会者选择 -->
              <v-card class="mb-4">
                <v-card-title class="d-flex align-center">
                  <v-icon icon="mdi-account-group" class="mr-2" />
                  {{ $t('agent.roundtables.editor.participants.title') }}
                  <v-spacer />
                  <v-chip size="small" :color="formData.participants.length >= 2 ? 'success' : 'warning'">
                    {{ formData.participants.length }}
                  </v-chip>
                </v-card-title>
                <v-card-text>
                  <v-alert type="info" variant="tonal" class="mb-3" density="compact">
                    {{ $t('agent.roundtables.editor.participants.hint') }}
                  </v-alert>

                  <AgentSelector v-model="formData.participants" />

                  <v-alert
                    v-if="formData.participants.length > 0 && formData.participants.length < 2"
                    type="warning"
                    variant="tonal"
                    density="compact"
                    class="mt-3"
                  >
                    {{ $t('agent.roundtables.editor.participants.minWarning') }}
                  </v-alert>
                </v-card-text>
              </v-card>
            </v-col>

            <!-- 右侧：会议类型、主持人设置、材料准备、轮数 -->
            <v-col cols="12" md="6">
              <!-- 会议类型 -->
              <v-card class="mb-4">
                <v-card-title>
                  <v-icon icon="mdi-shape-outline" class="mr-2" />
                  {{ $t('agent.roundtables.editor.meetingType.title') }}
                </v-card-title>
                <v-card-text>
                  <v-select
                    v-model="formData.meeting_type"
                    :items="meetingTypeOptions"
                    :label="$t('agent.roundtables.editor.meetingType.select')"
                    item-title="title"
                    item-value="value"
                    :rules="[rules.required]"
                    class="mb-3"
                  >
                    <template v-slot:item="{ props, item }">
                      <v-list-item v-bind="props">
                        <v-list-item-subtitle>
                          {{ item.raw.description }}
                        </v-list-item-subtitle>
                      </v-list-item>
                    </template>
                  </v-select>

                  <v-alert
                    v-if="selectedMeetingTypeDesc"
                    type="info"
                    variant="tonal"
                    density="compact"
                    class="mb-0"
                  >
                    {{ selectedMeetingTypeDesc }}
                  </v-alert>
                </v-card-text>
              </v-card>

              <!-- 主持人设置 -->
              <v-card class="mb-4">
                <v-card-title>
                  <v-icon icon="mdi-account-tie" class="mr-2" />
                  {{ $t('agent.roundtables.editor.moderator.title') }}
                </v-card-title>
                <v-card-text>
                  <v-radio-group v-model="formData.has_moderator" class="mb-3">
                    <v-radio :value="true">
                      <template v-slot:label>
                        <div>
                          <div class="text-subtitle-1">{{ $t('agent.roundtables.editor.moderator.enabled') }}</div>
                          <div class="text-caption text-grey">{{ $t('agent.roundtables.editor.moderator.enabledHint') }}</div>
                        </div>
                      </template>
                    </v-radio>
                    <v-radio :value="false">
                      <template v-slot:label>
                        <div>
                          <div class="text-subtitle-1">{{ $t('agent.roundtables.editor.moderator.disabled') }}</div>
                          <div class="text-caption text-grey">{{ $t('agent.roundtables.editor.moderator.disabledHint') }}</div>
                        </div>
                      </template>
                    </v-radio>
                  </v-radio-group>

                  <div v-if="formData.has_moderator">
                    <v-btn
                      v-if="meetingAssistantId && !formData.moderator"
                      variant="tonal"
                      color="primary"
                      block
                      class="mb-3"
                      @click="useMeetingAssistant"
                    >
                      <v-icon icon="mdi-account-star" class="mr-2" />
                      使用会议助手（推荐）
                    </v-btn>

                    <v-alert
                      v-if="formData.moderator === meetingAssistantId"
                      type="success"
                      variant="tonal"
                      density="compact"
                      class="mb-3"
                    >
                      已选择会议助手作为主持人，具备网络搜索、文档保存等能力
                    </v-alert>

                    <v-select
                      v-model="formData.moderator"
                      :items="moderatorOptions"
                      :label="$t('agent.roundtables.editor.moderator.select')"
                      item-title="title"
                      item-value="value"
                      :rules="[rules.requiredIfModerator]"
                      class="mb-3"
                    >
                      <template v-slot:item="{ props, item }">
                        <v-list-item v-bind="props">
                          <template v-slot:prepend>
                            <v-icon :icon="item.raw.isMeetingAssistant ? 'mdi-account-star' : 'mdi-robot'" :color="item.raw.isMeetingAssistant ? 'primary' : undefined" />
                          </template>
                          <template v-slot:append v-if="item.raw.isMeetingAssistant">
                            <v-chip size="x-small" color="primary" variant="tonal">会议助手</v-chip>
                          </template>
                        </v-list-item>
                      </template>
                    </v-select>
                  </div>
                </v-card-text>
              </v-card>

              <!-- 导出格式 -->
              <v-card class="mb-4">
                <v-card-title>
                  <v-icon icon="mdi-file-export" class="mr-2" />
                  {{ $t('agent.roundtables.editor.export.title') }}
                </v-card-title>
                <v-card-text>
                  <v-select
                    v-model="formData.export_format"
                    :items="exportFormatOptions"
                    :label="$t('agent.roundtables.editor.export.format')"
                    item-title="title"
                    item-value="value"
                    class="mb-0"
                  />
                </v-card-text>
              </v-card>

              <!-- 讨论轮数 -->
              <v-card class="mb-4">
                <v-card-title>
                  <v-icon icon="mdi-rotate-right" class="mr-2" />
                  {{ $t('agent.roundtables.editor.rounds.title') }}
                </v-card-title>
                <v-card-text>
                  <div class="d-flex align-center mb-2">
                    <v-slider
                      v-model="formData.rounds"
                      :min="1"
                      :max="10"
                      :step="1"
                      thumb-label
                      show-ticks
                      class="flex-grow-1 mr-4"
                    />
                    <v-text-field
                      v-model.number="formData.rounds"
                      type="number"
                      :min="1"
                      :max="10"
                      style="max-width: 80px;"
                      hide-details
                      density="compact"
                      variant="outlined"
                    />
                  </div>
                  <div class="text-caption text-grey">
                    {{ $t('agent.roundtables.editor.rounds.hint', { count: formData.rounds }) }}
                  </div>
                </v-card-text>
              </v-card>

              <!-- 高级配置 -->
              <v-card class="mb-4">
                <v-card-title class="d-flex align-center cursor-pointer" @click="showAdvanced = !showAdvanced">
                  <v-icon icon="mdi-tune-vertical" class="mr-2" />
                  {{ $t('agent.roundtables.editor.advanced.title') }}
                  <v-spacer />
                  <v-icon :icon="showAdvanced ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
                </v-card-title>
                <v-expand-transition>
                  <v-card-text v-show="showAdvanced">
                    <v-text-field
                      v-model.number="formData.max_length"
                      :label="$t('agent.roundtables.editor.advanced.maxLength')"
                      type="number"
                      :min="100"
                      :max="10000"
                      :step="100"
                      :hint="$t('agent.roundtables.editor.advanced.maxLengthHint')"
                      persistent-hint
                      class="mb-3"
                    />

                    <v-select
                      v-model="formData.output_format"
                      :items="outputFormatOptions"
                      :label="$t('agent.roundtables.editor.advanced.outputFormat')"
                      :hint="$t('agent.roundtables.editor.advanced.outputFormatHint')"
                      persistent-hint
                      class="mb-3"
                    />
                  </v-card-text>
                </v-expand-transition>
              </v-card>
            </v-col>
          </v-row>

          <!-- 材料准备区 -->
          <v-row>
            <v-col cols="12">
              <v-card class="mb-4">
                <v-card-title class="d-flex align-center">
                  <v-icon icon="mdi-book-open-variant" class="mr-2" />
                  {{ $t('agent.roundtables.editor.materials.title') }}
                  <v-spacer />
                  <v-chip size="small" color="info" v-if="formData.materials.type">
                    {{ materialsTypeLabel }}
                  </v-chip>
                </v-card-title>
                <v-card-text>
                  <v-tabs v-model="materialsTab" color="primary">
                    <v-tab value="none">{{ $t('agent.roundtables.editor.materials.none') }}</v-tab>
                    <v-tab value="url">{{ $t('agent.roundtables.editor.materials.url') }}</v-tab>
                    <v-tab value="file">{{ $t('agent.roundtables.editor.materials.file') }}</v-tab>
                    <v-tab value="manual">{{ $t('agent.roundtables.editor.materials.manual') }}</v-tab>
                  </v-tabs>

                  <v-window v-model="materialsTab" class="mt-4">
                    <!-- 无材料 -->
                    <v-window-item value="none">
                      <v-alert type="info" variant="tonal" density="compact">
                        {{ $t('agent.roundtables.editor.materials.noneHint') }}
                      </v-alert>
                    </v-window-item>

                    <!-- URL -->
                    <v-window-item value="url">
                      <v-text-field
                        v-model="formData.materials.content"
                        :label="$t('agent.roundtables.editor.materials.urlLabel')"
                        :hint="$t('agent.roundtables.editor.materials.urlHint')"
                        persistent-hint
                        prepend-icon="mdi-link"
                      />
                    </v-window-item>

                    <!-- 文件 -->
                    <v-window-item value="file">
                      <v-file-input
                        v-model="materialsFile"
                        :label="$t('agent.roundtables.editor.materials.fileLabel')"
                        :hint="$t('agent.roundtables.editor.materials.fileHint')"
                        persistent-hint
                        prepend-icon="mdi-paperclip"
                        accept=".pdf,.doc,.docx,.md,.txt"
                        @change="handleFileChange"
                      />
                      <v-textarea
                        v-if="formData.materials.content"
                        v-model="formData.materials.content"
                        :label="$t('agent.roundtables.editor.materials.fileContent')"
                        rows="5"
                        auto-grow
                        readonly
                        class="mt-3"
                      />
                    </v-window-item>

                    <!-- 人工补充（引导式） -->
                    <v-window-item value="manual">
                      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                        {{ $t('agent.roundtables.editor.materials.manualHint') }}
                      </v-alert>

                      <div v-if="preparationQuestions.length > 0">
                        <v-card
                          v-for="(q, idx) in preparationQuestions"
                          :key="q.id"
                          class="mb-3"
                          variant="outlined"
                        >
                          <v-card-text>
                            <div class="text-subtitle-2 mb-2">
                              <v-icon icon="mdi-help-circle" class="mr-1" color="primary" />
                              {{ q.question }}
                            </div>
                            <div class="text-caption text-grey mb-3">
                              {{ q.example }}
                            </div>
                            <v-textarea
                              v-model="preparationAnswers[idx]"
                              :label="$t('agent.roundtables.editor.materials.answerLabel')"
                              rows="2"
                              auto-grow
                              hide-details
                            />
                          </v-card-text>
                        </v-card>
                      </div>
                      <div v-else>
                        <v-textarea
                          v-model="formData.materials.content"
                          :label="$t('agent.roundtables.editor.materials.manualLabel')"
                          :hint="$t('agent.roundtables.editor.materials.manualHint2')"
                          persistent-hint
                          rows="5"
                          auto-grow
                        />
                      </div>
                    </v-window-item>
                  </v-window>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-form>
      </v-container>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue';
import axios from 'axios';
import { useI18n } from 'vue-i18n';
import AgentSelector from '../components/AgentSelector.vue';

const props = defineProps<{
  modelValue: boolean;
  roundtable: any;
  isEditing: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', roundtableData: any): void;
}>();

const { t } = useI18n();

// 状态
const formValid = ref(true);
const saving = ref(false);
const showAdvanced = ref(false);
const loadingAgents = ref(false);
const formRef = ref<any>(null);
const materialsTab = ref('none');
const materialsFile = ref<File[]>([]);
const preparationQuestions = ref<any[]>([]);
const preparationAnswers = ref<string[]>([]);
const meetingTypeOptions = ref<any[]>([
  { title: '标准研讨', value: 'standard', description: '通用深度讨论' },
  { title: '头脑风暴', value: 'brainstorm', description: '强发散，主持人引导发散并筛选保留' },
  { title: '议会投票', value: 'parliament', description: '多轮观点阐述+投票，直到全票当选' },
  { title: '方案收敛', value: 'convergence', description: '强收敛，主持人引导形成可落地方案' },
  { title: '六顶思考帽', value: 'six_hat', description: '按白/红/黑/黄/绿/蓝六角色顺序发言' },
  { title: '鱼骨图分析', value: 'fishbone', description: '从人/机/料/法/环/测维度分析根因' },
  { title: 'SWOT分析', value: 'swot', description: '优势/劣势/机会/威胁四维度分析' },
  { title: 'OKR拆解会', value: 'okr', description: '目标到关键结果到行动计划的拆解' },
  { title: '项目复盘', value: 'retrospective', description: '回顾做得好/待改进/行动项' },
  { title: '模拟面试', value: 'interview', description: '多面试官从不同维度考察候选人' },
]);

// 可选项
const availableAgents = ref<any[]>([]);
const meetingAssistantId = ref<string>('');

// 表单数据
const formData = ref({
  id: '',
  name: '',
  topic: '',
  deliverable: '',
  meeting_type: 'standard',
  participants: [] as string[],
  has_moderator: false,
  moderator: '',
  rounds: 3,
  max_length: 2000,
  output_format: 'markdown',
  export_format: 'markdown',
  materials: {
    type: '',
    content: '',
    filename: '',
    items: [] as any[],
  },
  preparation_records: [] as any[],
});

// 输出格式选项
const outputFormatOptions = [
  { title: t('agent.roundtables.editor.advanced.formatMarkdown'), value: 'markdown' },
  { title: t('agent.roundtables.editor.advanced.formatJson'), value: 'json' },
  { title: t('agent.roundtables.editor.advanced.formatText'), value: 'text' },
];

// 导出格式选项
const exportFormatOptions = [
  { title: 'Markdown', value: 'markdown' },
  { title: 'Word', value: 'word' },
];

// 主持人选项（从已选参会者中）
const moderatorOptions = computed(() => {
  return availableAgents.value
    .filter(agent => formData.value.participants.includes(agent.value))
    .map(agent => ({
      ...agent,
      isMeetingAssistant: agent.value === meetingAssistantId.value,
      title: agent.isMeetingAssistant ? `${agent.title} ⭐` : agent.title,
    }));
});

// 使用会议助手
function useMeetingAssistant() {
  if (meetingAssistantId.value) {
    if (!formData.value.participants.includes(meetingAssistantId.value)) {
      formData.value.participants.push(meetingAssistantId.value);
    }
    formData.value.moderator = meetingAssistantId.value;
  }
}

// 当前选中的会议类型描述
const selectedMeetingTypeDesc = computed(() => {
  const found = meetingTypeOptions.value.find(m => m.value === formData.value.meeting_type);
  return found?.description || '';
});

// 材料类型标签
const materialsTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    url: '链接',
    file: '文件',
    manual: '人工补充',
  };
  return labels[formData.value.materials.type] || '';
});

// 验证规则
const rules = {
  required: (v: string) => !!v || t('agent.roundtables.editor.validation.required'),
  minParticipants: (v: string[]) => (v && v.length >= 2) || t('agent.roundtables.editor.validation.minParticipants'),
  requiredIfModerator: (v: string) => {
    if (!formData.value.has_moderator) return true;
    return !!v || t('agent.roundtables.editor.validation.moderatorRequired');
  },
};

// 加载会议类型
async function loadMeetingTypes() {
  try {
    const response = await axios.get('/api/plug/agent/roundtables/meeting-types');
    if (response.data.status === 'ok') {
      meetingTypeOptions.value = (response.data.data || []).map((item: any) => ({
        title: _getMeetingTypeName(item.type),
        value: item.type,
        description: item.description,
      }));
    }
  } catch (error) {
    console.error('Failed to load meeting types:', error);
    // 使用默认选项
    meetingTypeOptions.value = [
      { title: '标准研讨', value: 'standard', description: '通用深度讨论' },
      { title: '头脑风暴', value: 'brainstorm', description: '强发散，主持人引导发散并筛选保留' },
      { title: '议会投票', value: 'parliament', description: '多轮观点阐述+投票，直到全票当选' },
      { title: '方案收敛', value: 'convergence', description: '强收敛，主持人引导形成可落地方案' },
      { title: '六顶思考帽', value: 'six_hat', description: '按白/红/黑/黄/绿/蓝六角色顺序发言' },
      { title: '鱼骨图分析', value: 'fishbone', description: '从人/机/料/法/环/测维度分析根因' },
      { title: 'SWOT分析', value: 'swot', description: '优势/劣势/机会/威胁四维度分析' },
      { title: 'OKR拆解会', value: 'okr', description: '目标到关键结果到行动计划的拆解' },
      { title: '项目复盘', value: 'retrospective', description: '回顾做得好/待改进/行动项' },
      { title: '模拟面试', value: 'interview', description: '多面试官从不同维度考察候选人' },
    ];
  }
}

function _getMeetingTypeName(type: string): string {
  const names: Record<string, string> = {
    standard: '标准研讨',
    brainstorm: '头脑风暴',
    parliament: '议会投票',
    convergence: '方案收敛',
    six_hat: '六顶思考帽',
    fishbone: '鱼骨图分析',
    swot: 'SWOT分析',
    okr: 'OKR拆解会',
    retrospective: '项目复盘',
    interview: '模拟面试',
  };
  return names[type] || type;
}

// 加载智能体列表
async function loadAgents() {
  loadingAgents.value = true;
  try {
    const response = await axios.get('/api/plug/agent/agents');
    if (response.data.status === 'ok') {
      availableAgents.value = (response.data.data || []).map((agent: any) => {
        const isMeetingAssistant = agent.metadata?.is_meeting_assistant === true;
        if (isMeetingAssistant) {
          meetingAssistantId.value = agent.id;
        }
        return {
          title: agent.name,
          value: agent.id,
          role: agent.role || '-',
          icon: isMeetingAssistant ? 'mdi-account-star' : 'mdi-robot',
          isMeetingAssistant,
        };
      });
    }
  } catch (error) {
    console.error('Failed to load agents:', error);
  } finally {
    loadingAgents.value = false;
  }
}

// 加载准备问题
async function loadPreparationQuestions() {
  if (!formData.value.id || formData.value.meeting_type === 'standard') {
    preparationQuestions.value = [];
    return;
  }
  try {
    const response = await axios.post(`/api/plug/agent/roundtables/${formData.value.id}/prepare`, {
      action: 'generate_questions',
    });
    if (response.data.status === 'ok') {
      preparationQuestions.value = response.data.data?.questions || [];
      preparationAnswers.value = new Array(preparationQuestions.value.length).fill('');
    }
  } catch (error) {
    console.error('Failed to load preparation questions:', error);
    preparationQuestions.value = [];
  }
}

// 文件变更处理
function handleFileChange() {
  const file = materialsFile.value?.[0];
  if (file) {
    formData.value.materials.filename = file.name;
    // 读取文件内容（文本文件）
    if (file.type.startsWith('text/') || file.name.endsWith('.md') || file.name.endsWith('.txt')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        formData.value.materials.content = (e.target?.result as string) || '';
      };
      reader.readAsText(file);
    } else {
      formData.value.materials.content = `[文件: ${file.name}]`;
    }
  }
}

// 监听材料标签页变化
watch(materialsTab, (newVal) => {
  formData.value.materials.type = newVal === 'none' ? '' : newVal;
  if (newVal !== 'file') {
    materialsFile.value = [];
  }
  if (newVal !== 'manual') {
    formData.value.materials.items = [];
  }
});

// 监听圆桌会议变化
watch(() => props.roundtable, (newRoundtable) => {
  if (newRoundtable) {
    const materials = newRoundtable.materials || {};
    formData.value = {
      id: newRoundtable.id || '',
      name: newRoundtable.name || '',
      topic: newRoundtable.topic || '',
      deliverable: newRoundtable.deliverable || '',
      meeting_type: newRoundtable.meeting_type || 'standard',
      participants: newRoundtable.participants || [],
      has_moderator: newRoundtable.has_moderator || false,
      moderator: newRoundtable.moderator || '',
      rounds: newRoundtable.rounds || 3,
      max_length: newRoundtable.max_length || 2000,
      output_format: newRoundtable.output_format || 'markdown',
      export_format: newRoundtable.export_format || 'markdown',
      materials: {
        type: materials.type || '',
        content: materials.content || '',
        filename: materials.filename || '',
        items: materials.items || [],
      },
      preparation_records: newRoundtable.preparation_records || [],
    };
    materialsTab.value = materials.type || 'none';
  } else {
    resetForm();
  }
}, { immediate: true });

// 监听会议类型变化，加载准备问题
watch(() => formData.value.meeting_type, () => {
  if (formData.value.id && formData.value.meeting_type !== 'standard') {
    loadPreparationQuestions();
  }
});

// 重置表单
function resetForm() {
  formData.value = {
    id: '',
    name: '',
    topic: '',
    deliverable: '',
    meeting_type: 'standard',
    participants: [],
    has_moderator: false,
    moderator: '',
    rounds: 3,
    max_length: 2000,
    output_format: 'markdown',
    export_format: 'markdown',
    materials: {
      type: '',
      content: '',
      filename: '',
      items: [],
    },
    preparation_records: [],
  };
  materialsTab.value = 'none';
  materialsFile.value = [];
  preparationQuestions.value = [];
  preparationAnswers.value = [];
  showAdvanced.value = false;
}

// 关闭
function handleClose() {
  emit('update:modelValue', false);
}

// 保存
async function handleSave() {
  const valid = await formRef.value?.validate();
  if (!valid?.valid) return;

  saving.value = true;
  try {
    // 处理人工补充材料
    if (materialsTab.value === 'manual' && preparationQuestions.value.length > 0) {
      const items = preparationQuestions.value.map((q: any, idx: number) => ({
        question: q.question,
        answer: preparationAnswers.value[idx] || '',
      })).filter((item: any) => item.answer);
      formData.value.materials.items = items;
      formData.value.materials.content = items.map((item: any) => `${item.question}\n${item.answer}`).join('\n\n');
    }

    // 处理 preparation_records
    const prepRecords = preparationQuestions.value.map((q: any, idx: number) => ({
      question: q.question,
      answer: preparationAnswers.value[idx] || '',
      time: new Date().toISOString(),
    })).filter((r: any) => r.answer);
    if (prepRecords.length > 0) {
      formData.value.preparation_records = prepRecords;
    }

    const roundtableData = {
      ...formData.value,
      // 无主持人模式下清空主持人
      moderator: formData.value.has_moderator ? formData.value.moderator : '',
    };
    await emit('save', roundtableData);
  } finally {
    saving.value = false;
  }
}

// 初始化
onMounted(() => {
  loadAgents();
  loadMeetingTypes();
});
</script>

<style scoped>
.roundtable-editor {
  background: rgb(var(--v-theme-background));
}

.cursor-pointer {
  cursor: pointer;
}
</style>
