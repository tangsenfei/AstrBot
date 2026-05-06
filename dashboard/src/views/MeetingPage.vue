<template>
  <div class="meeting-shell" :class="{ 'is-dark': isDark }">
    <aside class="meeting-category-pane">
      <div class="pane-header">
        <div>
          <div class="pane-title">Meeting</div>
          <div class="pane-subtitle">会议工作台</div>
        </div>
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="refreshAll" />
      </div>

      <button
        class="category-row"
        :class="{ active: selectedCategory === 'all' }"
        type="button"
        @click="selectCategory('all')"
      >
        <v-icon size="18">mdi-calendar-check-outline</v-icon>
        <span>全部会议</span>
      </button>
      <button
        class="category-row"
        :class="{ active: selectedCategory === 'running' }"
        type="button"
        @click="selectCategory('running')"
      >
        <v-icon size="18">mdi-progress-clock</v-icon>
        <span>进行中</span>
      </button>
      <button
        class="category-row"
        :class="{ active: selectedCategory === 'completed' }"
        type="button"
        @click="selectCategory('completed')"
      >
        <v-icon size="18">mdi-check-circle-outline</v-icon>
        <span>已结束</span>
      </button>
      <button
        class="category-row"
        :class="{ active: selectedCategory === 'pending' }"
        type="button"
        @click="selectCategory('pending')"
      >
        <v-icon size="18">mdi-clock-outline</v-icon>
        <span>待开始</span>
      </button>
    </aside>

    <aside class="meeting-task-pane">
      <div class="task-toolbar">
        <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreateDialog">
          新建会议
        </v-btn>
        <v-text-field
          v-model="searchText"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          placeholder="搜索会议"
          prepend-inner-icon="mdi-magnify"
        />
        <div class="filter-row">
          <v-select
            v-model="statusFilter"
            :items="statusOptions"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            label="状态"
          />
          <v-select
            v-model="typeFilter"
            :items="meetingTypeOptions"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            label="类型"
          />
        </div>
      </div>

      <MeetingList
        class="task-list"
        :meetings="filteredMeetings"
        :selected-meeting-id="selectedMeetingId"
        :loading="loading"
        :is-dark="isDark"
        @select="selectMeeting"
        @hitl-open="openMeetingHitl"
      />
    </aside>

    <main class="meeting-detail-pane">
      <template v-if="selectedMeeting">
        <header class="detail-header">
          <div class="detail-main">
            <div class="detail-title-row">
              <div class="detail-title">{{ selectedMeeting.name }}</div>
              <div class="detail-subtitle inline">
                <span>{{ selectedMeeting.type_info?.name || typeName(selectedMeeting.meeting_type) }}</span>
                <span>{{ statusLabel(selectedMeeting.status) }}</span>
                <span>{{ selectedMeeting.progress || 0 }}%</span>
              </div>
              <div class="progress-facts">
                <span>当前主持动作 <strong>{{ currentStageLabel }}</strong></span>
                <span>当前发言者 <strong>{{ selectedMeeting?.current_speaker || '-' }}</strong></span>
                <span>当前轮次 <strong>{{ selectedMeeting?.current_round || 0 }}</strong></span>
              </div>
            </div>
            <div class="token-inline">
              <v-icon size="15" icon="mdi-counter" />
              <strong>{{ formatTokens(selectedMeeting.total_tokens) }}</strong>
              <span>输入 {{ formatTokens(selectedMeeting.input_tokens) }}</span>
              <span>输出 {{ formatTokens(selectedMeeting.output_tokens) }}</span>
            </div>
            <div class="stage-progress-bar">
              <div
                v-for="stage in stages"
                :key="stage.key"
                class="stage-chip"
                :class="stageState(stage.key)"
              >
                <v-icon :icon="stageIcon(stage.key)" size="14" />
                <span class="stage-label">{{ stage.label }}</span>
              </div>
            </div>
          </div>
          <div class="detail-actions">
            <v-chip :color="statusColor(selectedMeeting.status)" size="small" variant="tonal">
              {{ statusLabel(selectedMeeting.status) }}
            </v-chip>
            <v-btn v-if="canStart" color="primary" variant="flat" size="small" :loading="starting" @click="startMeeting">
              <v-icon start icon="mdi-play" />开始
            </v-btn>
            <v-btn
              v-if="selectedMeeting && ['completed', 'failed'].includes(selectedMeeting.status)"
              color="primary"
              variant="tonal"
              size="small"
              @click="continueDialog = true"
            >
              <v-icon start icon="mdi-refresh" />续会
            </v-btn>
            <v-btn icon="mdi-refresh" size="small" variant="text" @click="loadMeeting" />
          </div>
        </header>

        <v-tabs v-model="detailTab" density="compact" class="detail-tabs">
          <v-tab value="chatroom">
            <v-icon start size="16">mdi-forum</v-icon>
            会议室
          </v-tab>
          <v-tab value="logs">
            <v-icon start size="16">mdi-text-box-search-outline</v-icon>
            日志
          </v-tab>
          <v-tab value="artifacts">
            <v-icon start size="16">mdi-package-variant-closed</v-icon>
            交付物
          </v-tab>
        </v-tabs>

        <section class="detail-body">
          <div v-if="detailTab === 'chatroom'" class="chatroom-wrap">
            <div v-if="selectedMeeting?.active_hitl" class="inline-hitl">
              <InteractionCardComponent
                :card="selectedMeeting.active_hitl"
                :is-dark="isDark"
                @respond="respondHitl"
              />
            </div>
            <AgentChatPanel
              class="meeting-chat"
              :messages="chatMessages"
              :sending="submittingInput"
              :show-input="!!selectedMeeting && ['running', 'waiting_feedback'].includes(selectedMeeting.status)"
              input-placeholder="在会议室主动发言，会议助理会在下一轮纳入讨论..."
              empty-text="会议开始后，会议助理、参会 Agent、工具调用和人工确认会显示在这里"
              show-round-divider
              @send="submitInput"
            />
          </div>

          <div v-else-if="detailTab === 'artifacts'" class="artifact-list">
            <article v-for="artifact in displayArtifacts" :key="artifact.id" class="artifact-item">
              <div class="artifact-title">
                <v-icon size="18">mdi-file-document-outline</v-icon>
                <span>{{ artifactTitle(artifact) }}</span>
              </div>
              <pre>{{ artifactText(artifact) }}</pre>
            </article>
            <div v-if="!displayArtifacts.length" class="empty-state">会议结束后会在这里显示交付结果</div>
          </div>

          <div v-else class="raw-log-list">
            <div v-for="log in displayLogs" :key="log.id" class="raw-log-row" :class="{ wide: log.kind === 'text' }">
              <span>{{ formatDate(log.created_at) }}</span>
              <strong>{{ log.label }}</strong>
              <p>{{ log.message }}</p>
            </div>
            <div v-if="!displayLogs.length" class="empty-state">暂无日志</div>
          </div>
        </section>
      </template>

      <div v-else class="detail-empty">
        <v-icon size="54">mdi-clipboard-text-search-outline</v-icon>
        <div>选择一个会议查看详情</div>
      </div>
    </main>



    <v-dialog v-model="meetingDialog" max-width="760">
      <v-card class="dialog-card">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-table-chair" class="mr-2" />
          新建会议
        </v-card-title>
        <v-card-text>
          <v-row dense>
            <v-col cols="12" md="6">
              <v-text-field v-model="meetingForm.name" label="会议名称" variant="outlined" density="compact" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select
                v-model="meetingForm.meeting_type"
                :items="meetingTypeOptions"
                label="会议类型"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12">
              <v-textarea v-model="meetingForm.goal" label="会议目标" rows="3" auto-grow variant="outlined" density="compact" />
            </v-col>
            <v-col cols="12">
              <v-textarea v-model="meetingForm.expected_output" label="产出要求" rows="2" auto-grow variant="outlined" density="compact" />
            </v-col>
            <v-col cols="12">
              <v-select
                v-model="meetingForm.participants"
                :items="agentOptions"
                label="参会专家 Agent"
                variant="outlined"
                density="compact"
                multiple
                chips
                closable-chips
              />
            </v-col>
            <v-col cols="12" md="8">
              <v-textarea v-model="materialsText" label="会议材料" rows="3" auto-grow variant="outlined" density="compact" />
            </v-col>
            <v-col cols="12" md="4">
              <v-switch
                v-model="meetingForm.settings.require_goal_confirmation"
                label="开始前确认目标"
                color="primary"
                hide-details
              />
              <v-text-field
                v-model="meetingForm.settings.rounds"
                label="讨论轮次"
                type="number"
                :min="1"
                :max="6"
                density="compact"
                variant="outlined"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="meetingDialog = false">取消</v-btn>
          <v-btn color="primary" :disabled="!meetingForm.name || !meetingForm.goal" @click="createMeeting">创建</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="continueDialog" max-width="560">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-refresh" class="mr-2" />
          续会
        </v-card-title>
        <v-card-text class="dialog-grid">
          <v-textarea
            v-model="continueForm.review_comment"
            label="不满意意见"
            rows="2"
            auto-grow
            density="compact"
            variant="outlined"
          />
          <v-textarea
            v-model="continueForm.additional_topic"
            label="追加议题"
            rows="2"
            auto-grow
            density="compact"
            variant="outlined"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="continueDialog = false">取消</v-btn>
          <v-btn color="primary" :disabled="!canContinue" @click="continueMeeting">提交续会</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <HitlDialog
      v-model="hitlDialog"
      :card="selectedMeeting?.active_hitl"
      :is-dark="isDark"
      @respond="respondHitl"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import axios from 'axios';
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue';
import HitlDialog from '@/components/chat/HitlDialog.vue';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';
import MeetingList from '@/components/meeting/MeetingList.vue';
import { useCustomizerStore } from '@/stores/customizer';

type MeetingEvent = {
  id: string;
  event_type: string;
  role: string;
  speaker: string;
  round: number;
  content: string;
  payload?: Record<string, any>;
  created_at?: string;
  seq?: number;
};

type ToolCallInfo = {
  id?: string;
  name: string;
  args?: any;
  result?: any;
  status?: 'running' | 'done' | 'error';
  ts?: number;
  finished_ts?: number;
};

type ChatMessage = {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  thinkingDone?: boolean;
  planning_steps?: string | null;
  toolCalls?: ToolCallInfo[];
  speaker?: string;
  round?: number;
  type?: string;
  streaming?: boolean;
  created_at?: number;
};

type Meeting = {
  id: string;
  name: string;
  goal: string;
  meeting_type: string;
  expected_output?: string;
  participants: string[];
  status: string;
  stage: string;
  progress: number;
  current_round: number;
  current_speaker: string;
  type_info?: { type: string; name: string; description: string; output: string };
  events?: MeetingEvent[];
  artifacts?: any[];
  has_hitl?: boolean;
  active_hitl?: any;
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
};

const customizer = useCustomizerStore();
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');

const meetings = ref<Meeting[]>([]);
const meetingTypes = ref<any[]>([]);
const agents = ref<any[]>([]);
const selectedMeetingId = ref('');
const selectedMeeting = ref<Meeting | null>(null);
const events = ref<MeetingEvent[]>([]);
const artifacts = ref<any[]>([]);
const searchText = ref('');
const statusFilter = ref<string | null>(null);
const typeFilter = ref<string | null>(null);
const selectedCategory = ref('all');
const meetingDialog = ref(false);
const continueDialog = ref(false);
const hitlDialog = ref(false);
const starting = ref(false);
const submittingInput = ref(false);
const loading = ref(false);
const detailTab = ref('chatroom');
let eventSource: EventSource | null = null;
let reloadTimer: ReturnType<typeof setTimeout> | null = null;

const meetingForm = reactive({
  name: '',
  meeting_type: 'solution_design',
  goal: '',
  expected_output: '',
  participants: [] as string[],
  settings: {
    rounds: 2,
    require_goal_confirmation: false,
  },
});
const materialsText = ref('');
const continueForm = reactive({ review_comment: '', additional_topic: '', additional_rounds: 1 });

const stages = [
  { key: 'goal', label: '会议目标确定', desc: '明确目标、输入和预期产出' },
  { key: 'materials', label: '会议材料准备', desc: '整理材料、参考信息和上下文' },
  { key: 'running', label: '会议开展', desc: '按会议类型主持讨论' },
  { key: 'completed', label: '会议结束', desc: '产出纪要和会议报告' },
];

const statusOptions = [
  { title: '草稿', value: 'draft' },
  { title: '待开始', value: 'pending' },
  { title: '进行中', value: 'running' },
  { title: '等待确认', value: 'waiting_feedback' },
  { title: '已结束', value: 'completed' },
  { title: '失败', value: 'failed' },
  { title: '已取消', value: 'cancelled' },
];

const meetingTypeOptions = computed(() => meetingTypes.value.map(item => ({
  title: `${item.name} - ${item.output}`,
  value: item.type,
})));

const agentOptions = computed(() => agents.value
  .filter(agent => agent.id !== 'agent_meeting_assistant')
  .map(agent => ({ title: `${agent.name}${agent.role ? ` · ${agent.role}` : ''}`, value: agent.id })));

const canStart = computed(() => selectedMeeting.value && ['pending', 'draft', 'failed'].includes(selectedMeeting.value.status));
const canContinue = computed(() => !!continueForm.review_comment.trim() || !!continueForm.additional_topic.trim());
const currentStageLabel = computed(() => stages.find(stage => stage.key === selectedMeeting.value?.stage)?.label || statusLabel(selectedMeeting.value?.status || ''));

const filteredMeetings = computed(() => {
  const q = searchText.value.trim().toLowerCase();
  return meetings.value.filter((meeting) => {
    if (statusFilter.value && meeting.status !== statusFilter.value) return false;
    if (typeFilter.value && meeting.meeting_type !== typeFilter.value) return false;
    if (selectedCategory.value === 'running' && meeting.status !== 'running') return false;
    if (selectedCategory.value === 'completed' && meeting.status !== 'completed') return false;
    if (selectedCategory.value === 'pending' && !['pending', 'draft'].includes(meeting.status)) return false;
    if (q && !`${meeting.name} ${meeting.goal || ''}`.toLowerCase().includes(q)) return false;
    return true;
  });
});

const chatMessages = computed<ChatMessage[]>(() => mapEventsToMessages(events.value));

const displayArtifacts = computed(() => {
  return artifacts.value.filter((artifact) =>
    artifact && (artifact.file_path || artifact.content || artifact.artifact_type === 'file')
  );
});

const displayLogs = computed(() => aggregateLogs(events.value));

onMounted(async () => {
  await Promise.all([loadMeetingTypes(), loadAgents(), loadMeetings()]);
  if (meetings.value.length) selectMeeting(meetings.value[0].id);
});

onBeforeUnmount(() => closeEventSource());

function selectCategory(cat: string) {
  selectedCategory.value = cat;
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadMeetingTypes(), loadAgents(), loadMeetings()]);
    if (selectedMeetingId.value) await loadMeeting();
  } finally {
    loading.value = false;
  }
}

async function loadMeetingTypes() {
  const response = await axios.get('/api/plug/meeting/types');
  if (response.data?.status === 'ok') meetingTypes.value = response.data.data || [];
}

async function loadAgents() {
  const response = await axios.get('/api/plug/agent/agents');
  if (response.data?.status === 'ok') agents.value = response.data.data || [];
}

async function loadMeetings() {
  const response = await axios.get('/api/plug/meeting/meetings', { params: { q: searchText.value } });
  if (response.data?.status === 'ok') meetings.value = response.data.data?.meetings || [];
}

async function selectMeeting(meetingId: string) {
  if (selectedMeetingId.value === meetingId) return;
  selectedMeetingId.value = meetingId;
  detailTab.value = 'chatroom';
  events.value = [];
  artifacts.value = [];
  await loadMeeting(meetingId);
  openEventSource(meetingId);
}

async function loadMeeting(meetingId = selectedMeetingId.value) {
  if (!meetingId) return;
  const response = await axios.get(`/api/plug/meeting/meetings/${encodeURIComponent(meetingId)}`);
  if (response.data?.status === 'ok') {
    selectedMeeting.value = response.data.data;
    const serverEvents: MeetingEvent[] = selectedMeeting.value?.events || [];
    const serverIds = new Set(serverEvents.map((e: MeetingEvent) => e.id));
    const sseOnlyEvents = events.value.filter(e => !serverIds.has(e.id));
    events.value = [...serverEvents, ...sseOnlyEvents];
    artifacts.value = selectedMeeting.value?.artifacts || [];
  }
}

function openCreateDialog() {
  Object.assign(meetingForm, {
    name: '',
    meeting_type: 'solution_design',
    goal: '',
    expected_output: '',
    participants: [],
    settings: { rounds: 2, require_goal_confirmation: false },
  });
  materialsText.value = '';
  meetingDialog.value = true;
}

async function createMeeting() {
  const response = await axios.post('/api/plug/meeting/meetings', {
    ...meetingForm,
    materials: { notes: materialsText.value.trim() },
  });
  if (response.data?.status === 'ok') {
    meetingDialog.value = false;
    await loadMeetings();
    await selectMeeting(response.data.data.id);
  }
}

async function startMeeting() {
  if (!selectedMeetingId.value) return;
  starting.value = true;
  try {
    await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/start`);
    await loadMeeting();
    await loadMeetings();
  } finally {
    starting.value = false;
  }
}

async function submitInput(message: string) {
  if (!selectedMeetingId.value) return;
  submittingInput.value = true;
  try {
    await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/input`, { text: message });
    await loadMeeting();
  } finally {
    submittingInput.value = false;
  }
}

async function respondHitl(payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }) {
  if (!selectedMeetingId.value) return;
  await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/hitl`, payload);
  hitlDialog.value = false;
  await loadMeeting();
  await loadMeetings();
}

async function continueMeeting() {
  if (!selectedMeetingId.value || !canContinue.value) return;
  await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/continue`, continueForm);
  continueForm.review_comment = '';
  continueForm.additional_topic = '';
  continueDialog.value = false;
  await loadMeeting();
  await loadMeetings();
}

function openMeetingHitl(meetingId: string) {
  if (selectedMeetingId.value !== meetingId) {
    selectMeeting(meetingId);
  }
  hitlDialog.value = true;
}

function openEventSource(meetingId: string) {
  closeEventSource();
  eventSource = new EventSource(`/api/plug/meeting/meetings/${encodeURIComponent(meetingId)}/events`);
  const reload = () => {
    if (reloadTimer) clearTimeout(reloadTimer);
    reloadTimer = setTimeout(async () => {
      await loadMeeting(meetingId);
      await loadMeetings();
    }, 300);
  };
  ['phase', 'text_delta', 'tool_call', 'tool_result', 'reasoning', 'interaction', 'artifact', 'error', 'done', 'user_message', 'token'].forEach(name => {
    eventSource?.addEventListener(name, (evt: MessageEvent) => {
      try {
        const payload = JSON.parse(evt.data);
        if (name === 'token') {
          reload();
          return;
        }
        if (name === 'phase' && selectedMeeting.value) {
          if (payload.status) selectedMeeting.value.status = payload.status;
          if (payload.stage) selectedMeeting.value.stage = payload.stage;
          if (payload.progress !== undefined) selectedMeeting.value.progress = payload.progress;
        }
        if (payload?.id && !events.value.find(item => item.id === payload.id)) {
          events.value = [...events.value, payload];
        }
      } catch {
        // Ignore malformed heartbeat payloads.
      }
      reload();
    });
  });
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
  if (reloadTimer) {
    clearTimeout(reloadTimer);
    reloadTimer = null;
  }
}

function mapEventsToMessages(items: MeetingEvent[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  const toolIndex = new Map<string, ToolCallInfo>();
  for (const event of items) {
    const type = event.event_type;
    const payload = event.payload || {};
    if (['phase', 'token', 'artifact', 'hitl_resolved'].includes(type)) continue;
    const content = event.content || payload.content || payload.text || payload.message || '';
    if (!content && !['tool_call', 'tool_result', 'interaction'].includes(type)) continue;

    if (type === 'tool_call') {
      const tool: ToolCallInfo = {
        id: payload.id || payload.tool_call_id || event.id,
        name: payload.name || payload.tool_name || payload.function?.name || 'tool',
        args: payload.args || payload.arguments || payload.function?.arguments,
        status: 'running',
        ts: Date.parse(event.created_at || '') / 1000 || Date.now() / 1000,
      };
      toolIndex.set(tool.id || event.id, tool);
      messages.push(baseAssistantMessage(event, `调用工具：${tool.name}`, 'tool_call', [tool]));
      continue;
    }

    if (type === 'tool_result') {
      const toolId = payload.id || payload.tool_call_id;
      const existing = toolId ? toolIndex.get(toolId) : null;
      if (existing) {
        existing.result = payload.result || payload.content || content;
        existing.status = payload.error ? 'error' : 'done';
        existing.finished_ts = Date.parse(event.created_at || '') / 1000 || Date.now() / 1000;
      } else {
        messages.push(baseAssistantMessage(event, '工具返回结果', 'tool_result', [{
          id: toolId || event.id,
          name: payload.name || payload.tool_name || 'tool',
          result: payload.result || payload.content || content,
          status: payload.error ? 'error' : 'done',
        }]));
      }
      continue;
    }

    if (type === 'text_delta') {
      const last = messages[messages.length - 1];
      if (last && last.role === 'assistant' && last.speaker === event.speaker && last.round === event.round && last.type === 'speech') {
        last.content += content;
      } else {
        messages.push(baseAssistantMessage(event, content, 'speech'));
      }
      continue;
    }

    if (type === 'reasoning') {
      const last = messages[messages.length - 1];
      if (last && last.role === 'assistant' && last.speaker === event.speaker) {
        last.thinking = `${last.thinking || ''}${content}`;
      } else {
        messages.push({ ...baseAssistantMessage(event, '', 'thinking'), thinking: content });
      }
      continue;
    }

    if (event.role === 'user' || type === 'user_message') {
      messages.push({
        id: event.id,
        role: 'user',
        content,
        speaker: event.speaker || '用户',
        round: event.round,
        type,
        created_at: eventTime(event),
      });
      continue;
    }

    messages.push(baseAssistantMessage(event, content || payload.title || type, normalizeEventType(type)));
  }
  return messages;
}

function baseAssistantMessage(event: MeetingEvent, content: string, type = 'speech', toolCalls?: ToolCallInfo[]): ChatMessage {
  return {
    id: event.id,
    role: 'assistant',
    content,
    speaker: event.speaker || '会议助理',
    round: event.round,
    type,
    created_at: eventTime(event),
    toolCalls,
  };
}

function eventTime(event: MeetingEvent): number {
  const ts = Date.parse(event.created_at || '');
  return Number.isFinite(ts) ? ts : Date.now();
}

function normalizeEventType(type: string) {
  if (type === 'phase') return 'guide';
  if (type === 'artifact') return 'summary';
  if (type === 'interaction') return 'question';
  return type;
}

function typeName(type: string) {
  return meetingTypes.value.find(item => item.type === type)?.name || type;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    pending: '待开始',
    running: '进行中',
    waiting_feedback: '等待确认',
    completed: '已结束',
    failed: '失败',
    cancelled: '已取消',
  };
  return labels[status] || status;
}

function statusColor(status: string) {
  const colors: Record<string, string> = {
    draft: 'grey',
    pending: 'info',
    running: 'primary',
    waiting_feedback: 'warning',
    completed: 'success',
    failed: 'error',
    cancelled: 'grey',
  };
  return colors[status] || 'default';
}

function stageState(stage: string) {
  const order = ['goal', 'materials', 'running', 'completed'];
  const current = selectedMeeting.value?.stage || 'goal';
  const currentIndex = order.indexOf(current === 'finalizing' ? 'completed' : current);
  const index = order.indexOf(stage);
  if (current === stage || (current === 'finalizing' && stage === 'completed')) return 'active';
  if (currentIndex > index || selectedMeeting.value?.status === 'completed') return 'done';
  return '';
}

function stageIcon(stage: string) {
  const icons: Record<string, string> = {
    goal: 'mdi-target',
    materials: 'mdi-file-document-outline',
    running: 'mdi-forum',
    completed: 'mdi-clipboard-check-outline',
  };
  return icons[stage] || 'mdi-circle-outline';
}

function formatTokens(value: number | undefined) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function formatDate(value: string | undefined) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function artifactTitle(artifact: any) {
  return artifact.title || artifact.metadata?.title || '会议交付物';
}

function artifactText(artifact: any) {
  const metadata = artifact.metadata || {};
  const value =
    artifact.content ||
    metadata.content ||
    metadata.body ||
    metadata.result ||
    metadata.summary ||
    artifact.file_path ||
    '暂无内容';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function aggregateLogs(rawEvents: MeetingEvent[]) {
  const result: Array<{ id: string; created_at: string; label: string; message: string; kind: string }> = [];
  let buffer: { id: string; created_at: string; label: string; message: string; kind: string } | null = null;
  const flush = () => {
    if (buffer) {
      result.push(buffer);
      buffer = null;
    }
  };

  for (const evt of rawEvents) {
    const data = evt.payload || {};
    const event = evt.event_type || 'log';
    if (event === 'token') continue;
    if (event === 'text_delta') {
      const text = String(data.text || evt.content || '');
      if (!buffer || buffer.kind !== 'text') {
        flush();
        buffer = {
          id: `${evt.id}-group`,
          created_at: evt.created_at || '',
          label: '输出',
          message: text,
          kind: 'text',
        };
      } else {
        buffer.message = joinDeltaText(buffer.message, text);
        buffer.created_at = evt.created_at || buffer.created_at;
      }
      continue;
    }
    if (event === 'reasoning') {
      const text = String(data.text || evt.content || '');
      if (!buffer || buffer.kind !== 'reasoning') {
        flush();
        buffer = {
          id: `${evt.id}-group`,
          created_at: evt.created_at || '',
          label: '思考',
          message: text,
          kind: 'reasoning',
        };
      } else {
        buffer.message = joinDeltaText(buffer.message, text);
        buffer.created_at = evt.created_at || buffer.created_at;
      }
      continue;
    }
    flush();
    result.push({
      id: evt.id,
      created_at: evt.created_at || '',
      label: eventLabel(event),
      message: logMessage(evt),
      kind: event,
    });
  }
  flush();
  return result;
}

function logMessage(evt: MeetingEvent) {
  const data = evt.payload || {};
  const event = evt.event_type || 'log';
  if (event === 'tool_call') return data.name ? `调用工具：${data.name}` : JSON.stringify(data, null, 2);
  if (event === 'tool_result') return data.result || data.output || data.message || '工具调用完成';
  if (event === 'phase') return data.message || data.label || data.phase || evt.content || '';
  if (event === 'interaction') return data.title || data.body || '等待人工处理';
  if (event === 'user_message') return evt.content || data.text || '';
  return evt.content || data.message || '';
}

function eventLabel(event: string) {
  const map: Record<string, string> = {
    phase: '阶段',
    tool_call: '工具',
    tool_result: '工具结果',
    artifact: '交付物',
    interaction: 'HITL',
    user_message: '用户',
    text_delta: '输出',
    reasoning: '思考',
    error: '错误',
  };
  return map[event] || event;
}

function joinDeltaText(current: string, next: string) {
  if (!current) return next;
  if (!next) return current;
  if (/^[，。！？；：、,.!?;:)\]\}]/.test(next)) return `${current}${next}`;
  if (/[\s([{（【]$/.test(current) || /^[\s]/.test(next)) return `${current}${next}`;
  if (/^[A-Za-z0-9_]/.test(next) && /[A-Za-z0-9_]$/.test(current)) return `${current} ${next}`;
  return `${current}${next}`;
}
</script>

<style scoped>
.meeting-shell {
  --work-bg: #f7f8fa;
  --work-panel: #ffffff;
  --work-panel-soft: #f1f4f8;
  --work-border: rgba(var(--v-border-color), 0.18);
  --work-muted: rgba(var(--v-theme-on-surface), 0.62);
  display: grid;
  grid-template-columns: 210px 320px minmax(360px, 1fr);
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--work-bg);
  color: rgb(var(--v-theme-on-surface));
}

.meeting-shell.is-dark {
  --work-bg: #17191d;
  --work-panel: #202329;
  --work-panel-soft: #262b33;
  --work-border: rgba(255, 255, 255, 0.1);
}

.meeting-category-pane,
.meeting-task-pane {
  min-height: 0;
  border-right: 1px solid var(--work-border);
  background: var(--work-panel);
}

.meeting-category-pane {
  overflow: auto;
  padding: 14px;
}

.pane-header,
.detail-header,
.filter-row {
  display: flex;
  align-items: center;
}

.pane-header,
.detail-header {
  justify-content: space-between;
  gap: 12px;
}

.pane-title {
  font-size: 19px;
  font-weight: 800;
}

.pane-title.small {
  font-size: 15px;
  margin-bottom: 12px;
}

.pane-subtitle,
.detail-subtitle,
.meeting-desc,
.meeting-meta {
  color: var(--work-muted);
}

.category-row {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 8px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.category-row:hover,
.category-row.active {
  background: rgba(var(--v-theme-primary), 0.1);
}

.meeting-task-pane {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid var(--work-border);
  background: var(--work-panel);
}

.filter-row {
  gap: 10px;
}

.filter-row > * {
  flex: 1;
  min-width: 0;
}

.task-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}

.meeting-detail-pane {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--work-bg);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--work-border);
  background: var(--work-panel);
}

.detail-main {
  min-width: 0;
  flex: 1;
}

.detail-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
}

.detail-title {
  font-size: 18px;
  font-weight: 800;
}

.detail-subtitle.inline {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 13px;
}

.detail-subtitle.inline span:not(:last-child)::after {
  content: "·";
  margin-left: 6px;
  color: var(--work-muted);
}

.token-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  margin-top: 4px;
  color: var(--work-muted);
  font-size: 12px;
}

.token-inline strong {
  color: rgb(var(--v-theme-on-surface));
  font-size: 13px;
}

.detail-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  min-width: 140px;
}

.detail-actions > .v-btn,
.detail-actions > .v-chip {
  align-self: flex-end;
}

.detail-tabs {
  background: var(--work-panel);
  border-bottom: 1px solid var(--work-border);
}

.detail-tabs :deep(.v-tabs__container) {
  justify-content: flex-start;
}

.detail-tabs :deep(.v-tab) {
  min-width: 90px;
  padding: 0 16px;
  text-transform: none;
  letter-spacing: normal;
}

.detail-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px max(18px, calc((100% - 880px) / 2));
}

.chatroom-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.inline-hitl {
  padding: 12px 18px 0;
  flex-shrink: 0;
}

.meeting-chat {
  flex: 1;
  min-height: 0;
}

.detail-empty,
.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  color: var(--work-muted);
}

.empty-state {
  min-height: 120px;
  height: auto;
  font-size: 13px;
}

.empty-state.compact {
  min-height: 48px;
}

.detail-main .stage-progress-bar {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  padding: 4px 0;
  overflow-x: auto;
}

.stage-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  transition: all 0.3s ease;
  border: 1px solid var(--work-border);
  background: var(--work-panel-soft);
  color: var(--work-muted);
}

.stage-chip.done {
  background: rgba(var(--v-theme-success), 0.12);
  border-color: rgba(var(--v-theme-success), 0.35);
  color: rgb(var(--v-theme-success));
}

.stage-chip.active {
  background: rgba(var(--v-theme-primary), 0.12);
  border-color: rgba(var(--v-theme-primary), 0.45);
  color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.12);
}

.stage-label {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-title-row .progress-facts {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  margin-left: auto;
  font-size: 12px;
}

.detail-title-row .progress-facts span {
  color: var(--work-muted);
  white-space: nowrap;
}

.detail-title-row .progress-facts strong {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 600;
}

.artifact-list,
.raw-log-list,
.dialog-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.artifact-item {
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel);
  padding: 14px;
}

.artifact-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 750;
  margin-bottom: 10px;
}

.artifact-item pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  margin: 0;
  font: inherit;
  line-height: 1.6;
}

.raw-log-row {
  display: grid;
  grid-template-columns: 160px 70px 1fr;
  gap: 8px;
  align-items: start;
  padding: 9px 0;
  border-bottom: 1px solid var(--work-border);
  font-size: 13px;
}

.raw-log-row p {
  min-width: 0;
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
}

.raw-log-row.wide {
  grid-template-columns: 160px 70px minmax(0, 1fr);
}

.dialog-grid {
  gap: 12px;
}

.dialog-card {
  border-radius: 8px;
}

@media (max-width: 1180px) {
  .meeting-shell {
    grid-template-columns: 170px 260px minmax(300px, 1fr) 320px;
  }
}

@media (max-width: 820px) {
  .meeting-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto 1fr auto;
  }

  .meeting-category-pane,
  .meeting-task-pane {
    max-height: 210px;
    border-right: 0;
    border-bottom: 1px solid var(--work-border);
  }

  .detail-body {
    padding: 14px;
  }

  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .raw-log-row {
    grid-template-columns: 1fr;
  }


}
</style>
