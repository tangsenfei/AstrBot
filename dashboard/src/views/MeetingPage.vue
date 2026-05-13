<template>
  <div class="meeting-shell" :class="{ 'is-dark': isDark }">
    <aside class="meeting-task-pane">
      <div class="task-toolbar">
        <div class="toolbar-actions">
          <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openCreateDialog">
            新建会议
          </v-btn>
          <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="refreshAll" />
        </div>
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
        :loading-more="loadingMore"
        :has-more="hasMore"
        :is-dark="isDark"
        @scroll.passive="handleMeetingListScroll"
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
                :class="[stageState(stage.key), { selected: selectedMeetingStageKey === stage.key }]"
                role="button"
                tabindex="0"
                @click="selectMeetingStage(stage.key)"
                @keydown.enter.prevent="selectMeetingStage(stage.key)"
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
            <v-btn
              v-if="canCancelMeeting"
              color="error"
              variant="tonal"
              size="small"
              :loading="cancelling"
              @click="cancelMeeting"
            >
              <v-icon start icon="mdi-stop-circle-outline" />取消会议
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
          </div>
        </header>

        <v-tabs v-model="detailTab" density="compact" class="detail-tabs">
          <v-tab value="chatroom">
            <v-icon start size="16">mdi-forum</v-icon>
            会议室
          </v-tab>
          <v-tab value="logs">
            <v-icon start size="16">mdi-text-box-search-outline</v-icon>
            详情
          </v-tab>
          <v-tab value="artifacts">
            <v-icon start size="16">mdi-package-variant-closed</v-icon>
            交付物
          </v-tab>
        </v-tabs>

        <section class="detail-body">
          <div v-if="detailTab === 'chatroom'" class="chatroom-wrap">
            <AgentChatPanel
              class="meeting-chat-panel"
              :messages="chatMessages"
              :sending="submittingInput"
              :show-input="!!selectedMeeting && ['running', 'waiting_feedback'].includes(selectedMeeting.status)"
              input-placeholder="在会议室主动发言，会议助理会在下一轮纳入讨论..."
              empty-text="会议开展后，主持人、参会 Agent 和用户发言会显示在这里"
              show-round-divider
              collapse-thinking-by-default
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

          <div v-else class="node-detail-view">
            <div v-if="selectedMeetingNode" class="node-detail-header">
              <span class="node-icon">
                <v-icon :icon="stageIcon(selectedMeetingNode.key)" size="18" />
              </span>
              <div class="node-title-wrap">
                <span class="node-title">{{ selectedMeetingNode.label }}</span>
                <span class="node-subtitle">{{ selectedMeetingNode.desc }}</span>
              </div>
              <span class="node-meta">
                <span v-if="selectedMeetingNode.tokenTotal" class="node-token">tokens {{ formatTokens(selectedMeetingNode.tokenTotal) }}</span>
                <v-chip size="x-small" :color="nodeStateColor(selectedMeetingNode.state)" variant="tonal">{{ nodeStateLabel(selectedMeetingNode.state) }}</v-chip>
              </span>
            </div>

            <WorkProgressTimeline
              v-if="selectedMeetingNode"
              :logs="selectedMeetingNode.logs"
              :active-cards="activeCardsForStage(selectedMeetingNode.key)"
              :is-dark="isDark"
              :loading="selectedMeeting?.status === 'running' && selectedMeetingNode.state === 'active'"
              agent-label="会议助理"
              @interaction-respond="respondHitl"
            />
            <div v-if="!selectedMeetingNode || (!selectedMeetingNode.logs.length && !activeCardsForStage(selectedMeetingNode.key).length)" class="empty-state">
              暂无节点详情
            </div>
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
                label="最大兜底轮数"
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import axios from 'axios';
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue';
import HitlDialog from '@/components/chat/HitlDialog.vue';
import MeetingList from '@/components/meeting/MeetingList.vue';
import WorkProgressTimeline from '@/components/work/WorkProgressTimeline.vue';
import { usePagedTaskList } from '@/composables/usePagedTaskList';
import { useSelectedEventStream } from '@/composables/useSelectedEventStream';
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
  call_id?: string;
  _stats?: { input: number; output: number; total: number } | null;
  _execution_time_ms?: number;
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

const meetingTypes = ref<any[]>([]);
const agents = ref<any[]>([]);
const selectedMeetingId = ref('');
const selectedMeeting = ref<Meeting | null>(null);
const events = ref<MeetingEvent[]>([]);
const artifacts = ref<any[]>([]);
const cachedMessages = ref<ChatMessage[]>([]);
const lastProcessedEventCount = ref(0);
const seenMeetingEventIds = new Set<string>();
const seenMeetingEventSignatures = new Set<string>();
const searchText = ref('');
const statusFilter = ref<string | null>(null);
const typeFilter = ref<string | null>(null);
const meetingDialog = ref(false);
const continueDialog = ref(false);
const hitlDialog = ref(false);
const starting = ref(false);
const cancelling = ref(false);
const submittingInput = ref(false);
const detailTab = ref('chatroom');
const selectedMeetingStageKey = ref('running');
const collapsedMeetingNodeIds = ref<Set<string>>(new Set());
let listRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let summaryRefreshTimer: ReturnType<typeof setInterval> | null = null;
let filterReloadTimer: ReturnType<typeof setTimeout> | null = null;

const meetingList = usePagedTaskList<Meeting>({
  pageSize: 30,
  loadPage: loadMeetingPage,
});
const meetings = meetingList.items;
const loading = meetingList.loading;
const loadingMore = meetingList.loadingMore;
const hasMore = meetingList.hasMore;
const meetingStream = useSelectedEventStream({
  eventNames: [
    'phase',
    'text_delta',
    'assistant_message',
    'tool_call',
    'tool_result',
    'reasoning',
    'interaction',
    'artifact',
    'error',
    'done',
    'user_message',
    'agent_call_start',
    'agent_call_end',
    'token',
    'hitl_resolved',
    'log',
  ],
  streamUrl: (meetingId, afterSeq) => `/api/plug/meeting/meetings/${encodeURIComponent(meetingId)}/events?after_seq=${afterSeq}`,
  getAfterSeq: maxEventSeq,
  onEvent: handleMeetingStreamEvent,
  onFallback: meetingId => loadMeetingEvents(meetingId, { afterSeq: maxEventSeq() }),
  shouldReconnect: meetingId => selectedMeetingId.value === meetingId && !isTerminalStatus(selectedMeeting.value?.status || ''),
});

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
const canCancelMeeting = computed(() => selectedMeeting.value && ['pending', 'running', 'waiting_feedback'].includes(selectedMeeting.value.status));
const canContinue = computed(() => !!continueForm.review_comment.trim() || !!continueForm.additional_topic.trim());
const currentStageLabel = computed(() => stages.find(stage => stage.key === selectedMeeting.value?.stage)?.label || statusLabel(selectedMeeting.value?.status || ''));

const meetingNodes = computed(() => {
  const callIdsWithText = new Set(
    events.value
      .filter(event => event.event_type === 'text_delta' && eventContent(event).trim())
      .map(event => String(event.payload?.call_id || ''))
      .filter(Boolean)
  );
  return stages.map(stage => {
    const stageEvents = events.value
      .filter(event => stageKeyForEvent(event) === stage.key)
      .map(event => meetingEventToLog(event, callIdsWithText))
      .filter(Boolean) as any[];
    return {
      ...stage,
      state: stageState(stage.key),
      logs: stageEvents,
      tokenTotal: stageEvents.reduce((sum, log) => {
        const data = log.data || {};
        if (data.event !== 'token') return sum;
        return sum + Number(data.total || data.total_tokens || Number(data.input || 0) + Number(data.output || 0));
      }, 0),
    };
  });
});

const filteredMeetings = computed(() => {
  return meetings.value;
});

const selectedMeetingNode = computed(() =>
  meetingNodes.value.find(node => node.key === selectedMeetingStageKey.value) || meetingNodes.value[0] || null
);

const chatMessages = computed<ChatMessage[]>(() => {
  const currentEvents = events.value;
  const result = mapEventsToMessages(currentEvents);
  cachedMessages.value = result;
  lastProcessedEventCount.value = currentEvents.length;
  return result;
});

const displayArtifacts = computed(() => {
  return artifacts.value.filter((artifact) =>
    artifact && (artifact.file_path || artifact.content || artifact.artifact_type === 'file')
  );
});

watch([searchText, statusFilter, typeFilter], () => {
  scheduleFilterReload();
});

onMounted(async () => {
  await Promise.all([loadMeetingTypes(), loadAgents(), loadMeetings()]);
  await ensureSelectedMeeting();
  startSummaryRefresh();
});

onBeforeUnmount(() => {
  closeEventSource();
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  if (filterReloadTimer) clearTimeout(filterReloadTimer);
});

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadMeetingTypes(), loadAgents(), loadMeetings()]);
    await ensureSelectedMeeting();
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
  await meetingList.loadFirstPage();
}

async function loadMeetingPage(page: number, pageSize: number) {
  const params: Record<string, any> = {
    page,
    page_size: pageSize,
    q: searchText.value.trim() || undefined,
    meeting_type: typeFilter.value || undefined,
  };
  const status = listStatusFilter();
  if (status) params.status = status;
  const response = await axios.get('/api/plug/meeting/meetings', { params });
  const data = response.data?.data || {};
  return {
    items: data.meetings || [],
    pagination: data.pagination,
  };
}

function listStatusFilter() {
  return statusFilter.value || '';
}

async function reloadMeetingsForFilters() {
  closeEventSource();
  selectedMeetingId.value = '';
  selectedMeeting.value = null;
  events.value = [];
  resetEventIndexes();
  artifacts.value = [];
  cachedMessages.value = [];
  lastProcessedEventCount.value = 0;
  await loadMeetings();
  await ensureSelectedMeeting();
}

function scheduleFilterReload() {
  if (filterReloadTimer) clearTimeout(filterReloadTimer);
  filterReloadTimer = setTimeout(() => {
    filterReloadTimer = null;
    reloadMeetingsForFilters().catch(() => undefined);
  }, 350);
}

async function ensureSelectedMeeting() {
  if (selectedMeetingId.value && meetings.value.some(item => item.id === selectedMeetingId.value)) return;
  const first = meetings.value[0];
  if (first) {
    await selectMeeting(first.id);
    return;
  }
  selectedMeetingId.value = '';
  selectedMeeting.value = null;
  events.value = [];
  resetEventIndexes();
  artifacts.value = [];
}

function handleMeetingListScroll(event: Event) {
  const target = event.target as HTMLElement | null;
  if (!target) return;
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 120) {
    meetingList.loadMore().catch(() => undefined);
  }
}

function startSummaryRefresh() {
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  summaryRefreshTimer = setInterval(() => {
    if (!document.hidden) refreshMeetingSummaries().catch(() => undefined);
  }, 10000);
}

async function refreshMeetingSummaries() {
  const ids = meetingList.loadedIds.value;
  if (!ids.length) return;
  const response = await axios.get('/api/plug/meeting/meetings/summaries', {
    params: { ids: ids.join(',') },
  });
  if (response.data?.status !== 'ok') return;
  const summaries: Meeting[] = response.data.data?.meetings || [];
  meetingList.mergeSummaries(summaries);
  const selectedSummary = summaries.find(item => item.id === selectedMeetingId.value);
  if (selectedSummary && selectedMeeting.value) {
    selectedMeeting.value = {
      ...selectedMeeting.value,
      ...selectedSummary,
      artifacts: selectedMeeting.value.artifacts,
      events: selectedMeeting.value.events,
    };
  }
}

async function selectMeeting(meetingId: string) {
  if (selectedMeetingId.value === meetingId) {
    await loadMeeting(meetingId);
    await loadMeetingEvents(meetingId, { afterSeq: maxEventSeq() });
    if (!meetingStream.connected.value && !isTerminalStatus(selectedMeeting.value?.status || '')) {
      openEventSource(meetingId);
    }
    return;
  }
  closeEventSource();
  selectedMeetingId.value = meetingId;
  detailTab.value = 'chatroom';
  selectedMeetingStageKey.value = 'running';
  events.value = [];
  resetEventIndexes();
  artifacts.value = [];
  cachedMessages.value = [];
  lastProcessedEventCount.value = 0;
  await loadMeeting(meetingId);
  selectedMeetingStageKey.value = normalizeStageKey(selectedMeeting.value?.stage) || 'running';
  await loadMeetingEvents(meetingId, { tail: true });
  openEventSource(meetingId);
}

async function loadMeeting(meetingId = selectedMeetingId.value) {
  if (!meetingId) return;
  const response = await axios.get(`/api/plug/meeting/meetings/${encodeURIComponent(meetingId)}`);
  if (response.data?.status === 'ok') {
    selectedMeeting.value = response.data.data;
    artifacts.value = selectedMeeting.value?.artifacts || [];
    if (!selectedMeetingStageKey.value) {
      selectedMeetingStageKey.value = normalizeStageKey(selectedMeeting.value?.stage) || 'running';
    }
  }
}

async function loadMeetingEvents(meetingId = selectedMeetingId.value, options: { tail?: boolean; afterSeq?: number } = {}) {
  if (!meetingId) return;
  const response = await axios.get(`/api/plug/meeting/meetings/${encodeURIComponent(meetingId)}/events`, {
    params: {
      stream: 0,
      limit: 500,
      tail: options.tail ? 1 : undefined,
      after_seq: options.afterSeq,
    },
  });
  if (response.data?.status === 'ok') {
    const serverEvents: MeetingEvent[] = response.data.data?.events || [];
    if (options.afterSeq) {
      for (const event of serverEvents) appendMeetingEvent(event);
    } else {
      events.value = serverEvents;
      rebuildEventIndexes(serverEvents);
      cachedMessages.value = [];
      lastProcessedEventCount.value = 0;
    }
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
    meetingList.replaceItem(response.data.data);
    await selectMeeting(response.data.data.id);
  }
}

async function startMeeting() {
  if (!selectedMeetingId.value) return;
  starting.value = true;
  try {
    await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/start`);
    if (selectedMeeting.value) {
      selectedMeeting.value.status = 'running';
      selectedMeeting.value.stage = 'goal';
      selectedMeeting.value.progress = Math.max(selectedMeeting.value.progress || 0, 5);
    }
    meetingList.mergeSummaries([{ id: selectedMeetingId.value, status: 'running', stage: 'goal', progress: selectedMeeting.value?.progress || 5 } as any]);
    openEventSource(selectedMeetingId.value);
    await loadMeeting();
    scheduleListRefresh(1000);
  } finally {
    starting.value = false;
  }
}

async function cancelMeeting() {
  if (!selectedMeetingId.value || cancelling.value) return;
  cancelling.value = true;
  try {
    const response = await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/cancel`);
    if (response.data?.status === 'ok') {
      const meeting = response.data.data;
      selectedMeeting.value = meeting;
      meetingList.mergeSummaries([meeting]);
      closeEventSource();
      await loadMeetingEvents(selectedMeetingId.value, { tail: true });
    }
  } finally {
    cancelling.value = false;
  }
}

async function submitInput(message: string) {
  if (!selectedMeetingId.value) return;
  submittingInput.value = true;
  try {
    const response = await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/input`, { text: message });
    if (response.data?.status === 'ok') appendMeetingEvent(response.data.data);
  } finally {
    submittingInput.value = false;
  }
}

async function respondHitl(payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }) {
  if (!selectedMeetingId.value) return;
  await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/hitl`, payload);
  hitlDialog.value = false;
  // 立即清除 active_hitl，避免状态不同步
  if (selectedMeeting.value) {
    selectedMeeting.value.active_hitl = null;
    selectedMeeting.value.has_hitl = false;
    selectedMeeting.value.status = 'running';
  }
  meetingList.mergeSummaries([{ id: selectedMeetingId.value, active_hitl: null, has_hitl: false, status: 'running' } as any]);
  await loadMeeting();
  scheduleListRefresh(1000);
}

async function continueMeeting() {
  if (!selectedMeetingId.value || !canContinue.value) return;
  await axios.post(`/api/plug/meeting/meetings/${encodeURIComponent(selectedMeetingId.value)}/continue`, continueForm);
  continueForm.review_comment = '';
  continueForm.additional_topic = '';
  continueDialog.value = false;
  await loadMeeting();
  await loadMeetingEvents(selectedMeetingId.value, { tail: true });
  openEventSource(selectedMeetingId.value);
  scheduleListRefresh(1000);
}

function selectMeetingStage(stage: string) {
  selectedMeetingStageKey.value = normalizeStageKey(stage) || 'goal';
  detailTab.value = 'logs';
}

async function openMeetingHitl(meetingId: string) {
  if (selectedMeetingId.value !== meetingId) {
    await selectMeeting(meetingId);
  } else if (!selectedMeeting.value?.active_hitl) {
    await loadMeeting(meetingId);
  }
  hitlDialog.value = true;
}

function openEventSource(meetingId: string) {
  if (isTerminalStatus(selectedMeeting.value?.status || '')) return;
  meetingStream.open(meetingId);
}

function closeEventSource() {
  meetingStream.close();
  if (listRefreshTimer) {
    clearTimeout(listRefreshTimer);
    listRefreshTimer = null;
  }
}

function handleMeetingStreamEvent(name: string, payload: any) {
  const eventPayload = payload?.payload || payload || {};
  if (name === 'heartbeat') return;
  if (name === 'token' && selectedMeeting.value) {
    scheduleListRefresh(800);
  }
  if (name === 'phase' && selectedMeeting.value) {
    const nextStatus = eventPayload.status || selectedMeeting.value.status;
    const nextStage = eventPayload.stage || eventPayload.phase;
    const nextProgress = Number(eventPayload.progress);
    const isCompletedPhase = nextStatus === 'completed' || nextStage === 'completed';
    if (isCompletedPhase) {
      selectedMeeting.value.status = 'completed';
      selectedMeeting.value.stage = 'completed';
      selectedMeeting.value.progress = 100;
    } else if (!isTerminalStatus(selectedMeeting.value.status)) {
      if (eventPayload.status) selectedMeeting.value.status = eventPayload.status;
      if (nextStage) selectedMeeting.value.stage = nextStage;
      if (Number.isFinite(nextProgress)) {
        selectedMeeting.value.progress = Math.max(Number(selectedMeeting.value.progress || 0), nextProgress);
      }
    }
    if (payload.speaker) selectedMeeting.value.current_speaker = payload.speaker;
    if (Number(payload.round || eventPayload.round || 0) > 0) {
      selectedMeeting.value.current_round = Number(payload.round || eventPayload.round);
    }
    meetingList.mergeSummaries([{ id: selectedMeeting.value.id, status: selectedMeeting.value.status, stage: selectedMeeting.value.stage, progress: selectedMeeting.value.progress, current_round: selectedMeeting.value.current_round, current_speaker: selectedMeeting.value.current_speaker } as any]);
  }
  if (name === 'hitl_resolved' && selectedMeeting.value) {
    selectedMeeting.value.active_hitl = null;
    selectedMeeting.value.has_hitl = false;
    if (!isTerminalStatus(selectedMeeting.value.status)) selectedMeeting.value.status = 'running';
    meetingList.mergeSummaries([{ id: selectedMeeting.value.id, active_hitl: null, has_hitl: false, status: selectedMeeting.value.status } as any]);
  }
  if (name === 'interaction' && selectedMeeting.value) {
    selectedMeeting.value.active_hitl = eventPayload;
    selectedMeeting.value.has_hitl = true;
    selectedMeeting.value.status = 'waiting_feedback';
    meetingList.mergeSummaries([{ id: selectedMeeting.value.id, active_hitl: eventPayload, has_hitl: true, status: 'waiting_feedback' } as any]);
  }
  if (name === 'artifact') {
    scheduleArtifactRefresh();
  }
  if (name === 'done') {
    if (selectedMeeting.value) {
      selectedMeeting.value.status = eventPayload.status || 'completed';
      if (selectedMeeting.value.status === 'completed') {
        selectedMeeting.value.stage = 'completed';
        selectedMeeting.value.progress = 100;
        selectedMeeting.value.current_speaker = '已完成';
      }
      meetingList.mergeSummaries([{ id: selectedMeeting.value.id, status: selectedMeeting.value.status, stage: selectedMeeting.value.stage, progress: selectedMeeting.value.progress, current_speaker: selectedMeeting.value.current_speaker } as any]);
    }
    scheduleListRefresh(500);
    scheduleArtifactRefresh(500);
    meetingStream.close();
    return;
  }
  appendMeetingEvent(payload);
}

function appendMeetingEvent(event: MeetingEvent) {
  if (!event?.id) return;
  if (seenMeetingEventIds.has(event.id)) return;
  if (isMergeableDeltaEvent(event)) {
    const merged = mergeWithLastDeltaEvent(event);
    if (merged) {
      events.value = merged;
      cachedMessages.value = [];
      lastProcessedEventCount.value = 0;
      rebuildEventIndexes(merged);
      return;
    }
  }
  const signature = eventSignature(event);
  if (signature && seenMeetingEventSignatures.has(signature)) return;
  seenMeetingEventIds.add(event.id);
  if (signature) seenMeetingEventSignatures.add(signature);
  const nextEvents = [...events.value, event].slice(-1500);
  if (nextEvents.length === events.value.length) {
    cachedMessages.value = [];
    lastProcessedEventCount.value = 0;
    rebuildEventIndexes(nextEvents);
  }
  events.value = nextEvents;
}

function resetEventIndexes() {
  seenMeetingEventIds.clear();
  seenMeetingEventSignatures.clear();
}

function rebuildEventIndexes(items: MeetingEvent[]) {
  resetEventIndexes();
  for (const item of items) {
    if (item?.id) seenMeetingEventIds.add(item.id);
    const signature = eventSignature(item);
    if (signature) seenMeetingEventSignatures.add(signature);
  }
}

function isMergeableDeltaEvent(event: MeetingEvent) {
  return event.event_type === 'text_delta' || event.event_type === 'reasoning';
}

function mergeWithLastDeltaEvent(event: MeetingEvent): MeetingEvent[] | null {
  const last = events.value[events.value.length - 1];
  if (!last || last.event_type !== event.event_type) return null;
  if ((last.speaker || '') !== (event.speaker || '')) return null;
  if (displayRound(last) !== displayRound(event)) return null;

  const text = joinDeltaText(eventContent(last), eventContent(event));
  const payload = {
    ...(last.payload || {}),
    ...(event.payload || {}),
    text,
    content: text,
  };
  return [
    ...events.value.slice(0, -1),
    {
      ...last,
      id: last.id,
      content: text,
      payload,
      created_at: last.created_at || event.created_at,
    },
  ];
}

function eventSignature(event: MeetingEvent) {
  const type = event.event_type || '';
  const content = eventContent(event).trim();
  if (!type || !content || type === 'text_delta' || type === 'reasoning' || type === 'token') return '';
  return [type, event.speaker || '', Number(event.round || event.payload?.round || 0), content].join('|');
}

function maxEventSeq() {
  return events.value.reduce((max, event) => Math.max(max, Number(event.seq || 0)), 0);
}

function scheduleListRefresh(delay = 5000) {
  if (listRefreshTimer) clearTimeout(listRefreshTimer);
  listRefreshTimer = setTimeout(() => {
    refreshMeetingSummaries().catch(() => undefined);
    listRefreshTimer = null;
  }, delay);
}

function scheduleArtifactRefresh(delay = 1000) {
  setTimeout(() => {
    if (selectedMeetingId.value) loadMeeting(selectedMeetingId.value).catch(() => undefined);
  }, delay);
}

function isTerminalStatus(status: string) {
  return ['completed', 'failed', 'cancelled'].includes(status || '');
}

function mapEventsToMessages(items: MeetingEvent[], existingMessages?: ChatMessage[]): ChatMessage[] {
  const messages: ChatMessage[] = existingMessages ? [...existingMessages] : [];
  const callStats = buildChatCallStats(items);
  const toolIndex = new Map<string, ToolCallInfo>();
  // 如果已有消息，重建 toolIndex
  if (existingMessages) {
    for (const msg of existingMessages) {
      if (msg.toolCalls) {
        for (const tc of msg.toolCalls) {
          if (tc.id) toolIndex.set(tc.id, tc);
        }
      }
    }
  }
  for (const event of items) {
    if (!isChatroomEvent(event)) continue;
    const type = event.event_type || 'log';
    const payload = event.payload || {};
    if (['token', 'artifact', 'hitl_resolved'].includes(type)) continue;
    const content = eventContent(event);
    if (!content && !['tool_call', 'tool_result', 'interaction', 'phase'].includes(type)) continue;

    if (type !== 'reasoning') finishOpenThinking(messages);

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
      const round = displayRound(event);
      const last = findOpenSpeech(messages, event);
      if (last && last.round === round) {
        last.content += content;
        last.streaming = true;
      } else {
        messages.push({ ...baseAssistantMessage(event, content, 'speech'), round, streaming: true });
      }
      continue;
    }

    if (type === 'assistant_message') {
      const existing = findOpenSpeech(messages, event);
      if (existing) {
        existing.id = event.id;
        existing.content = content;
        existing.streaming = false;
        existing.thinkingDone = true;
      } else {
        messages.push({ ...baseAssistantMessage(event, content, 'speech'), streaming: false });
      }
      continue;
    }

    if (type === 'reasoning') {
      const reasoningText = reasoningContent(event);
      if (!reasoningText) continue;
      const last = findOpenSpeech(messages, event);
      if (last) {
        last.thinking = joinDeltaText(last.thinking || '', reasoningText);
        last.thinkingDone = false;
      } else {
        messages.push({ ...baseAssistantMessage(event, '', 'speech'), thinking: reasoningText, thinkingDone: false, streaming: true });
      }
      continue;
    }

    if (type === 'phase') {
      messages.push(baseAssistantMessage(event, content || payload.label || payload.stage || '会议阶段更新', 'guide'));
      continue;
    }

    if (event.role === 'user' || type === 'user_message') {
      messages.push({
        id: event.id,
        role: 'user',
        content,
        speaker: event.speaker || '用户',
        round: displayRound(event),
        type,
        created_at: eventTime(event),
      });
      continue;
    }

    messages.push(baseAssistantMessage(event, content || payload.title || type, normalizeEventType(type)));
  }
  applyChatCallStats(messages, callStats);
  return messages;
}

function isChatroomEvent(event: MeetingEvent): boolean {
  const type = event.event_type || '';
  if (type === 'user_message') return true;
  if (stageKeyForEvent(event) !== 'running') return false;
  return ['text_delta', 'assistant_message', 'reasoning', 'tool_call', 'tool_result', 'error'].includes(type);
}

function buildChatCallStats(items: MeetingEvent[]) {
  const stats = new Map<string, { input: number; output: number; total: number; duration_ms?: number }>();
  for (const event of items) {
    const payload = event.payload || {};
    const callId = String(payload.call_id || '');
    if (!callId) continue;
    const current = stats.get(callId) || { input: 0, output: 0, total: 0 };
    if (event.event_type === 'token') {
      const input = Number(payload.input || payload.input_tokens || 0);
      const output = Number(payload.output || payload.output_tokens || 0);
      current.input += Number.isFinite(input) ? input : 0;
      current.output += Number.isFinite(output) ? output : 0;
      current.total += Number(payload.total || payload.total_tokens || input + output || 0) || 0;
    }
    if (event.event_type === 'agent_call_end') {
      const duration = Number(payload.duration_ms || 0);
      if (Number.isFinite(duration) && duration > 0) current.duration_ms = duration;
    }
    stats.set(callId, current);
  }
  return stats;
}

function applyChatCallStats(messages: ChatMessage[], stats: Map<string, { input: number; output: number; total: number; duration_ms?: number }>) {
  for (const message of messages) {
    if (!message.call_id) continue;
    const stat = stats.get(message.call_id);
    if (!stat) continue;
    if (stat.input || stat.output || stat.total) {
      message._stats = {
        input: stat.input,
        output: stat.output,
        total: stat.total || stat.input + stat.output,
      };
    }
    if (stat.duration_ms) message._execution_time_ms = stat.duration_ms;
  }
}

function eventContent(event: MeetingEvent): string {
  const payload = event.payload || {};
  const value =
    event.content ||
    payload.content ||
    payload.text ||
    payload.delta ||
    payload.reasoning ||
    payload.reasoning_content ||
    payload.thinking ||
    payload.message ||
    payload.label ||
    payload.title ||
    '';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

function reasoningContent(event: MeetingEvent): string {
  const payload = event.payload || {};
  const value =
    event.content ||
    payload.reasoning ||
    payload.reasoning_content ||
    payload.thinking ||
    payload.text ||
    payload.delta ||
    payload.content ||
    '';
  if (typeof value !== 'string') return JSON.stringify(value);
  return value.trim() ? value : '';
}

function findOpenSpeech(messages: ChatMessage[], event: MeetingEvent): ChatMessage | undefined {
  const speaker = event.speaker || '会议助理';
  const round = displayRound(event);
  const callId = String(event.payload?.call_id || '');
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const msg = messages[index];
    if (msg.role !== 'assistant' || msg.type !== 'speech') continue;
    if ((msg.speaker || '会议助理') !== speaker || msg.round !== round) return undefined;
    if (callId && msg.call_id && msg.call_id !== callId) return undefined;
    if (msg.streaming || !msg.content || msg.thinkingDone === false) return msg;
    return undefined;
  }
  return undefined;
}

function finishOpenThinking(messages: ChatMessage[]) {
  const last = messages[messages.length - 1];
  if (last && last.role === 'assistant' && last.thinking !== undefined && last.thinkingDone === false) {
    last.thinkingDone = true;
  }
}

function baseAssistantMessage(event: MeetingEvent, content: string, type = 'speech', toolCalls?: ToolCallInfo[]): ChatMessage {
  return {
    id: event.id,
    role: 'assistant',
    content,
    speaker: event.speaker || '会议助理',
    round: displayRound(event),
    type,
    created_at: eventTime(event),
    call_id: String(event.payload?.call_id || '') || undefined,
    toolCalls,
  };
}

function displayRound(event: MeetingEvent): number | undefined {
  const round = Number(event.round || event.payload?.round || 0);
  return round > 0 ? round : undefined;
}

function eventTime(event: MeetingEvent): number {
  const ts = Date.parse(event.created_at || '');
  return Number.isFinite(ts) ? ts : Date.now();
}

function toggleMeetingNode(key: string) {
  const next = new Set(collapsedMeetingNodeIds.value);
  if (next.has(key)) next.delete(key); else next.add(key);
  collapsedMeetingNodeIds.value = next;
}

function isMeetingNodeCollapsed(key: string) {
  return collapsedMeetingNodeIds.value.has(key);
}

function activeCardsForStage(stage: string) {
  const card = selectedMeeting.value?.active_hitl;
  if (!card) return [];
  const cardStage = card.meta?.stage || card.metadata?.stage || 'goal';
  return normalizeStageKey(cardStage) === stage ? [card] : [];
}

function normalizeStageKey(value: string | undefined) {
  const stage = String(value || '');
  if (stage === 'finalizing' || stage === 'finalize') return 'completed';
  if (['goal', 'materials', 'running', 'completed'].includes(stage)) return stage;
  return '';
}

function stageKeyForEvent(event: MeetingEvent) {
  const payload = event.payload || {};
  const explicitStage = normalizeStageKey(payload.stage || payload.phase || payload.stage_id || payload.node_id);
  if (explicitStage) return explicitStage;
  const type = event.event_type || '';
  if (type === 'user_message') return 'running';
  if (type === 'artifact') {
    return payload.artifact_type === 'brief' ? 'materials' : 'completed';
  }
  if (displayRound(event)) return 'running';
  if (['agent_call_start', 'agent_call_end', 'text_delta', 'reasoning', 'assistant_message', 'tool_call', 'tool_result', 'token'].includes(type)) {
    return payload.call_id ? 'running' : 'goal';
  }
  return 'goal';
}

function meetingEventToLog(event: MeetingEvent, callIdsWithText: Set<string>) {
  const payload = event.payload || {};
  let type = event.event_type || 'log';
  const callId = String(payload.call_id || '');
  if (type === 'assistant_message') {
    if (callId && callIdsWithText.has(callId)) return null;
    type = 'text_delta';
  }
  const text = eventContent(event);
  const data = {
    ...payload,
    event: type,
    text,
    content: text,
    speaker: event.speaker,
    agent_label: payload.agent_label || payload.agent_name || event.speaker,
    agent: payload.agent_label || payload.agent_name || event.speaker,
    round: displayRound(event),
    stage_id: stageKeyForEvent(event),
    node_id: payload.node_id || stageKeyForEvent(event),
  };
  return {
    id: event.id,
    seq: event.seq,
    level: type === 'error' ? 'error' : 'info',
    message: text || payload.title || payload.label || type,
    data,
    created_at: event.created_at,
  };
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
  if (selectedMeeting.value?.status === 'completed') return 'done';
  const order = ['goal', 'materials', 'running', 'completed'];
  const current = selectedMeeting.value?.stage || 'goal';
  const currentIndex = order.indexOf(current === 'finalizing' ? 'completed' : current);
  const index = order.indexOf(stage);
  if (current === stage || (current === 'finalizing' && stage === 'completed')) return 'active';
  if (currentIndex > index || selectedMeeting.value?.status === 'completed') return 'done';
  return '';
}

function nodeStateLabel(state: string) {
  const labels: Record<string, string> = {
    done: '已完成',
    active: '进行中',
  };
  return labels[state] || '待处理';
}

function nodeStateColor(state: string) {
  const colors: Record<string, string> = {
    done: 'success',
    active: 'primary',
  };
  return colors[state] || 'default';
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
  const ignoredEvents = new Set(['token', 'text_delta', 'reasoning', 'assistant_message', 'hitl_resolved']);

  for (const evt of rawEvents) {
    const event = evt.event_type || 'log';
    if (ignoredEvents.has(event)) continue;
    const message = logMessage(evt);
    if (!message) continue;
    result.push({
      id: evt.id,
      created_at: evt.created_at || '',
      label: eventLabel(event),
      message,
      kind: event,
    });
  }
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
  if (event === 'artifact') return data.title || evt.content || '交付物已生成';
  return eventContent(evt);
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
  grid-template-columns: 400px minmax(480px, 1fr);
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

.meeting-task-pane {
  min-height: 0;
  border-right: 1px solid var(--work-border);
  background: var(--work-panel);
}

.pane-header,
.detail-header,
.filter-row,
.toolbar-actions {
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

.toolbar-actions {
  justify-content: space-between;
  gap: 8px;
}

.toolbar-actions .v-btn:first-child {
  flex: 1;
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
  padding: 18px;
}

.chatroom-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 12px;
}

.meeting-chat-panel {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--work-panel);
}

.meeting-node-timeline {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 4px;
}

.meeting-node-card {
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel);
  overflow: hidden;
}

.meeting-node-card.active {
  border-color: rgba(var(--v-theme-primary), 0.38);
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.08);
}

.meeting-node-card.node-done {
  border-color: rgba(var(--v-theme-success), 0.24);
}

.meeting-node-header {
  width: 100%;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.meeting-node-header:hover {
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.node-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
}

.node-done .node-icon {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.1);
}

.node-title-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-title {
  font-size: 14px;
  font-weight: 700;
}

.node-subtitle {
  font-size: 12px;
  color: var(--work-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--work-muted);
  font-size: 12px;
}

.node-token {
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}

.meeting-node-body {
  border-top: 1px solid var(--work-border);
  padding: 10px 12px 12px;
  background: rgba(var(--v-theme-on-surface), 0.015);
}

.meeting-room-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--work-muted);
}

.meeting-room-caption span:first-child {
  color: rgb(var(--v-theme-on-surface));
  font-weight: 700;
}

.meeting-input-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel);
  flex-shrink: 0;
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
  cursor: pointer;
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

.stage-chip.selected {
  border-color: rgba(var(--v-theme-primary), 0.7);
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.16);
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

.node-detail-view {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.node-detail-header {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel);
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
    grid-template-columns: 320px minmax(360px, 1fr);
  }
}

@media (max-width: 820px) {
  .meeting-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }

  .meeting-task-pane {
    max-height: 210px;
    border-right: 0;
    border-bottom: 1px solid var(--work-border);
  }

  .detail-body {
    padding: 14px;
  }

  .meeting-node-header {
    grid-template-columns: 30px minmax(0, 1fr);
  }

  .node-meta {
    grid-column: 1 / -1;
    justify-content: flex-end;
  }

  .meeting-input-panel {
    grid-template-columns: 1fr;
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
