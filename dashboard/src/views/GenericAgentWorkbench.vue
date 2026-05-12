<template>
  <div class="ga-run-shell">
    <aside class="ga-run-list-pane">
      <div class="pane-header">
        <div>
          <div class="pane-title">智能RPA</div>
          <div class="pane-subtitle">OS 操作运行台</div>
        </div>
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="refreshAll" />
      </div>

      <div class="run-toolbar">
        <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" block @click="openRunDialog">
          新建任务
        </v-btn>
        <v-text-field
          v-model="searchText"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          placeholder="搜索目标、摘要或目录"
          prepend-inner-icon="mdi-magnify"
        />
        <div class="filter-row">
          <v-select
            v-model="statusFilter"
            :items="statusFilterOptions"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            label="状态"
          />
          <v-select
            v-model="sourceFilter"
            :items="sourceFilterOptions"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            label="来源"
          />
        </div>
      </div>

      <div class="run-list" @scroll.passive="handleRunListScroll">
        <button
          v-for="run in filteredRuns"
          :key="run.id"
          class="run-card"
          :class="{ active: selectedRunId === run.id, running: run.status === 'running' }"
          type="button"
          @click="selectRun(run)"
        >
          <div class="run-card-top">
            <v-chip :color="statusColor(run.status)" variant="tonal" size="x-small">
              <v-icon start size="13" :icon="statusIcon(run.status)" />
              {{ statusLabel(run.status) }}
            </v-chip>
            <span>{{ shortDate(run.created_at) }}</span>
          </div>
          <strong>{{ run.goal }}</strong>
          <p>{{ run.summary || run.error || run.constraints || '等待智能RPA生成运行摘要' }}</p>
          <v-progress-linear
            :model-value="progressValue(run)"
            :color="statusColor(run.status)"
            height="5"
            rounded
          />
          <div class="run-card-meta">
            <span><v-icon size="14" icon="mdi-source-branch" />{{ sourceLabel(run.source) }}</span>
            <span><v-icon size="14" icon="mdi-timer-outline" />{{ durationText(run) }}</span>
            <span><v-icon size="14" icon="mdi-package-variant-closed" />{{ visibleArtifactCount(run) }}</span>
          </div>
        </button>

        <div v-if="!filteredRuns.length" class="empty-list">
          <v-icon size="38" icon="mdi-timeline-clock-outline" />
          <span>{{ runs.length ? '没有匹配的任务' : '暂无智能RPA运行记录' }}</span>
        </div>
        <div v-else-if="loadingMore" class="list-footer">正在加载更多...</div>
        <div v-else-if="hasMore" class="list-footer">下拉加载更多</div>
      </div>
    </aside>

    <main class="ga-run-detail-pane">
      <template v-if="selectedRun">
        <header class="detail-header">
          <div class="detail-main">
            <div class="detail-title-row">
              <div>
                <h1>{{ selectedRun.goal }}</h1>
                <div class="detail-subtitle">
                  <span>{{ sourceLabel(selectedRun.source) }}</span>
                  <span>{{ selectedRun.workspace_path || '-' }}</span>
                  <span v-if="selectedRun.parent_task_id">父任务 {{ selectedRun.parent_task_id }}</span>
                </div>
              </div>
              <v-chip :color="statusColor(selectedRun.status)" variant="tonal" size="small">
                {{ statusLabel(selectedRun.status) }}
              </v-chip>
            </div>

            <div class="detail-facts">
              <span>进度 <strong>{{ progressValue(selectedRun) }}%</strong></span>
              <span>耗时 <strong>{{ durationText(selectedRun) }}</strong></span>
              <span>产物 <strong>{{ visibleArtifactCount(selectedRun) }}</strong></span>
              <span>队列 <strong>{{ selectedRun.queue_position || '-' }}</strong></span>
            </div>

            <v-progress-linear
              :model-value="progressValue(selectedRun)"
              :color="statusColor(selectedRun.status)"
              height="7"
              rounded
            />
          </div>
          <div class="detail-actions">
            <v-btn
              v-if="canStop(selectedRun)"
              :color="selectedRun.status === 'pending' ? 'warning' : 'error'"
              variant="tonal"
              size="small"
              :loading="stoppingRunId === selectedRun.id"
              @click="stopRun(selectedRun)"
            >
              <v-icon start :icon="selectedRun.status === 'pending' ? 'mdi-close-circle-outline' : 'mdi-stop-circle-outline'" />
              {{ selectedRun.status === 'pending' ? '取消' : '停止' }}
            </v-btn>
            <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loadingEvents" @click="loadSelectedEvents" />
          </div>
        </header>

        <v-alert v-if="selectedRun.error" type="error" variant="tonal" density="compact" class="mx-4 mt-3">
          {{ selectedRun.error }}
        </v-alert>

        <v-tabs v-model="detailTab" density="compact" class="detail-tabs">
          <v-tab value="process">
            <v-icon start size="16" icon="mdi-timeline-text-outline" />过程
          </v-tab>
          <v-tab value="artifacts">
            <v-icon start size="16" icon="mdi-package-variant-closed" />产物
          </v-tab>
          <v-tab value="audit">
            <v-icon start size="16" icon="mdi-shield-search" />审计
          </v-tab>
        </v-tabs>

        <section class="detail-body">
          <div v-if="detailTab === 'process'" class="process-timeline">
            <article
              v-for="step in processSteps"
              :key="step.id"
              class="tl-entry"
              :class="[`kind-${step.kind}`, { streaming: step.streaming }]"
            >
              <div class="tl-node">
                <v-icon size="16" :icon="step.icon" />
              </div>
              <div class="tl-body">
                <button
                  class="tl-header"
                  :class="{ clickable: step.collapsible }"
                  type="button"
                  @click="step.collapsible ? toggleProcessStep(step.id) : undefined"
                >
                  <span class="tl-title">
                    <span class="tl-kind-badge" :class="`badge-${step.kind}`">{{ stepKindLabel(step.kind) }}</span>
                    <span>{{ step.title }}</span>
                    <span v-if="step.subtitle" class="tl-subtitle">· {{ step.subtitle }}</span>
                    <v-progress-circular v-if="step.streaming" indeterminate size="12" width="2" color="primary" />
                  </span>
                  <span class="tl-right">
                    <time v-if="step.created_at" class="tl-time">{{ formatTime(step.created_at) }}</time>
                    <v-icon
                      v-if="step.collapsible"
                      size="14"
                      :icon="isProcessStepExpanded(step) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    />
                  </span>
                </button>

                <div v-if="isProcessStepExpanded(step)" class="tl-content">
                  <div v-if="step.tools.length" class="tool-chip-row">
                    <v-chip v-for="tool in step.tools" :key="tool" size="x-small" color="info" variant="tonal">
                      <v-icon start size="12" icon="mdi-wrench-outline" />{{ tool }}
                    </v-chip>
                  </div>
                  <pre v-if="step.text" class="tl-text" :class="{ 'stream-text': step.streaming, 'error-text': step.kind === 'error' }">{{ step.text }}</pre>
                  <pre v-if="step.detail" class="tl-json">{{ step.detail }}</pre>
                </div>
              </div>
            </article>

            <div v-if="!processSteps.length" class="detail-empty compact">
              暂无过程事件，任务开始后会实时追加
            </div>
          </div>

          <div v-else-if="detailTab === 'artifacts'" class="artifact-panel">
            <article v-if="finalOutputText" class="final-output-card">
              <div class="artifact-title-row">
                <div class="artifact-title-main">
                  <div class="artifact-icon">
                    <v-icon icon="mdi-text-box-check-outline" />
                  </div>
                  <div>
                    <strong>智能RPA最终输出</strong>
                    <p>{{ finalOutputArtifact?.summary || '智能RPA最后一轮交付内容' }}</p>
                  </div>
                </div>
                <span v-if="finalOutputArtifact?.size">大小 {{ formatSize(finalOutputArtifact.size) }}</span>
              </div>
              <pre>{{ finalOutputText }}</pre>
            </article>

            <div v-if="fileArtifacts.length" class="artifact-grid">
              <article v-for="artifact in fileArtifacts" :key="artifact.path" class="artifact-card">
                <div class="artifact-icon">
                  <v-icon icon="mdi-file-document-outline" />
                </div>
                <div>
                  <strong>{{ artifact.name || artifactTitle(artifact.path) }}</strong>
                  <p>{{ artifact.summary || '智能RPA运行产物' }}</p>
                  <code>{{ artifact.path }}</code>
                  <span v-if="artifact.size">大小 {{ formatSize(artifact.size) }}</span>
                </div>
              </article>
            </div>

            <div v-if="!finalOutputText && !fileArtifacts.length" class="detail-empty compact">
              任务完成后会在这里显示文件、截图或摘要产物
            </div>
          </div>

          <div v-else class="audit-list">
            <article v-for="event in auditEvents" :key="event.id" class="audit-row">
              <v-chip :color="eventColor(event.event_type)" size="x-small" variant="tonal">
                {{ event.event_type }}
              </v-chip>
              <div>
                <strong>{{ event.title || event.event_type }}</strong>
                <span>{{ formatDate(event.created_at) }}</span>
                <pre v-if="eventPreview(event)">{{ eventPreview(event) }}</pre>
              </div>
            </article>
            <div v-if="!auditEvents.length" class="detail-empty compact">
              暂无工具、文件、浏览器或停止审计事件
            </div>
          </div>
        </section>
      </template>

      <div v-else class="detail-empty">
        <v-icon size="58" icon="mdi-desktop-classic" />
        <div>选择一个智能RPA任务查看详情</div>
      </div>
    </main>

    <v-dialog v-model="runDialogOpen" max-width="760">
      <v-card class="dialog-card">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-plus-box-outline" class="mr-2" />
          新建智能RPA任务
        </v-card-title>
        <v-card-text class="dialog-grid">
          <v-textarea
            v-model="runForm.goal"
            label="目标"
            variant="outlined"
            rows="3"
            auto-grow
            autofocus
            placeholder="例如：在指定目录整理日志并生成摘要"
          />
          <v-text-field
            v-model="runForm.workspace_path"
            label="工作目录"
            variant="outlined"
            placeholder="留空时使用默认工作目录"
          />
          <v-textarea
            v-model="runForm.constraints"
            label="自然语言约束"
            variant="outlined"
            rows="4"
            auto-grow
            placeholder="例如：只操作指定目录；不要删除文件；不要提交代码"
          />
          <v-textarea
            v-model="runForm.expected_outputs_text"
            label="期望产物"
            variant="outlined"
            rows="3"
            auto-grow
            placeholder="每行一个，例如：运行摘要、生成文件路径、截图"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="runDialogOpen = false">取消</v-btn>
          <v-btn color="primary" :loading="creatingRun" @click="createRun">加入队列</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3200">
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import { usePagedTaskList } from '@/composables/usePagedTaskList';
import { useSelectedEventStream } from '@/composables/useSelectedEventStream';

const route = useRoute();

type GenericAgentRun = {
  id: string;
  source: string;
  goal: string;
  constraints?: string;
  expected_outputs?: string[];
  workspace_path?: string;
  parent_task_id?: string;
  status: string;
  queue_position?: number;
  progress?: number;
  summary?: string;
  artifacts?: GenericAgentArtifact[];
  error?: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at?: string;
};

type GenericAgentArtifact = {
  name?: string;
  path: string;
  size?: number;
  summary?: string;
  content?: string;
  artifact_type?: string;
  type?: string;
};

type GenericAgentEvent = {
  id: string;
  seq?: number;
  event_type: string;
  title?: string;
  payload?: Record<string, any>;
  created_at: string;
};

type ProcessStep = {
  id: string;
  kind: string;
  icon: string;
  title: string;
  subtitle?: string;
  text: string;
  detail?: string;
  tools: string[];
  created_at: string;
  collapsible: boolean;
  streaming?: boolean;
};

type AgentTurn = {
  turn?: number;
  text: string;
};

const events = ref<GenericAgentEvent[]>([]);
const selectedRunId = ref('');
const detailTab = ref('process');
const searchText = ref('');
const statusFilter = ref('');
const sourceFilter = ref('');
const loading = ref(false);
const loadingEvents = ref(false);
const creatingRun = ref(false);
const stoppingRunId = ref('');
const runDialogOpen = ref(false);
const defaultWorkspacePath = ref('');
const snackbar = reactive({ show: false, text: '', color: 'success' });
const expandedProcessStepIds = ref<Set<string>>(new Set());
let summaryRefreshTimer: ReturnType<typeof setInterval> | null = null;

const runList = usePagedTaskList<GenericAgentRun>({
  pageSize: 30,
  loadPage: loadRunPage,
});
const runs = runList.items;
const loadingMore = runList.loadingMore;
const hasMore = runList.hasMore;
const runStream = useSelectedEventStream({
  eventNames: [
    'phase',
    'queued',
    'lifecycle',
    'process',
    'llm_chunk',
    'tool_call',
    'terminal',
    'skill_review',
    'stop_requested',
    'force_kill',
    'timeout',
    'cancelled',
    'completed',
    'failed',
    'error',
    'done',
    'heartbeat',
  ],
  streamUrl: (runId, afterSeq) => `/api/plug/generic-agent/runs/${encodeURIComponent(runId)}/events?after_seq=${afterSeq}`,
  getAfterSeq: maxEventSeq,
  onEvent: handleRunStreamEvent,
  onFallback: runId => loadRunEvents(runId, maxEventSeq()),
  shouldReconnect: runId => selectedRunId.value === runId && !isTerminalRun(selectedRun.value),
});

const runForm = reactive({
  goal: '',
  workspace_path: '',
  constraints: '',
  expected_outputs_text: '',
});

const statusFilterOptions = [
  { title: '等待中', value: 'pending' },
  { title: '运行中', value: 'running' },
  { title: '已完成', value: 'completed' },
  { title: '失败', value: 'failed' },
  { title: '已取消', value: 'cancelled' },
];

const selectedRun = computed(() => runs.value.find((run) => run.id === selectedRunId.value) || null);
const sourceFilterOptions = computed(() => {
  const values = [...new Set(runs.value.map((run) => run.source || 'manual'))];
  return values.map((value) => ({ title: sourceLabel(value), value }));
});

const orderedRuns = computed(() =>
  [...runs.value].sort((a, b) => {
    const priority = (run: GenericAgentRun) => (run.status === 'running' ? 0 : run.status === 'pending' ? 1 : 2);
    const diff = priority(a) - priority(b);
    if (diff !== 0) return diff;
    if (a.status === 'pending' && b.status === 'pending') {
      return (a.queue_position || 0) - (b.queue_position || 0);
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  }),
);

const filteredRuns = computed(() => {
  return orderedRuns.value;
});

const llmStreamText = computed(() =>
  events.value
    .filter((event) => event.event_type === 'llm_chunk')
    .map((event) => eventText(event))
    .filter(Boolean)
    .join('\n'),
);

const processSteps = computed<ProcessStep[]>(() => {
  const steps: ProcessStep[] = [];
  const phaseTypes = new Set(['queued', 'lifecycle', 'process', 'stop_requested', 'force_kill', 'timeout', 'cancelled']);

  for (const event of events.value) {
    if (!phaseTypes.has(event.event_type)) continue;
    const text = eventPreview(event);
    steps.push({
      id: event.id,
      kind: phaseStepKind(event.event_type),
      icon: processStepIcon(event.event_type),
      title: event.title || event.event_type,
      subtitle: event.event_type === 'process' ? processPidText(event) : '',
      text,
      tools: [],
      created_at: event.created_at,
      collapsible: Boolean(text),
    });
  }

  const turns = splitAgentTurns(llmStreamText.value);
  turns.forEach((turn, index) => {
    const tools = extractToolNames(turn.text);
    const summary = extractTurnSummary(turn.text);
    const title = turn.turn ? `第 ${turn.turn} 轮：${summary || '执行中'}` : summary || '智能RPA输出';
    const streaming = isLatestTurn(index, turns.length);
    steps.push({
      id: turn.turn ? `turn-${turn.turn}` : `turn-${index}`,
      kind: tools.length ? 'tool_call' : 'text_delta',
      icon: tools.length ? 'mdi-wrench-outline' : 'mdi-message-text-outline',
      title,
      subtitle: tools.length ? `${tools.length} 个工具调用` : '',
      text: cleanAgentTurnText(turn.text),
      tools,
      created_at: turnCreatedAt(turn.turn, index),
      collapsible: true,
      streaming,
    });
  });

  const terminalDigest = filteredTerminalDigest.value;
  if (terminalDigest.summary) {
    steps.push({
      id: 'terminal-diagnostics',
      kind: 'log',
      icon: 'mdi-console-line',
      title: '运行输出',
      subtitle: terminalDigest.collapsed ? '已折叠重复重试日志' : '已过滤重复上下文',
      text: terminalDigest.summary,
      detail: terminalDigest.raw && terminalDigest.raw !== terminalDigest.summary ? terminalDigest.raw : '',
      tools: [],
      created_at: lastEventTime(['terminal', 'output']) || selectedRun.value?.updated_at || selectedRun.value?.created_at || '',
      collapsible: true,
    });
  }

  const outcome = [...events.value].reverse().find((event) => ['failed', 'error'].includes(event.event_type));
  if (outcome) {
    steps.push({
      id: `outcome-${outcome.id}`,
      kind: 'error',
      icon: 'mdi-alert-circle-outline',
      title: '执行失败',
      subtitle: selectedRun.value ? statusLabel(selectedRun.value.status) : '',
      text: selectedRun.value?.error || eventPreview(outcome),
      tools: [],
      created_at: outcome.created_at,
      collapsible: true,
    });
  }

  return steps.sort((a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime());
});

const filteredTerminalDigest = computed(() => buildTerminalDigest(events.value, llmStreamText.value));
const finalOutputArtifact = computed(() => {
  const artifact = (selectedRun.value?.artifacts || []).find(isFinalOutputArtifact) || null;
  return artifact && !isErrorOnlyOutput(artifact.content || '') ? artifact : null;
});
const fileArtifacts = computed(() => visibleArtifacts(selectedRun.value).filter((artifact) => !isFinalOutputArtifact(artifact)));
const finalOutputText = computed(() =>
  finalOutputArtifact.value?.content || latestAgentFinalOutput() || (selectedRun.value?.status === 'completed' ? selectedRun.value?.summary : '') || '',
);

const auditEvents = computed(() =>
  events.value.filter((event) =>
    /(tool|file|browser|web|stop|kill|cancel|error|timeout|skill)/.test(event.event_type),
  ),
);

watch(selectedRunId, () => {
  expandedProcessStepIds.value = new Set();
});

watch([searchText, statusFilter, sourceFilter], () => {
  reloadRunsForFilters().catch(() => undefined);
});

onMounted(async () => {
  await refreshAll();
  startSummaryRefresh();
});

onUnmounted(() => {
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  runStream.close();
});

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadRuns(), loadConfig()]);
    const hadSelection = Boolean(selectedRun.value);
    await ensureSelectedRun();
    if (hadSelection && selectedRun.value) await loadSelectedEvents(true);
  } catch (error: any) {
    showSnack(errorMessage(error, '加载智能RPA运行页失败'), 'error');
  } finally {
    loading.value = false;
  }
}

async function loadRuns() {
  await runList.loadFirstPage();
}

async function loadRunPage(page: number, pageSize: number) {
  const response = await axios.get('/api/plug/generic-agent/runs', {
    params: {
      page,
      page_size: pageSize,
      q: searchText.value.trim() || undefined,
      status: statusFilter.value || undefined,
      source: sourceFilter.value || undefined,
    },
  });
  const data = response.data?.data || {};
  return {
    items: data.runs || [],
    pagination: data.pagination,
  };
}

async function loadConfig() {
  const response = await axios.get('/api/plug/generic-agent/config');
  defaultWorkspacePath.value = response.data?.data?.default_workspace_path || '';
}

async function loadSelectedEvents(replace = true) {
  if (!selectedRun.value) return;
  loadingEvents.value = true;
  try {
    if (replace) {
      const response = await axios.get(`/api/plug/generic-agent/runs/${selectedRun.value.id}/events`, {
        params: { stream: 0, limit: 1200 },
      });
      const data = response.data?.data;
      events.value = Array.isArray(data) ? data : [];
    } else {
      await loadRunEvents(selectedRun.value.id, maxEventSeq());
    }
  } catch (error: any) {
    showSnack(errorMessage(error, '加载任务事件失败'), 'error');
  } finally {
    loadingEvents.value = false;
  }
}

async function loadRunEvents(runId: string, afterSeq = 0) {
  const response = await axios.get(`/api/plug/generic-agent/runs/${encodeURIComponent(runId)}/events`, {
    params: { stream: 0, limit: 500, after_seq: afterSeq || undefined },
  });
  const data = response.data?.data;
  if (Array.isArray(data)) {
    for (const event of data) appendRunEvent(event);
  }
}

async function reloadRunsForFilters() {
  runStream.close();
  selectedRunId.value = '';
  events.value = [];
  await loadRuns();
  await ensureSelectedRun();
}

function handleRunListScroll(event: Event) {
  const target = event.target as HTMLElement | null;
  if (!target) return;
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 120) {
    runList.loadMore().catch(() => undefined);
  }
}

function startSummaryRefresh() {
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  summaryRefreshTimer = setInterval(() => {
    if (!document.hidden) refreshRunSummaries().catch(() => undefined);
  }, 5000);
}

async function refreshRunSummaries() {
  const ids = runList.loadedIds.value;
  if (!ids.length) return;
  const response = await axios.get('/api/plug/generic-agent/runs/summaries', {
    params: { ids: ids.join(',') },
  });
  if (response.data?.status !== 'ok') return;
  const summaries: GenericAgentRun[] = response.data.data?.runs || [];
  runList.mergeSummaries(summaries);
}

function openRunStream(runId: string) {
  if (isTerminalRun(selectedRun.value)) return;
  runStream.open(runId);
}

function handleRunStreamEvent(name: string, payload: any) {
  if (name === 'heartbeat') return;
  if (name === 'phase') {
    mergeSelectedRun(payload);
    return;
  }
  if (name === 'done') {
    mergeSelectedRun(payload);
    runStream.close();
    refreshRunSummaries().catch(() => undefined);
    return;
  }
  if (payload?.id) appendRunEvent(payload);
  if (['completed', 'failed', 'cancelled'].includes(name)) {
    mergeSelectedRun({
      status: name === 'failed' ? 'failed' : name === 'cancelled' ? 'cancelled' : 'completed',
      progress: name === 'completed' ? 100 : selectedRun.value?.progress,
    });
    runStream.close();
  }
}

function mergeSelectedRun(summary: any) {
  const id = summary?.id || selectedRun.value?.id;
  if (!id) return;
  runList.mergeSummaries([{ id, ...summary }]);
}

function appendRunEvent(event: GenericAgentEvent) {
  if (!event?.id) return;
  if (events.value.some(item => item.id === event.id)) return;
  events.value = [...events.value, event]
    .sort((a, b) => Number(a.seq || 0) - Number(b.seq || 0))
    .slice(-2000);
}

function maxEventSeq() {
  return events.value.reduce((max, event) => Math.max(max, Number(event.seq || 0)), 0);
}

async function ensureSelectedRun() {
  if (selectedRun.value) return;
  const queryRunId = typeof route.query.run === 'string' ? route.query.run : '';
  if (queryRunId) {
    const existing = runs.value.find((run) => run.id === queryRunId);
    if (existing) {
      selectedRunId.value = existing.id;
    } else {
      try {
        const response = await axios.get(`/api/plug/generic-agent/runs/${encodeURIComponent(queryRunId)}`);
        const run = response.data?.data;
        if (run?.id) {
          runList.replaceItem(run);
          selectedRunId.value = run.id;
        }
      } catch {
        selectedRunId.value = '';
      }
    }
  }
  if (selectedRunId.value) {
    detailTab.value = 'process';
    await loadSelectedEvents(true);
    openRunStream(selectedRunId.value);
    return;
  }
  const running = runs.value.find((run) => run.status === 'running');
  selectedRunId.value = running?.id || orderedRuns.value[0]?.id || '';
  detailTab.value = 'process';
  if (selectedRunId.value) {
    await loadSelectedEvents(true);
    openRunStream(selectedRunId.value);
  }
}

function selectRun(run: GenericAgentRun) {
  if (selectedRunId.value === run.id) {
    loadSelectedEvents(false);
    if (!runStream.connected.value && !isTerminalRun(run)) openRunStream(run.id);
    return;
  }
  runStream.close();
  selectedRunId.value = run.id;
  detailTab.value = 'process';
  events.value = [];
  loadSelectedEvents(true).then(() => openRunStream(run.id));
}

function openRunDialog() {
  runForm.goal = '';
  runForm.workspace_path = defaultWorkspacePath.value;
  runForm.constraints = '只操作指定工作目录；不要删除无关文件；不要提交代码；如遇高风险动作请在结果中说明。';
  runForm.expected_outputs_text = '';
  runDialogOpen.value = true;
}

async function createRun() {
  if (!runForm.goal.trim()) {
    showSnack('请先填写任务目标。', 'warning');
    return;
  }
  creatingRun.value = true;
  try {
    const response = await axios.post('/api/plug/generic-agent/runs', {
      goal: runForm.goal.trim(),
      workspace_path: runForm.workspace_path.trim(),
      constraints: runForm.constraints.trim(),
      expected_outputs: runForm.expected_outputs_text
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      source: 'manual',
    });
    runDialogOpen.value = false;
    const run = response.data?.data;
    if (run?.id) {
      runList.replaceItem(run);
      selectRun(run);
    }
    showSnack('智能RPA任务已加入队列。', 'success');
    await refreshRunSummaries();
  } catch (error: any) {
    showSnack(errorMessage(error, '创建智能RPA任务失败'), 'error');
  } finally {
    creatingRun.value = false;
  }
}

async function stopRun(run: GenericAgentRun) {
  stoppingRunId.value = run.id;
  try {
    await axios.post(`/api/plug/generic-agent/runs/${run.id}/stop`);
    showSnack(run.status === 'pending' ? '任务已取消。' : '已请求智能RPA停止。', 'success');
    await refreshRunSummaries();
    if (selectedRunId.value === run.id) await loadSelectedEvents(false);
  } catch (error: any) {
    showSnack(errorMessage(error, '停止智能RPA任务失败'), 'error');
  } finally {
    stoppingRunId.value = '';
  }
}

function canStop(run: GenericAgentRun) {
  return ['pending', 'running'].includes(run.status);
}

function isTerminalRun(run: GenericAgentRun | null) {
  return ['completed', 'failed', 'cancelled'].includes(run?.status || '');
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  };
  return map[status] || status;
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    running: 'primary',
    completed: 'success',
    failed: 'error',
    cancelled: 'grey',
  };
  return map[status] || 'grey';
}

function statusIcon(status: string) {
  const map: Record<string, string> = {
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    completed: 'mdi-check-circle-outline',
    failed: 'mdi-alert-circle-outline',
    cancelled: 'mdi-cancel',
  };
  return map[status] || 'mdi-circle-outline';
}

function progressValue(run: GenericAgentRun) {
  if (run.status === 'completed') return 100;
  return Math.max(0, Math.min(100, Number(run.progress || 0)));
}

function sourceLabel(source?: string) {
  const map: Record<string, string> = {
    manual: '手动',
    chat: 'Chat',
    task: '任务模块',
    meeting: '会议模块',
    system: '系统',
  };
  return map[source || 'manual'] || source || '手动';
}

function toggleProcessStep(id: string) {
  const next = new Set(expandedProcessStepIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  expandedProcessStepIds.value = next;
}

function isProcessStepExpanded(step: ProcessStep) {
  if (step.streaming || step.kind === 'error') return true;
  return expandedProcessStepIds.value.has(step.id);
}

function stepKindLabel(kind: string) {
  const map: Record<string, string> = {
    phase: '阶段',
    text_delta: '输出',
    tool_call: '工具',
    log: '输出',
    error: '错误',
    result: '结果',
  };
  return map[kind] || kind;
}

function phaseStepKind(type: string) {
  if (type.includes('error') || type.includes('timeout') || type.includes('kill')) return 'error';
  if (type.includes('stop') || type.includes('cancel')) return 'log';
  return 'phase';
}

function processStepIcon(type: string) {
  if (type.includes('queued')) return 'mdi-clock-outline';
  if (type.includes('process')) return 'mdi-chip';
  if (type.includes('stop') || type.includes('cancel')) return 'mdi-stop-circle-outline';
  if (type.includes('error') || type.includes('timeout') || type.includes('kill')) return 'mdi-alert-circle-outline';
  return 'mdi-timeline-clock-outline';
}

function processPidText(event: GenericAgentEvent) {
  const pid = event.payload?.pid;
  return pid ? `PID ${pid}` : '';
}

function splitAgentTurns(text: string): AgentTurn[] {
  const source = text.trim();
  if (!source) return [];
  const matches = [...source.matchAll(/\*\*Turn\s+(\d+)\s+\.\.\.\*\*/g)];
  if (!matches.length) return [{ text: source }];
  return matches.map((match, index) => {
    const start = match.index || 0;
    const end = matches[index + 1]?.index ?? source.length;
    return {
      turn: Number(match[1]),
      text: source.slice(start, end).trim(),
    };
  });
}

function extractTurnSummary(text: string) {
  const summary = text.match(/<summary>([\s\S]*?)<\/summary>/i)?.[1];
  const candidate = summary || cleanAgentTurnText(text).split('\n').find((line) => line.trim() && !line.includes('Tool:')) || '';
  return compactText(candidate, 72) || '执行中';
}

function latestAgentFinalOutput() {
  const turns = splitAgentTurns(llmStreamText.value);
  const last = turns[turns.length - 1];
  if (!last) return '';
  const output = cleanFinalOutputText(last.text);
  return isErrorOnlyOutput(output) ? '' : output;
}

function cleanAgentTurnText(text: string) {
  return text
    .replace(/^\*\*Turn\s+\d+\s+\.\.\.\*\*/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function cleanFinalOutputText(text: string) {
  return cleanAgentTurnText(text)
    .replace(/<summary>.*?<\/summary>/gis, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function isFinalOutputArtifact(artifact: GenericAgentArtifact) {
  const path = artifact.path || '';
  return (
    artifact.artifact_type === 'final_output' ||
    artifact.type === 'final_output' ||
    artifact.name === 'GenericAgent 最终输出' ||
    artifact.name === '智能RPA最终输出' ||
    /(^|[\\/])output\.txt$/i.test(path)
  );
}

function visibleArtifacts(run: GenericAgentRun | null) {
  return (run?.artifacts || []).filter((artifact) => {
    if (!isFinalOutputArtifact(artifact)) return true;
    return !isErrorOnlyOutput(artifact.content || '');
  });
}

function visibleArtifactCount(run: GenericAgentRun) {
  return visibleArtifacts(run).length;
}

function isErrorOnlyOutput(text: string) {
  const source = String(text || '');
  if (!source.includes('!!!Error:') && !source.includes('APIConnectionError')) return false;
  const cleaned = source
    .replace(/<thinking>[\s\S]*?<\/thinking>/g, '')
    .replace(/<summary>[\s\S]*?<\/summary>/gi, '')
    .replace(/\*\*Turn\s+\d+\s+\.\.\.\*\*/g, '')
    .replace(/!!!Error:\s*[^\n`]+/g, '')
    .replace(/APIConnectionError|ConnectionError|Timeout/g, '')
    .replace(/\[Info\] Final response to user\./g, '')
    .replace(/\[ROUND END\]/g, '')
    .replace(/`+/g, '')
    .replace(/\s+/g, '');
  return cleaned.length < 24;
}

function extractToolNames(text: string) {
  const names = [...text.matchAll(/Tool:\s*`([^`]+)`/g)].map((match) => match[1]);
  return [...new Set(names)];
}

function isLatestTurn(index: number, total: number) {
  return selectedRun.value?.status === 'running' && total > 0 && index === total - 1;
}

function turnCreatedAt(turn?: number, fallbackIndex = 0) {
  const chunkEvents = events.value.filter((event) => event.event_type === 'llm_chunk');
  if (turn) {
    const marker = `**Turn ${turn} ...**`;
    const matched = chunkEvents.find((event) => eventText(event).includes(marker));
    if (matched?.created_at) return matched.created_at;
  }
  return chunkEvents[fallbackIndex]?.created_at || selectedRun.value?.started_at || selectedRun.value?.created_at || '';
}

function lastEventTime(types: string[]) {
  return [...events.value].reverse().find((event) => types.includes(event.event_type))?.created_at || '';
}

function eventText(event: GenericAgentEvent) {
  const payload = event.payload || {};
  const value = payload.text || payload.message || payload.summary || payload.result || '';
  return value === undefined || value === null ? '' : String(value);
}

function buildTerminalDigest(items: GenericAgentEvent[], streamText: string) {
  const lines: string[] = [];
  const rawLines: string[] = [];
  const seen = new Map<string, number>();
  const retryStats = new Map<string, { current: number; total: number }>();

  for (const event of items) {
    if (!['terminal', 'output'].includes(event.event_type) && !event.event_type.includes('terminal')) continue;
    for (const line of eventText(event).split(/\r?\n/)) {
      const normalized = line.trim();
      if (!normalized || isNoisyTerminalLine(normalized)) continue;
      rawLines.push(redactTerminalLine(line.trimEnd()));
      const retry = normalized.match(/^\[LLM Retry\]\s+(.+?),\s+retry in .*?\((\d+)\/(\d+)\)/i);
      if (retry) {
        retryStats.set(retry[1], {
          current: Math.max(Number(retry[2]), retryStats.get(retry[1])?.current || 0),
          total: Math.max(Number(retry[3]), retryStats.get(retry[1])?.total || 0),
        });
        continue;
      }
      if (normalized.length > 12 && streamText.includes(normalized)) continue;
      const count = seen.get(normalized) || 0;
      if (count >= 2) continue;
      seen.set(normalized, count + 1);
      lines.push(redactTerminalLine(line.trimEnd()));
    }
  }

  const retryLines = [...retryStats.entries()].map(([reason, stat]) =>
    `[LLM Retry] ${reason}，已重试 ${stat.current}/${stat.total} 次`,
  );
  const summary = [...retryLines, ...lines].slice(-220).join('\n');
  const raw = rawLines.slice(-260).join('\n');
  return {
    summary,
    raw,
    collapsed: retryStats.size > 0,
  };
}

function isNoisyTerminalLine(line: string) {
  if (['### [WORKING MEMORY]', '<history>', '</history>', 'code run output:'].includes(line)) return true;
  if (/^Current turn:\s*\d+/i.test(line)) return true;
  return (
    line.startsWith('[Debug]') ||
    line.startsWith('[Cache]') ||
    line.startsWith('[Cut]') ||
    line.startsWith('[USER]') ||
    line.startsWith('[Agent]')
  );
}

function redactTerminalLine(line: string) {
  return line.replace(/(api[_-]?key|apikey|authorization|token)(\s*[:=]\s*)\S+/gi, '$1$2***');
}

function compactText(value: string, max = 120) {
  const text = String(value || '')
    .replace(/<summary>|<\/summary>/gi, '')
    .replace(/[`*_#>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function eventColor(type: string) {
  if (type.includes('error') || type.includes('timeout')) return 'error';
  if (type.includes('tool') || type.includes('process')) return 'primary';
  if (type.includes('skill')) return 'success';
  if (type.includes('cancel') || type.includes('stop')) return 'warning';
  return 'grey';
}

function eventPreview(event: GenericAgentEvent) {
  const payload = event.payload || {};
  const value =
    payload.text ||
    payload.message ||
    payload.summary ||
    payload.tool_name ||
    payload.path ||
    payload.review_id ||
    '';
  if (value) return String(value).slice(0, 3000);
  const compact = JSON.stringify(payload);
  return compact && compact !== '{}' ? compact.slice(0, 1200) : '';
}

function durationText(run: GenericAgentRun) {
  const start = run.started_at || run.created_at;
  if (!start) return '-';
  const end = run.completed_at || (run.status === 'running' ? new Date().toISOString() : run.updated_at || run.created_at);
  const diff = Math.max(0, new Date(end).getTime() - new Date(start).getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h${minutes % 60}m`;
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function formatTime(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function shortDate(value?: string | null) {
  if (!value) return '-';
  return new Date(value).toLocaleString([], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function artifactTitle(path?: string) {
  if (!path) return '产物';
  return path.split(/[\\/]/).pop() || path;
}

function formatSize(size?: number) {
  if (!size) return '-';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function showSnack(text: string, color: string) {
  snackbar.text = text;
  snackbar.color = color;
  snackbar.show = true;
}

function errorMessage(error: any, fallback: string) {
  return error?.response?.data?.message || error?.response?.data?.error || error?.message || fallback;
}
</script>

<style scoped>
.ga-run-shell {
  height: calc(100vh - 64px);
  min-height: 720px;
  display: grid;
  grid-template-columns: 400px minmax(480px, 1fr);
  background: rgb(var(--v-theme-background));
  overflow: hidden;
}

.ga-run-list-pane {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
  overflow: hidden;
}

.pane-header,
.run-card-top,
.detail-title-row,
.detail-header,
.detail-actions,
.audit-row,
.artifact-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.pane-title {
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: 0;
}

.pane-subtitle,
.run-card p,
.run-card-meta,
.detail-subtitle,
.tl-subtitle,
.artifact-card p,
.audit-row span {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.run-toolbar {
  display: grid;
  gap: 12px;
}

.filter-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.run-list {
  min-height: 0;
  display: grid;
  align-content: start;
  gap: 10px;
  overflow-y: auto;
  padding-right: 4px;
}

.run-card {
  width: 100%;
  display: grid;
  gap: 9px;
  padding: 12px;
  text-align: left;
  color: inherit;
  background: transparent;
  border: 1px solid rgba(var(--v-border-color), 0.24);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 160ms ease, background 160ms ease;
}

.run-card:hover,
.run-card.active {
  border-color: rgba(var(--v-theme-primary), 0.46);
  background: rgba(var(--v-theme-primary), 0.055);
}

.run-card.running {
  border-color: rgba(var(--v-theme-primary), 0.72);
}

.run-card strong,
.run-card p {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 0.78rem;
}

.run-card-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.empty-list,
.detail-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 220px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  text-align: center;
}

.list-footer {
  padding: 10px 0 4px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 0.78rem;
}

.ga-run-detail-pane {
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  align-items: flex-start;
  padding: 18px 22px 14px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
}

.detail-main {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 12px;
}

h1 {
  margin: 0;
  font-size: 1.46rem;
  line-height: 1.22;
  letter-spacing: 0;
}

.detail-subtitle,
.detail-facts {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.detail-subtitle {
  margin-top: 5px;
  font-size: 0.86rem;
}

.detail-facts {
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 0.86rem;
}

.detail-actions {
  flex-wrap: wrap;
}

.detail-tabs {
  padding: 0 18px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
}

.detail-body {
  min-height: 0;
  flex: 1;
  overflow: auto;
  padding: 18px 22px 24px;
}

.artifact-card,
.audit-row {
  border: 1px solid rgba(var(--v-border-color), 0.22);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.process-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: 1180px;
}

.tl-entry {
  display: flex;
  gap: 10px;
  padding: 8px 12px 8px 8px;
  border-left: 2px solid transparent;
  transition: background 0.12s;
}

.tl-entry:hover {
  background: rgba(var(--v-theme-on-surface), 0.025);
}

.tl-entry.streaming {
  border-left-color: rgba(var(--v-theme-primary), 0.36);
}

.tl-node {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.48);
}

.tl-body {
  flex: 1;
  min-width: 0;
}

.tl-header {
  width: 100%;
  min-height: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: default;
}

.tl-header.clickable {
  cursor: pointer;
}

.tl-title {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 13px;
  font-weight: 550;
}

.tl-kind-badge {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.tl-subtitle {
  font-size: 11px;
  font-weight: 400;
}

.tl-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.tl-time {
  color: rgba(var(--v-theme-on-surface), 0.38);
  font-family: 'Courier New', monospace;
  font-size: 10px;
}

.tl-content {
  margin-top: 6px;
}

.tool-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.tl-text,
.tl-json,
.audit-row pre {
  margin: 8px 0 0;
  padding: 8px 10px;
  max-height: 420px;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}

.tl-text {
  color: rgba(var(--v-theme-on-surface), 0.68);
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.tl-json,
.audit-row pre {
  color: rgba(var(--v-theme-on-surface), 0.72);
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-border-color), 0.12);
  font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
  font-size: 11px;
}

.stream-text {
  border-left: 3px solid rgba(var(--v-theme-primary), 0.22);
}

.error-text {
  color: rgb(var(--v-theme-error));
  font-weight: 550;
}

.badge-text_delta,
.badge-log {
  color: rgba(var(--v-theme-on-surface), 0.55);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.badge-phase,
.badge-result {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.badge-tool_call {
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.12);
}

.badge-error {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.1);
}

.kind-tool_call .tl-node {
  color: rgb(var(--v-theme-info));
  background: rgba(var(--v-theme-info), 0.1);
}

.kind-result .tl-node {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.1);
}

.kind-error .tl-node {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.1);
}

.kind-phase .tl-node {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.artifact-panel {
  display: grid;
  gap: 12px;
}

.artifact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.final-output-card,
.artifact-card {
  padding: 13px;
}

.final-output-card {
  border: 1px solid rgba(var(--v-border-color), 0.22);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.final-output-card pre {
  margin: 12px 0 0;
  padding: 12px;
  max-height: none;
  overflow: auto;
  color: rgba(var(--v-theme-on-surface), 0.78);
  background: rgba(var(--v-theme-on-surface), 0.035);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.artifact-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.1);
  border-radius: 8px;
}

.artifact-title-row,
.artifact-title-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.artifact-title-main {
  justify-content: flex-start;
}

.artifact-card code {
  display: block;
  margin: 6px 0;
  overflow-wrap: anywhere;
  color: rgba(var(--v-theme-on-surface), 0.74);
}

.artifact-card span {
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 0.78rem;
}

.audit-list {
  display: grid;
  gap: 10px;
}

.audit-row {
  align-items: flex-start;
  justify-content: flex-start;
  padding: 12px;
}

.audit-row > div {
  min-width: 0;
}

.detail-empty.compact {
  min-height: 180px;
}

.dialog-card {
  border-radius: 8px;
}

.dialog-grid {
  display: grid;
  gap: 12px;
}

@media (max-width: 1100px) {
  .ga-run-shell {
    height: auto;
    min-height: 100%;
    grid-template-columns: 1fr;
    overflow: visible;
  }

  .ga-run-list-pane {
    max-height: 520px;
    border-right: 0;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }

  .artifact-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .detail-header,
  .pane-header,
  .detail-title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-header,
  .detail-body {
    padding-left: 14px;
    padding-right: 14px;
  }

  .filter-row {
    grid-template-columns: 1fr;
  }
}
</style>
