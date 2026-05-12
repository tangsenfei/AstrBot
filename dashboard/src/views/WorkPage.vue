<template>
  <div class="work-shell" :class="{ 'is-dark': isDark }">
    <aside class="work-task-pane">
      <div class="task-toolbar">
        <div class="toolbar-actions">
          <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openTaskDialog">
            新建任务
          </v-btn>
          <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="refreshAll" />
        </div>
        <v-text-field
          v-model="searchQuery"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          placeholder="搜索任务"
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
            v-model="kindFilter"
            :items="kindOptions"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            label="类型"
          />
        </div>
      </div>

      <WorkTaskList
        class="task-list"
        :tasks="filteredTasks"
        :selected-task-id="selectedTaskId"
        :loading="loading"
        :loading-more="loadingMore"
        :has-more="hasMore"
        :is-dark="isDark"
        @scroll.passive="handleTaskListScroll"
        @select="selectTask"
        @hitl-open="openTaskHitl"
        @interaction-respond="handleInteractionRespond"
      />
    </aside>

    <main class="work-detail-pane">
      <template v-if="selectedTask">
        <header class="detail-header">
          <div class="detail-main">
            <div class="detail-title-row">
              <div class="detail-title">{{ selectedTask.name }}</div>
              <div class="detail-subtitle inline">
                <span>{{ taskKindLabel(selectedTask.work_task_kind || selectedTask.task_type) }}</span>
                <span v-if="selectedExecutorLabel">{{ selectedExecutorLabel }}</span>
                <span>{{ statusLabel(selectedTask.status) }}</span>
                <span>{{ selectedTask.progress || 0 }}%</span>
              </div>
            </div>
            <div class="token-inline">
              <v-icon size="15" icon="mdi-counter" />
              <strong>{{ formatTokens(selectedTask.total_tokens) }}</strong>
              <span>输入 {{ formatTokens(selectedTask.input_tokens) }}</span>
              <span>输出 {{ formatTokens(selectedTask.output_tokens) }}</span>
            </div>
          </div>
          <div class="detail-actions">
            <v-chip :prepend-icon="taskModeIcon(selectedTaskMode)" color="primary" size="small" variant="tonal">
              任务模式：{{ taskModeLabel(selectedTaskMode) }}
            </v-chip>
            <v-btn
              v-if="canPauseTask"
              size="small"
              variant="tonal"
              prepend-icon="mdi-pause"
              :loading="controllingTask === 'pause'"
              @click="controlTask('pause')"
            >
              暂停
            </v-btn>
            <v-btn
              v-else-if="isPauseRequested"
              size="small"
              variant="tonal"
              prepend-icon="mdi-pause-circle-outline"
              disabled
            >
              暂停中
            </v-btn>
            <v-btn
              v-if="canResumeTask"
              size="small"
              color="primary"
              variant="tonal"
              prepend-icon="mdi-play"
              :loading="controllingTask === 'resume'"
              @click="controlTask('resume')"
            >
              继续
            </v-btn>
            <v-btn
              v-if="canTerminateTask"
              size="small"
              color="error"
              variant="tonal"
              prepend-icon="mdi-stop-circle-outline"
              :loading="controllingTask === 'terminate'"
              @click="controlTask('terminate')"
            >
              终止
            </v-btn>
            <v-chip :color="statusColor(selectedTask.status)" size="small" variant="tonal">
              {{ statusLabel(selectedTask.status) }}
            </v-chip>
            <v-btn icon="mdi-refresh" size="small" variant="text" @click="loadSelectedTask" />
          </div>
        </header>

        <div v-if="stageSteps.length" class="detail-stage-strip">
          <div
            v-for="(stage, idx) in stageSteps"
            :key="stage.id"
            class="stage-chip"
            :class="{
              'stage-done': stage.status === 'done' || stage.status === 'completed',
              'stage-running': stage.status === 'running',
              'stage-pending': stage.status === 'pending',
              'stage-failed': stage.status === 'failed' || stage.status === 'retryable_failed',
              active: selectedStageIndex === idx,
            }"
            @click="selectStage(idx)"
          >
            <v-icon :icon="stage.status === 'done' || stage.status === 'completed' ? 'mdi-check-circle' : stage.status === 'running' ? 'mdi-progress-clock' : stage.status === 'failed' || stage.status === 'retryable_failed' ? 'mdi-alert-circle' : 'mdi-circle-outline'" size="14" />
            <span class="stage-label">{{ stage.title || stage.description || stage.name }}</span>
          </div>
        </div>

        <section class="detail-body node-detail-body">
          <div v-if="selectedNode" class="node-detail">
            <div class="node-agent-strip">
              <div class="node-agent-main">
                <v-icon size="16">mdi-account-cog-outline</v-icon>
                <span>{{ nodeAgentText(selectedNode) }}</span>
              </div>
              <div class="node-time-meta">
                <span>进入 {{ formatDate(selectedNode.entered_at || selectedNode.started_at) }}</span>
                <span>完成 {{ formatDate(selectedNode.completed_at) }}</span>
                <span>耗时 {{ formatDuration(selectedNode.duration_ms) }}</span>
              </div>
              <v-chip :color="stepColor(selectedNode.status)" size="small" variant="tonal">
                {{ stepStatusLabel(selectedNode.status) }}
              </v-chip>
              <v-btn
                v-if="canRetrySelectedNode"
                size="small"
                color="primary"
                variant="tonal"
                prepend-icon="mdi-reload"
                :loading="retryingNode"
                @click="retrySelectedNode"
              >
                重试节点
              </v-btn>
            </div>

            <div v-if="selectedStage?.id === 'stage_execute'" class="execution-detail-grid">
              <div class="execution-tree-panel">
                <div class="section-title">依赖执行树</div>
                <div v-if="executionGraph.length" class="execution-tree">
                  <template v-for="node in executionGraph" :key="node.id">
                    <button
                      class="execution-node"
                      :class="{ active: selectedExecutionNode?.id === node.id }"
                      type="button"
                      @click="selectedExecutionNode = node"
                    >
                      <v-icon :color="stepColor(node.status)" :icon="stepIcon(node.status)" size="16" />
                      <span>{{ stepPreviewText(node.title || node.description) }}</span>
                    </button>
                    <button
                      v-for="child in node.children || []"
                      :key="child.id"
                      class="execution-node child"
                      :class="{ active: selectedExecutionNode?.id === child.id }"
                      type="button"
                      @click="selectedExecutionNode = child"
                    >
                      <span class="tree-branch" />
                      <v-icon :color="stepColor(child.status)" :icon="stepIcon(child.status)" size="16" />
                      <span>{{ stepPreviewText(child.title || child.description) }}</span>
                    </button>
                  </template>
                </div>
                <div v-else class="empty-state compact">暂无依赖树</div>
              </div>
              <div v-if="selectedExecutionNode?.result" class="execution-result-panel">
                <div class="section-title">节点输出</div>
                <pre>{{ selectedExecutionNode.result }}</pre>
              </div>
            </div>

            <WorkProgressTimeline
              :logs="selectedNodeLogs"
              :active-cards="selectedStage?.id === 'stage_execute' ? [] : interactionCards"
              :is-dark="isDark"
              :agent-label="nodeAgentLabel(selectedNode)"
              :loading="detailLoading"
              @interaction-respond="handleInteractionRespond"
            />

            <div v-if="selectedStage?.id === 'stage_deliver'" class="artifact-list node-artifacts">
              <article v-for="artifact in displayArtifacts" :key="artifact.id" class="artifact-item">
                <div class="artifact-title">
                  <v-icon size="18">mdi-file-document-outline</v-icon>
                  <span>{{ artifactTitle(artifact) }}</span>
                </div>
                <pre>{{ artifactText(artifact) }}</pre>
              </article>
            </div>
          </div>
          <div v-else class="empty-state">暂无节点详情</div>
        </section>

        <section class="input-panel">
          <v-textarea
            v-model="supplementText"
            rows="2"
            auto-grow
            hide-details
            variant="outlined"
            placeholder="补充信息、调整要求或人工确认说明..."
            @keydown.ctrl.enter.prevent="submitSupplement"
            @keydown.meta.enter.prevent="submitSupplement"
          />
          <v-btn color="primary" :disabled="!supplementText.trim()" :loading="submittingInput" @click="submitSupplement">
            <v-icon start>mdi-send</v-icon>
            发送
          </v-btn>
        </section>
      </template>

      <div v-else class="detail-empty">
        <v-icon size="54">mdi-clipboard-text-search-outline</v-icon>
        <div>选择一个任务查看执行进展</div>
      </div>
    </main>

    <v-dialog v-model="stepDialog" max-width="760">
      <v-card v-if="selectedStep">
        <v-card-title class="step-dialog-title">
          <v-icon :color="stepColor(selectedStep.status)" :icon="stepIcon(selectedStep.status)" size="20" />
          <span>{{ selectedStep.description || selectedStep.name || '步骤详情' }}</span>
        </v-card-title>
        <v-card-text>
          <div class="step-detail-meta">
            <v-chip size="small" :color="stepColor(selectedStep.status)" variant="tonal">
              {{ stepStatusLabel(selectedStep.status) }}
            </v-chip>
            <span v-if="executorDisplay(selectedStep)">{{ executorDisplay(selectedStep) }}</span>
            <span v-if="selectedStep.reviewer_id">审查者：{{ resourceNameById(agents, selectedStep.reviewer_id) || selectedStep.reviewer_id }}</span>
          </div>
          <pre class="step-detail-text">{{ stepDetailText(selectedStep) }}</pre>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="stepDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <HitlDialog
      v-model="hitlDialog"
      :card="activeHitlCard"
      :is-dark="isDark"
      @respond="handleInteractionRespond"
    />

    <v-dialog v-model="projectDialog" max-width="640">
      <v-card>
        <v-card-title>{{ editingProject ? '编辑项目' : '创建项目' }}</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="projectForm.name" label="项目名称" variant="outlined" />
          <v-text-field v-model="projectForm.directory" label="项目目录" variant="outlined" />
          <v-textarea v-model="projectForm.goal" label="项目目标" variant="outlined" rows="3" />
          <v-textarea v-model="projectForm.rules" label="项目规则" variant="outlined" rows="4" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="projectDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="savingProject" @click="saveProject">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="dailyDialog" max-width="560">
      <v-card>
        <v-card-title>{{ editingDailyDir ? '编辑日常目录' : '创建日常目录' }}</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="dailyForm.name" label="名称" variant="outlined" />
          <v-text-field v-model="dailyForm.directory" label="目录" variant="outlined" />
          <v-textarea v-model="dailyForm.default_rules" label="默认规则" variant="outlined" rows="4" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dailyDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="savingDaily" @click="saveDailyDir">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="taskDialog" max-width="760">
      <v-card>
        <v-card-title>创建 Work 任务</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="taskForm.name" label="任务名称" variant="outlined" />
          <v-textarea v-model="taskForm.description" label="交付目标" variant="outlined" rows="3" />
          <div class="option-row">
            <v-checkbox v-model="taskForm.plan_config.approval_enabled" label="人工审查规划" density="compact" hide-details />
            <v-checkbox v-model="taskForm.clarification_config.interrogation_enabled" label="开启拷问" density="compact" hide-details />
            <v-checkbox v-model="taskForm.review_config.enabled" label="执行后审查" density="compact" hide-details />
            <v-text-field
              v-if="taskForm.review_config.enabled"
              v-model.number="taskForm.review_config.max_rework"
              type="number"
              min="0"
              label="最大返工次数"
              variant="outlined"
              density="compact"
              hide-details
            />
          </div>
          <div class="task-mode-row">
            <span class="task-mode-label">任务模式</span>
            <v-btn-toggle v-model="taskForm.plan_config.task_mode" mandatory color="primary" variant="outlined" density="compact" divided>
              <v-btn value="quick" size="small">
                <v-icon start size="16">mdi-flash-outline</v-icon>
                快速
              </v-btn>
              <v-btn value="normal" size="small">
                <v-icon start size="16">mdi-tune-vertical</v-icon>
                常规
              </v-btn>
              <v-btn value="deep" size="small">
                <v-icon start size="16">mdi-microscope</v-icon>
                深度
              </v-btn>
            </v-btn-toggle>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="taskDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="creatingTask" :disabled="!taskForm.name" @click="createTask">创建</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import WorkTaskList from '@/components/work/WorkTaskList.vue';
import WorkProgressTimeline from '@/components/work/WorkProgressTimeline.vue';
import HitlDialog from '@/components/chat/HitlDialog.vue';
import { usePagedTaskList } from '@/composables/usePagedTaskList';
import { useSelectedEventStream } from '@/composables/useSelectedEventStream';
import { useCustomizerStore } from '@/stores/customizer';

const customizer = useCustomizerStore();
const route = useRoute();
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');

const detailLoading = ref(false);
const projects = ref<any[]>([]);
const dailyDirs = ref<any[]>([]);
const selectedScope = ref<'daily' | 'project'>('daily');
const selectedProjectId = ref<string | null>(null);
const selectedDailyDirId = ref<string | null>(null);
const selectedTaskId = ref<string | null>(null);
const selectedTask = ref<any | null>(null);
const logs = ref<any[]>([]);
const artifacts = ref<any[]>([]);
const interactionCards = ref<any[]>([]);
const hitlDialog = ref(false);
const selectedStep = ref<any | null>(null);
const selectedExecutionNode = ref<any | null>(null);
const detailTab = ref('logs');
const searchQuery = ref('');
const statusFilter = ref<string | null>(null);
const kindFilter = ref<string | null>(null);
const supplementText = ref('');
const submittingInput = ref(false);
const retryingNode = ref(false);
const controllingTask = ref<'pause' | 'resume' | 'terminate' | ''>('');
let summaryRefreshTimer: ReturnType<typeof setInterval> | null = null;
let selectedRefreshTimer: ReturnType<typeof setTimeout> | null = null;
let filterReloadTimer: ReturnType<typeof setTimeout> | null = null;
let selectedTaskRequestId = 0;
let selectedTaskLoading = false;
let pendingSelectedReload = false;
const seenLogIds = new Set<string>();
const taskList = usePagedTaskList<any>({
  pageSize: 30,
  loadPage: loadTaskPage,
});
const tasks = taskList.items;
const loading = taskList.loading;
const loadingMore = taskList.loadingMore;
const hasMore = taskList.hasMore;
const workStream = useSelectedEventStream({
  eventNames: ['phase', 'text_delta', 'tool_call', 'tool_result', 'reasoning', 'token', 'artifact', 'interaction', 'hitl_resolved', 'error', 'done', 'log'],
  streamUrl: (taskId, afterSeq) => `/api/plug/work/tasks/${encodeURIComponent(taskId)}/events?after_seq=${afterSeq}`,
  getAfterSeq: maxLogSeq,
  onEvent: handleWorkStreamEvent,
  onFallback: taskId => loadTaskLogs(taskId, maxLogSeq()),
  shouldReconnect: taskId => selectedTaskId.value === taskId && !isCompleted(selectedTask.value),
});

const agents = ref<any[]>([]);
const crews = ref<any[]>([]);
const flows = ref<any[]>([]);
const BUILTIN_DAILY_FLOW_ID = 'builtin_nicebot_daily_work_flow';

const projectDialog = ref(false);
const editingProject = ref<any | null>(null);
const savingProject = ref(false);
const projectForm = reactive({ name: '', directory: '', goal: '', rules: '' });

const dailyDialog = ref(false);
const editingDailyDir = ref<any | null>(null);
const savingDaily = ref(false);
const dailyForm = reactive({ name: '', directory: '', default_rules: '' });

const taskDialog = ref(false);
const creatingTask = ref(false);
const taskForm = reactive<any>(defaultTaskForm());

const statusOptions = [
  { title: '等待中', value: 'pending' },
  { title: '执行中', value: 'running' },
  { title: '暂停中', value: 'pause_requested' },
  { title: '已暂停', value: 'paused' },
  { title: '等待确认', value: 'waiting_feedback' },
  { title: '已完成', value: 'completed' },
  { title: '失败', value: 'failed' },
  { title: '可重试失败', value: 'retryable_failed' },
  { title: '已取消', value: 'cancelled' },
];
const kindOptions = [
  { title: '单智能体', value: 'single_agent' },
  { title: '多智能体', value: 'multi_agent' },
  { title: '交付任务', value: 'workflow' },
];

const filteredTasks = computed(() => {
  return tasks.value;
});

const steps = computed(() => {
  const raw = selectedTask.value?.steps;
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') {
    try { return JSON.parse(raw); } catch { return []; }
  }
  return [];
});

const selectedExecutorLabel = computed(() => executorLabel(selectedTask.value));
const selectedTaskMode = computed(() => taskMode(selectedTask.value));
const canPauseTask = computed(() => selectedTask.value?.status === 'running');
const isPauseRequested = computed(() => selectedTask.value?.status === 'pause_requested');
const canResumeTask = computed(() => selectedTask.value?.status === 'paused');
const canTerminateTask = computed(() =>
  ['running', 'pause_requested', 'paused'].includes(selectedTask.value?.status || '')
);

const stepDialog = computed({
  get: () => Boolean(selectedStep.value),
  set: (value: boolean) => {
    if (!value) selectedStep.value = null;
  },
});

const displayArtifacts = computed(() => {
  return uniqueArtifacts(artifacts.value.filter((artifact) =>
    artifact && (artifact.file_path || artifact.content || artifact.artifact_type === 'file')
  ));
});

const displayLogs = computed(() => aggregateLogs(logs.value));
const activeHitlCard = computed(() =>
  selectedTask.value?.active_hitl || selectedTask.value?.hitl_cards?.[0] || interactionCards.value?.[0] || null
);
const flattenedSteps = computed(() => flattenSteps(steps.value));
const selectedStageIndex = ref(0);
const timeline = computed(() => selectedTask.value?.timeline || { stages: [], execution_graph: [], unclassified_events: [] });
const stageSteps = computed(() => {
  const stages = Array.isArray(timeline.value?.stages) ? timeline.value.stages : [];
  if (stages.length) return stages;
  return flattenedSteps.value.filter((step: any) => /(?:^|:)stage_/.test(String(step.id || '')));
});
const executionSteps = computed(() =>
  flattenedSteps.value.filter((step: any) => !/(?:^|:)stage_/.test(String(step.id || '')))
);
const executionGraph = computed(() => Array.isArray(timeline.value?.execution_graph) ? timeline.value.execution_graph : []);
const selectedStage = computed(() => stageSteps.value[selectedStageIndex.value] || stageSteps.value[0] || null);
const selectedNode = computed(() => {
  if (selectedStage.value?.id === 'stage_execute' && selectedExecutionNode.value) return selectedExecutionNode.value;
  return selectedStage.value;
});
const selectedNodeLogs = computed(() => {
  const events = normalizeTimelineEvents(selectedNode.value?.events || []);
  if (selectedStage.value?.id !== 'stage_deliver') return events;
  return events.filter((event: any) => !isArtifactTimelineLog(event));
});
const canRetrySelectedNode = computed(() => {
  const status = selectedNode.value?.status || selectedTask.value?.status;
  return ['failed', 'retryable_failed'].includes(status) && Boolean(selectedTaskId.value && selectedNode.value?.id);
});
function defaultTaskForm() {
  return {
    name: '',
    description: '',
    work_task_kind: 'workflow',
    executor_config: { flow_id: BUILTIN_DAILY_FLOW_ID },
    plan_config: { approval_enabled: true, task_mode: 'normal' },
    clarification_config: { interrogation_enabled: false },
    review_config: { enabled: false, max_rework: 3 },
  };
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadProjects(), loadDailyDirs(), loadResources()]);
    syncScopeFromRoute();
    await loadTasks();
    await ensureSelectedTask();
    if (selectedTaskId.value) await loadSelectedTask(true);
  } finally {
    loading.value = false;
  }
}

async function loadProjects() {
  const response = await axios.get('/api/plug/work/projects');
  if (response.data?.status === 'ok') projects.value = response.data.data || [];
}

async function loadDailyDirs() {
  const response = await axios.get('/api/plug/work/daily-dirs');
  if (response.data?.status === 'ok') {
    dailyDirs.value = response.data.data || [];
  }
}

async function loadResources() {
  const [agentRes, crewRes, flowRes] = await Promise.allSettled([
    axios.get('/api/plug/agent/agents'),
    axios.get('/api/plug/agent/crews'),
    axios.get('/api/plug/agent/flows'),
  ]);
  if (agentRes.status === 'fulfilled' && agentRes.value.data?.status === 'ok') agents.value = agentRes.value.data.data || [];
  if (crewRes.status === 'fulfilled' && crewRes.value.data?.status === 'ok') crews.value = crewRes.value.data.data || [];
  if (flowRes.status === 'fulfilled' && flowRes.value.data?.status === 'ok') {
    flows.value = flowRes.value.data.data || [];
    if (!taskForm.executor_config.flow_id && flows.value.find(flow => flow.id === BUILTIN_DAILY_FLOW_ID)) {
      taskForm.executor_config.flow_id = BUILTIN_DAILY_FLOW_ID;
    }
  }
}

async function loadTasks() {
  await taskList.loadFirstPage();
}

async function loadTaskPage(page: number, pageSize: number) {
  const params: any = {
    page,
    page_size: pageSize,
    work_scope: selectedScope.value,
    include_hitl_cards: false,
    q: searchQuery.value.trim() || undefined,
    status: statusFilter.value || undefined,
    work_task_kind: kindFilter.value || undefined,
  };
  if (selectedScope.value === 'project' && selectedProjectId.value) params.project_id = selectedProjectId.value;
  if (selectedScope.value === 'daily' && selectedDailyDirId.value) params.daily_dir_id = selectedDailyDirId.value;
  const response = await axios.get('/api/plug/work/tasks', { params });
  const data = response.data?.data || {};
  return {
    items: data.tasks || [],
    pagination: data.pagination,
  };
}

watch([searchQuery, statusFilter, kindFilter], () => {
  scheduleFilterReload();
});

watch(
  () => [route.query.scope, route.query.daily_dir_id, route.query.project_id],
  () => {
    syncScopeFromRoute();
    scheduleFilterReload();
  }
);

watch(stageSteps, (stages) => {
  if (!stages.length) return;
  if (selectedStageIndex.value >= stages.length) selectedStageIndex.value = 0;
  if (stages[selectedStageIndex.value]?.id === 'stage_execute' && !selectedExecutionNode.value) {
    selectedExecutionNode.value = firstExecutionNode(executionGraph.value);
  }
});

async function reloadTasksForFilters() {
  clearSelection();
  await loadTasks();
  await ensureSelectedTask();
}

function scheduleFilterReload() {
  if (filterReloadTimer) clearTimeout(filterReloadTimer);
  filterReloadTimer = setTimeout(() => {
    filterReloadTimer = null;
    reloadTasksForFilters().catch(() => undefined);
  }, 350);
}

async function ensureSelectedTask() {
  if (selectedTaskId.value && tasks.value.some(task => task.id === selectedTaskId.value)) return;
  const first = tasks.value[0];
  if (first) {
    await selectTask(first.id);
    return;
  }
  clearSelection();
}

function handleTaskListScroll(event: Event) {
  const target = event.target as HTMLElement | null;
  if (!target) return;
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 120) {
    taskList.loadMore().catch(() => undefined);
  }
}

function startSummaryRefresh() {
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  summaryRefreshTimer = setInterval(() => {
    if (!document.hidden) refreshTaskSummaries().catch(() => undefined);
  }, 10000);
}

async function refreshTaskSummaries() {
  const ids = taskList.loadedIds.value;
  if (!ids.length) return;
  const response = await axios.get('/api/plug/work/tasks/summaries', {
    params: { ids: ids.join(',') },
  });
  if (response.data?.status !== 'ok') return;
  const summaries = response.data.data?.tasks || [];
  taskList.mergeSummaries(summaries);
  const selectedSummary = summaries.find((task: any) => task.id === selectedTaskId.value);
  if (selectedSummary && selectedTask.value) {
    selectedTask.value = { ...selectedTask.value, ...selectedSummary };
  }
}

async function loadTaskLogs(taskId: string, afterSeq = 0) {
  if (!taskId) return;
  const response = await axios.get(`/api/plug/work/tasks/${encodeURIComponent(taskId)}/logs`, {
    params: { after_seq: afterSeq || undefined, limit: 500 },
  });
  if (response.data?.status !== 'ok') return;
  for (const log of response.data.data || []) appendTaskLog(log);
}

async function loadSelectedTask(mergeLogs = false) {
  if (!selectedTaskId.value) return;
  const requestId = ++selectedTaskRequestId;
  if (selectedTaskLoading) {
    pendingSelectedReload = true;
    return;
  }
  selectedTaskLoading = true;
  detailLoading.value = true;
  const taskId = selectedTaskId.value;
  try {
    const response = await axios.get(`/api/plug/work/tasks/${taskId}`, {
      params: { logs_limit: 500 },
    });
    if (requestId !== selectedTaskRequestId || taskId !== selectedTaskId.value) return;
    if (response.data?.status === 'ok') {
      selectedTask.value = response.data.data;
      if (!mergeLogs) {
        logs.value = selectedTask.value.logs || [];
        seenLogIds.clear();
        for (const log of logs.value) {
          if (log?.id) seenLogIds.add(log.id);
        }
      }
      artifacts.value = selectedTask.value.artifacts || [];
      interactionCards.value = selectedTask.value.hitl_cards || [];
    }
  } finally {
    selectedTaskLoading = false;
    detailLoading.value = false;
    if (pendingSelectedReload && selectedTaskId.value) {
      pendingSelectedReload = false;
      loadSelectedTask(mergeLogs);
    }
  }
}

function routeString(value: unknown) {
  return typeof value === 'string' ? value : '';
}

function syncScopeFromRoute() {
  const scope = routeString(route.query.scope) === 'project' ? 'project' : 'daily';
  selectedScope.value = scope;
  if (scope === 'project') {
    selectedProjectId.value = routeString(route.query.project_id) || null;
    selectedDailyDirId.value = null;
    return;
  }
  selectedDailyDirId.value = routeString(route.query.daily_dir_id) || null;
  selectedProjectId.value = null;
}

function selectDaily(id: string | null) {
  selectedScope.value = 'daily';
  selectedDailyDirId.value = id;
  selectedProjectId.value = null;
  clearSelection();
  loadTasks().then(ensureSelectedTask).catch(() => undefined);
}

function selectProject(id: string | null) {
  selectedScope.value = 'project';
  selectedProjectId.value = id;
  selectedDailyDirId.value = null;
  clearSelection();
  loadTasks().then(ensureSelectedTask).catch(() => undefined);
}

function clearSelection() {
  selectedTaskRequestId += 1;
  pendingSelectedReload = false;
  selectedTaskId.value = null;
  selectedTask.value = null;
  logs.value = [];
  seenLogIds.clear();
  artifacts.value = [];
  interactionCards.value = [];
  selectedStep.value = null;
  selectedExecutionNode.value = null;
  selectedStageIndex.value = 0;
  closeEventSource();
  if (selectedRefreshTimer) {
    clearTimeout(selectedRefreshTimer);
    selectedRefreshTimer = null;
  }
}

async function selectTask(taskId: string) {
  if (selectedTaskId.value === taskId) {
    await loadSelectedTask(true);
    await loadTaskLogs(taskId, maxLogSeq());
    if (!workStream.connected.value && !isCompleted(selectedTask.value)) openEventSource(taskId);
    return;
  }
  selectedTaskRequestId += 1;
  pendingSelectedReload = false;
  selectedTaskId.value = taskId;
  detailTab.value = 'logs';
  interactionCards.value = [];
  selectedStep.value = null;
  selectedExecutionNode.value = null;
  closeEventSource();
  await loadSelectedTask();
  openEventSource(taskId);
}

async function openTaskHitl(taskId: string) {
  if (selectedTaskId.value !== taskId) {
    await selectTask(taskId);
  } else {
    await loadSelectedTask();
  }
  hitlDialog.value = Boolean(activeHitlCard.value);
}

function openEventSource(taskId: string) {
  if (isCompleted(selectedTask.value)) return;
  workStream.open(taskId);
}

function closeEventSource() {
  workStream.close();
}

function handleWorkStreamEvent(name: string, payload: any) {
  if (name === 'heartbeat') return;
  if (name === 'phase') {
    if (payload?.id) {
      appendTaskLog(payload);
      const data = payload.data || {};
      if (selectedTask.value) {
        selectedTask.value = {
          ...selectedTask.value,
          status: data.status || selectedTask.value.status,
          progress: data.progress ?? selectedTask.value.progress,
        };
        taskList.mergeSummaries([{ id: selectedTask.value.id, status: selectedTask.value.status, progress: selectedTask.value.progress }]);
      }
      if (data.steps || data.phase === 'step_done' || data.phase === 'completed') {
        scheduleSelectedTaskRefresh(data.phase === 'step_done' ? 250 : 500);
      }
      return;
    }
    if (payload?.status && selectedTask.value) {
      selectedTask.value = {
        ...selectedTask.value,
        status: payload.status,
        progress: payload.progress ?? selectedTask.value?.progress,
      };
      taskList.mergeSummaries([{ id: selectedTask.value.id, status: selectedTask.value.status, progress: selectedTask.value.progress }]);
      if (isCompleted(selectedTask.value)) {
        scheduleSelectedTaskRefresh(500);
        workStream.close();
      }
    }
    if (payload?.steps) {
      scheduleSelectedTaskRefresh(500);
    }
    return;
  }
  if (name === 'done') {
    if (selectedTask.value) {
      selectedTask.value = {
        ...selectedTask.value,
        status: payload?.status || selectedTask.value.status || 'completed',
        progress: payload?.status === 'completed' ? 100 : selectedTask.value.progress,
      };
      taskList.mergeSummaries([{ id: selectedTask.value.id, status: selectedTask.value.status, progress: selectedTask.value.progress }]);
    }
    scheduleSelectedTaskRefresh(500);
    workStream.close();
    return;
  }
  if (name === 'artifact') {
    scheduleSelectedTaskRefresh(500);
    return;
  }
  if (name === 'interaction' || name === 'hitl_resolved') {
    scheduleSelectedTaskRefresh(500);
  }
  if (payload?.id) appendTaskLog(payload);
}

function appendTaskLog(log: any) {
  if (!log?.id) return;
  if (seenLogIds.has(log.id)) return;
  seenLogIds.add(log.id);
  logs.value = [...logs.value, log].sort((a, b) => Number(a.seq || 0) - Number(b.seq || 0)).slice(-5000);
  if (logs.value.length >= 5000) {
    seenLogIds.clear();
    for (const item of logs.value) {
      if (item?.id) seenLogIds.add(item.id);
    }
  }
}

function maxLogSeq() {
  return logs.value.reduce((max, log) => Math.max(max, Number(log.seq || 0)), 0);
}

function selectStage(index: number) {
  selectedStageIndex.value = index;
  selectedExecutionNode.value = null;
  if (stageSteps.value[index]?.id === 'stage_execute') {
    selectedExecutionNode.value = firstExecutionNode(executionGraph.value);
  }
}

function selectExecutionStep(step: any) {
  const id = shortTimelineId(step?.id);
  selectedStageIndex.value = Math.max(0, stageSteps.value.findIndex((stage: any) => stage.id === 'stage_execute'));
  selectedExecutionNode.value = findExecutionNodeById(executionGraph.value, id) || step;
}

function scheduleSelectedTaskRefresh(delay = 500) {
  if (selectedRefreshTimer) clearTimeout(selectedRefreshTimer);
  selectedRefreshTimer = setTimeout(() => {
    selectedRefreshTimer = null;
    if (selectedTaskId.value) loadSelectedTask(true).catch(() => undefined);
    refreshTaskSummaries().catch(() => undefined);
  }, delay);
}

function openProjectDialog(project?: any) {
  editingProject.value = project || null;
  Object.assign(projectForm, project || { name: '', directory: '', goal: '', rules: '' });
  projectDialog.value = true;
}

async function saveProject() {
  savingProject.value = true;
  try {
    if (editingProject.value) {
      await axios.patch(`/api/plug/work/projects/${editingProject.value.id}`, projectForm);
    } else {
      await axios.post('/api/plug/work/projects', projectForm);
    }
    projectDialog.value = false;
    await loadProjects();
  } finally {
    savingProject.value = false;
  }
}

function openDailyDialog(dir?: any) {
  editingDailyDir.value = dir || null;
  Object.assign(dailyForm, dir || { name: '', directory: '', default_rules: '' });
  dailyDialog.value = true;
}

async function saveDailyDir() {
  savingDaily.value = true;
  try {
    if (editingDailyDir.value) {
      await axios.patch(`/api/plug/work/daily-dirs/${editingDailyDir.value.id}`, dailyForm);
    } else {
      await axios.post('/api/plug/work/daily-dirs', dailyForm);
    }
    dailyDialog.value = false;
    await loadDailyDirs();
  } finally {
    savingDaily.value = false;
  }
}

function openTaskDialog() {
  Object.assign(taskForm, defaultTaskForm());
  taskDialog.value = true;
}

async function createTask() {
  creatingTask.value = true;
  try {
    const payload = { ...JSON.parse(JSON.stringify(taskForm)), ...resolveTaskScopeForCreate() };
    payload.executor_config = { ...(payload.executor_config || {}), flow_id: BUILTIN_DAILY_FLOW_ID };
    payload.flow_id = BUILTIN_DAILY_FLOW_ID;
    payload.work_task_kind = 'workflow';
    const response = await axios.post('/api/plug/work/tasks', payload);
    taskDialog.value = false;
    if (response.data?.data?.id) {
      taskList.replaceItem(response.data.data);
      await selectTask(response.data.data.id);
    } else {
      await loadTasks();
      await ensureSelectedTask();
    }
  } finally {
    creatingTask.value = false;
  }
}

async function submitSupplement() {
  if (!selectedTaskId.value || !supplementText.value.trim()) return;
  submittingInput.value = true;
  try {
    await axios.post(`/api/plug/work/tasks/${selectedTaskId.value}/input`, { text: supplementText.value.trim() });
    supplementText.value = '';
    await loadSelectedTask(true);
  } finally {
    submittingInput.value = false;
  }
}

async function retrySelectedNode() {
  if (!selectedTaskId.value || !selectedNode.value?.id || retryingNode.value) return;
  retryingNode.value = true;
  try {
    const nodeId = encodeURIComponent(String(selectedNode.value.id));
    await axios.post(`/api/plug/work/tasks/${selectedTaskId.value}/nodes/${nodeId}/retry`);
    await Promise.all([loadSelectedTask(true), refreshTaskSummaries()]);
    openEventSource(selectedTaskId.value);
  } finally {
    retryingNode.value = false;
  }
}

function resolveTaskScopeForCreate() {
  if (selectedScope.value === 'project' && selectedProjectId.value) {
    return {
      work_scope: 'project',
      work_project_id: selectedProjectId.value,
      work_daily_dir_id: null,
    };
  }
  return {
    work_scope: 'daily',
    work_project_id: null,
    work_daily_dir_id: selectedDailyDirId.value || dailyDirs.value[0]?.id || null,
  };
}

async function controlTask(action: 'pause' | 'resume' | 'terminate') {
  if (!selectedTaskId.value || controllingTask.value) return;
  controllingTask.value = action;
  try {
    const response = await axios.post(`/api/plug/work/tasks/${selectedTaskId.value}/${action}`);
    const task = response.data?.data;
    if (task?.id) {
      selectedTask.value = task;
      taskList.mergeSummaries([task]);
    }
    await Promise.all([refreshTaskSummaries(), loadSelectedTask(true)]);
    if (action === 'terminate') {
      closeEventSource();
    } else if (action === 'resume' && selectedTaskId.value) {
      openEventSource(selectedTaskId.value);
    }
  } finally {
    controllingTask.value = '';
  }
}

async function handleInteractionRespond() {
  hitlDialog.value = false;
  if (selectedTask.value) {
    selectedTask.value = { ...selectedTask.value, active_hitl: null, has_hitl: false, hitl_cards: [], status: 'running' };
    taskList.mergeSummaries([{ id: selectedTask.value.id, active_hitl: null, has_hitl: false, hitl_cards: [], status: 'running' }]);
  }
  await Promise.all([refreshTaskSummaries(), loadSelectedTask(true)]);
}

function isCompleted(task: any) {
  return ['completed', 'failed', 'retryable_failed', 'cancelled'].includes(task?.status);
}

function taskMode(task: any) {
  const mode = task?.task_mode || task?.plan_config?.task_mode || 'normal';
  return ['quick', 'normal', 'deep'].includes(mode) ? mode : 'normal';
}

function taskModeLabel(mode: string) {
  const map: Record<string, string> = {
    quick: '快速',
    normal: '常规',
    deep: '深度',
  };
  return map[mode] || '常规';
}

function taskModeIcon(mode: string) {
  const map: Record<string, string> = {
    quick: 'mdi-lightning-bolt',
    normal: 'mdi-tune-variant',
    deep: 'mdi-microscope',
  };
  return map[mode] || 'mdi-tune-variant';
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    pause_requested: '暂停中',
    paused: '已暂停',
    waiting_feedback: '等待确认',
    completed: '已完成',
    failed: '失败',
    retryable_failed: '可重试失败',
    cancelled: '已取消',
  };
  return map[status] || status || '-';
}

function stepStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    done: '已完成',
    completed: '已完成',
    failed: '失败',
    retryable_failed: '可重试失败',
  };
  return map[status] || status || '-';
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'grey',
    running: 'primary',
    pause_requested: 'warning',
    paused: 'warning',
    waiting_feedback: 'warning',
    completed: 'success',
    failed: 'error',
    retryable_failed: 'warning',
    cancelled: 'grey',
  };
  return map[status] || 'grey';
}

function statusIcon(status: string) {
  const map: Record<string, string> = {
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    pause_requested: 'mdi-pause-circle-outline',
    paused: 'mdi-pause-circle-outline',
    waiting_feedback: 'mdi-account-question-outline',
    completed: 'mdi-check-circle-outline',
    failed: 'mdi-alert-circle-outline',
    retryable_failed: 'mdi-alert-circle-outline',
    cancelled: 'mdi-cancel',
  };
  return map[status] || 'mdi-circle-outline';
}

function taskKindLabel(kind: string) {
  const map: Record<string, string> = {
    single_agent: '单智能体',
    multi_agent: '多智能体',
    workflow: '交付任务',
    work_task: 'Work 任务',
  };
  return map[kind] || kind || '任务';
}

function executorLabel(task: any) {
  if (!task) return '';
  const taskSteps = parseSteps(task?.steps);
  const activeStepAgent = taskSteps.find((step: any) => step?.status === 'running' && step?.agent)?.agent;
  if (activeStepAgent) return `执行者：${activeStepAgent}`;

  const config = task?.executor_config || {};
  const kind = task?.work_task_kind || task?.task_type;
  if (kind === 'multi_agent') {
    const name = resourceNameById(crews.value, config.crew_id || task?.crew_id);
    return name ? `执行团队：${name}` : '执行团队：任务助手自动选择';
  }
  if (kind === 'workflow') {
    return '内置交付流程';
  }
  const name = resourceNameById(agents.value, config.agent_id || task?.agent_id);
  return name ? `执行智能体：${name}` : '执行智能体：任务助手自动选择';
}

function resourceNameById(items: any[], id: string) {
  const key = String(id || '').trim();
  if (!key) return '';
  return items.find((item) => item?.id === key)?.name || '';
}

function parseSteps(raw: unknown) {
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

function stepIcon(status: string) {
  if (status === 'done' || status === 'completed') return 'mdi-check-circle-outline';
  if (status === 'running') return 'mdi-progress-clock';
  if (status === 'failed' || status === 'retryable_failed') return 'mdi-alert-circle-outline';
  return 'mdi-circle-outline';
}

function stepColor(status: string) {
  if (status === 'done' || status === 'completed') return 'success';
  if (status === 'running') return 'primary';
  if (status === 'failed') return 'error';
  if (status === 'retryable_failed') return 'warning';
  return 'grey';
}

function formatTokens(value: number) {
  const n = Number(value || 0);
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function formatDate(value: string) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function formatDuration(ms: number) {
  const value = Number(ms || 0);
  if (!value) return '-';
  if (value < 1000) return `${value}ms`;
  const seconds = Math.floor(value / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return rest ? `${minutes}m${rest}s` : `${minutes}m`;
}

function nodeAgentText(node: any) {
  const label = nodeAgentLabel(node);
  return label ? `执行者：${label}` : '执行者：系统';
}

function nodeAgentLabel(node: any) {
  const agent = node?.agent || {};
  if (agent.label && !looksLikeAgentId(agent.label)) return agent.label;
  if (agent.id) return resourceNameById(agents.value, agent.id) || agent.id;
  if (agent.label) return resourceNameById(agents.value, agent.label) || agent.label;
  const text = executorDisplay(node) || '';
  return text.replace(/^执行者[:：]\s*/, '');
}

function looksLikeAgentId(value: unknown) {
  const text = String(value || '');
  return text.startsWith('agent_') || text.startsWith('expert_');
}

function normalizeTimelineEvents(events: any[]) {
  return (events || []).map((event, index) => {
    if (event?.raw?.data?.event) return event.raw;
    const raw = event?.raw || {};
    const data = {
      ...(raw.data || {}),
      ...(event.raw && !event.raw.data ? {} : {}),
      event: event.event || event.kind || raw.event || 'log',
      text: event.content || raw.content || raw.message || '',
      title: event.title || raw.title || '',
      result: event.kind === 'tool_result' ? event.content : raw.result,
      input_tokens: event.token_usage?.input_tokens,
      output_tokens: event.token_usage?.output_tokens,
      total_tokens: event.token_usage?.total_tokens,
    };
    if (event.kind === 'hitl_call') data.event = 'interaction';
    if (event.kind === 'hitl_result') data.event = 'hitl_resolved';
    if (event.kind === 'artifact') data.event = 'artifact';
    return {
      id: event.id || `timeline-${index}`,
      seq: event.seq || index,
      level: data.event === 'error' ? 'error' : 'info',
      message: event.title || event.content || '',
      data,
      created_at: event.created_at,
    };
  });
}

function isArtifactTimelineLog(log: any) {
  const data = log?.data || {};
  return data.event === 'artifact' || log?.kind === 'artifact';
}

function uniqueArtifacts(items: any[]) {
  const seen = new Set<string>();
  const result: any[] = [];
  for (const artifact of items || []) {
    const key = artifactDedupeKey(artifact);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(artifact);
  }
  return result;
}

function artifactDedupeKey(artifact: any) {
  const title = artifactTitle(artifact);
  const stableId = artifact.artifact_id || artifact.metadata?.artifact_id || artifact.file_path || '';
  const content = artifactText(artifact);
  return `${title}::${stableId || content}`;
}

function shortTimelineId(value: string) {
  const raw = String(value || '');
  const prefix = `${selectedTaskId.value}:`;
  return raw.startsWith(prefix) ? raw.slice(prefix.length) : raw;
}

function firstExecutionNode(nodes: any[]): any | null {
  for (const node of nodes || []) {
    if (node) return node;
  }
  return null;
}

function findExecutionNodeById(nodes: any[], id: string): any | null {
  for (const node of nodes || []) {
    if (shortTimelineId(node?.id) === id) return node;
    const child = findExecutionNodeById(node?.children || [], id);
    if (child) return child;
  }
  return null;
}

function aggregateLogs(rawLogs: any[]) {
  const result: Array<{ id: string; created_at: string; label: string; message: string; kind: string }> = [];
  let buffer: { id: string; created_at: string; label: string; message: string; kind: string } | null = null;
  const flush = () => {
    if (buffer) {
      result.push(buffer);
      buffer = null;
    }
  };

  for (const log of rawLogs) {
    const data = log?.data || {};
    const event = data.event || 'log';
    if (event === 'text_delta') {
      const text = String(data.text || log.message || '');
      if (!buffer) {
        buffer = {
          id: `${log.id}-group`,
          created_at: log.created_at,
          label: '输出',
          message: text,
          kind: 'text',
        };
      } else {
        buffer.message = joinDeltaText(buffer.message, text);
        buffer.created_at = log.created_at || buffer.created_at;
      }
      continue;
    }
    flush();
    result.push({
      id: log.id,
      created_at: log.created_at,
      label: eventLabel(event, log.level),
      message: logMessage(log),
      kind: event,
    });
  }
  flush();
  return result;
}

function logMessage(log: any) {
  const data = log?.data || {};
  const event = data.event || 'log';
  if (event === 'tool_call') return data.name ? `调用工具：${data.name}` : JSON.stringify(data, null, 2);
  if (event === 'tool_result') return data.result || data.output || data.message || '工具调用完成';
  if (event === 'token') return tokenText(data);
  if (event === 'phase') return data.message || data.label || data.phase || log.message || '';
  if (event === 'interaction') return data.title || data.body || '等待人工处理';
  if (event === 'hitl_resolved') {
    const actionLabels: Record<string, string> = { approve: '批准执行', modify: '调整计划', reject: '拒绝', retry: '继续返工', finish: '接受当前结果', cancel: '取消任务' };
    const label = actionLabels[data.action_key] || data.action_key || '';
    const fields = data.field_values || {};
    const feedback = fields.modify_text || fields.guidance || fields.feedback || '';
    return feedback ? `已处理：${label} — ${feedback}` : `已处理：${label}`;
  }
  return data.message || log.message || '';
}

function eventLabel(event: string, level: string) {
  const map: Record<string, string> = {
    phase: '阶段',
    tool_call: '工具',
    tool_result: '工具结果',
    token: 'Token',
    artifact: '交付物',
    interaction: 'HITL',
    hitl_resolved: 'HITL',
    error: '错误',
    log: level || '日志',
  };
  return map[event] || level || event;
}

function tokenText(data: any) {
  const stats = data.stats || {};
  const usage = stats.token_usage || {};
  const input = data.input_tokens ?? data.input ?? usage.input_other ?? usage.input ?? 0;
  const output = data.output_tokens ?? data.output ?? usage.output ?? 0;
  const total = data.total_tokens ?? data.total ?? Number(input || 0) + Number(output || 0);
  return `输入 ${formatTokens(input)} · 输出 ${formatTokens(output)} · 总计 ${formatTokens(total)}`;
}

function joinDeltaText(current: string, next: string) {
  if (!current) return next;
  if (!next) return current;
  if (/^[，。！？；：、,.!?;:)\]}]/.test(next)) return `${current}${next}`;
  if (/[\s([{（【]$/.test(current) || /^[\s]/.test(next)) return `${current}${next}`;
  if (/^[A-Za-z0-9_]/.test(next) && /[A-Za-z0-9_]$/.test(current)) return `${current} ${next}`;
  return `${current}${next}`;
}

function artifactTitle(artifact: any) {
  return artifact.title || artifact.metadata?.title || '任务交付物';
}

function artifactText(artifact: any) {
  const metadata = artifact.metadata || {};
  const value =
    artifact.content ||
    metadata.content ||
    metadata.body ||
    metadata.result ||
    metadata.summary ||
    selectedTask.value?.result ||
    selectedTask.value?.output?.result ||
    selectedTask.value?.final_summary ||
    artifact.file_path ||
    '暂无内容';
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function stepDetailText(step: any) {
  const parts = [];
  if (step.description || step.name || step.title) parts.push(step.description || step.name || step.title);
  if (step.dependencies?.length) parts.push(`依赖：${dependencyLabels(step.dependencies)}`);
  if (executorDisplay(step)) parts.push(`执行者：${executorDisplay(step)}`);
  if (step.reviewer_id) parts.push(`审查者：${resourceNameById(agents.value, step.reviewer_id) || step.reviewer_id}`);
  if (step.result_ref) parts.push(`结果引用：${step.result_ref}`);
  if (step.result) parts.push(`结果：\n${step.result}`);
  if (step.error) parts.push(`错误：\n${step.error}`);
  if (step.stats) parts.push(`统计：\n${JSON.stringify(step.stats, null, 2)}`);
  return parts.join('\n\n') || '暂无详情';
}

function flattenSteps(rawSteps: any[]) {
  const tree = Array.isArray(selectedTask.value?.steps_tree) && selectedTask.value.steps_tree.length
    ? selectedTask.value.steps_tree
    : rawSteps;
  const result: any[] = [];
  const visit = (step: any, depth = 1) => {
    result.push({ ...step, depth: Math.min(2, step.depth || depth) });
    for (const child of (step.children || []).slice(0, 20)) {
      visit(child, 2);
    }
  };
  for (const step of tree || []) visit(step, 1);
  return result;
}

function dependencyLabels(ids: string[]) {
  const map = new Map(flattenedSteps.value.map((step: any) => [String(step.id), step.title || step.description || step.name || step.id]));
  return ids.map((id) => stepPreviewText(map.get(String(id)) || id)).join(' → ');
}

function hasUnfinishedDependencies(step: any) {
  const ids = step?.dependencies || [];
  if (!ids.length) return false;
  const byId = new Map(flattenedSteps.value.map((item: any) => [String(item.id), item]));
  return ids.some((id: string) => {
    const dep = byId.get(String(id));
    return dep && !['done', 'completed'].includes(dep.status);
  });
}

function executorDisplay(step: any) {
  const id = step?.executor_id || step?.agent || '';
  if (step?.executor) return `执行者：${step.executor}`;
  if (!id) return '';
  if (step.executor_type === 'crew') return `执行团队：${resourceNameById(crews.value, id) || id}`;
  return `执行者：${resourceNameById(agents.value, id) || id}`;
}

function stepPreviewText(value: unknown) {
  return cleanPreviewText(value, 180);
}

function cleanPreviewText(value: unknown, maxLength = 180) {
  if (value == null) return '';
  let text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  text = text
    .replace(/\r\n/g, '\n')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/^#+\s*/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

onMounted(() => {
  refreshAll().then(startSummaryRefresh).catch(() => undefined);
});

onBeforeUnmount(() => {
  if (summaryRefreshTimer) clearInterval(summaryRefreshTimer);
  if (selectedRefreshTimer) clearTimeout(selectedRefreshTimer);
  if (filterReloadTimer) clearTimeout(filterReloadTimer);
  closeEventSource();
});
</script>

<style scoped>
.work-shell {
  --work-bg: #f7f8fa;
  --work-panel: #ffffff;
  --work-panel-soft: #f1f4f8;
  --work-border: rgba(var(--v-border-color), 0.18);
  --work-muted: rgba(var(--v-theme-on-surface), 0.62);
  display: grid;
  grid-template-columns: 320px minmax(360px, 1fr);
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--work-bg);
  color: rgb(var(--v-theme-on-surface));
}

.work-shell.is-dark {
  --work-bg: #17191d;
  --work-panel: #202329;
  --work-panel-soft: #262b33;
  --work-border: rgba(255, 255, 255, 0.1);
}

.work-task-pane {
  min-height: 0;
  border-right: 1px solid var(--work-border);
  background: var(--work-panel);
}

.pane-header,
.detail-header,
.task-card-top,
.artifact-title,
.filter-row,
.dialog-row,
.option-row,
.toolbar-actions,
.input-panel {
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
.task-desc,
.task-meta,
.step-result {
  color: var(--work-muted);
}

.task-card:hover,
.task-card.active {
  background: rgba(var(--v-theme-primary), 0.1);
}

.work-task-pane {
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

.filter-row,
.dialog-row,
.option-row {
  gap: 10px;
}

.task-mode-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-mode-label {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  color: var(--work-muted);
}

.filter-row > *,
.dialog-row > * {
  flex: 1;
  min-width: 0;
}

.task-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}

.task-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-card-top {
  gap: 8px;
}

.task-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.task-desc {
  min-height: 38px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  font-size: 13px;
}

.task-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.work-detail-pane {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--work-bg);
}

.detail-header {
  min-height: 62px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--work-border);
  background: var(--work-panel);
}

.detail-main {
  min-width: 0;
}

.detail-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
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
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.detail-tabs {
  background: var(--work-panel);
  border-bottom: 1px solid var(--work-border);
}

.detail-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 28px;
}

.node-detail-body {
  padding-top: 16px;
}

.node-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-title {
  color: var(--work-muted);
  font-size: 12px;
  font-weight: 700;
}

.node-agent-strip,
.execution-tree-panel,
.execution-result-panel {
  padding: 12px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel);
}

.node-agent-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--work-muted);
  font-size: 13px;
}

.node-agent-main,
.node-time-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.node-agent-main {
  color: rgba(var(--v-theme-on-surface), 0.78);
  font-weight: 600;
}

.node-time-meta {
  margin-left: auto;
  color: var(--work-muted);
}

.node-time-meta span:not(:last-child)::after {
  content: "·";
  margin-left: 8px;
  color: rgba(var(--v-theme-on-surface), 0.32);
}

.execution-detail-grid {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(260px, 1fr);
  gap: 12px;
}

.execution-tree {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.execution-node {
  position: relative;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 8px;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.execution-node.child {
  margin-left: 18px;
  width: calc(100% - 18px);
  border-style: dashed;
}

.execution-node.active,
.stage-chip.active {
  border-color: rgba(var(--v-theme-primary), 0.6);
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-primary), 0.6);
}

.execution-node span:last-child {
  min-width: 0;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.45;
}

.execution-result-panel pre {
  max-height: 260px;
  overflow: auto;
  margin: 10px 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
  line-height: 1.6;
}

.node-artifacts {
  margin-top: 0;
}

.input-panel {
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--work-border);
  background: var(--work-panel);
}

.input-panel .v-textarea {
  flex: 1;
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

.step-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.stage-progress-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  padding: 6px 0;
  overflow-x: auto;
}

.detail-stage-strip {
  display: flex;
  gap: 8px;
  padding: 10px 22px 8px;
  border-top: 1px solid var(--work-border);
  border-bottom: 1px solid var(--work-border);
  background: var(--work-panel);
  overflow-x: auto;
  flex-shrink: 0;
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
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid var(--work-border);
  background: var(--work-panel-soft);
  color: var(--work-muted);
}

.stage-chip.stage-done {
  background: rgba(var(--v-theme-success), 0.12);
  border-color: rgba(var(--v-theme-success), 0.35);
  color: rgb(var(--v-theme-success));
}

.stage-chip.stage-running {
  background: rgba(var(--v-theme-primary), 0.12);
  border-color: rgba(var(--v-theme-primary), 0.45);
  color: rgb(var(--v-theme-primary));
  box-shadow: 0 0 0 2px rgba(var(--v-theme-primary), 0.12);
}

.stage-chip.stage-pending {
  opacity: 0.65;
}

.stage-chip.stage-failed {
  background: rgba(var(--v-theme-error), 0.1);
  border-color: rgba(var(--v-theme-error), 0.35);
  color: rgb(var(--v-theme-error));
}

.stage-label {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-list-enter-active {
  transition: all 0.3s ease;
}

.step-list-leave-active {
  transition: all 0.2s ease;
}

.step-list-enter-from {
  opacity: 0;
  transform: translateX(-12px);
}

.step-list-leave-to {
  opacity: 0;
  transform: translateX(8px);
}

.step-list-move {
  transition: transform 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.step-row {
  position: relative;
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 8px;
  width: 100%;
  padding: 10px;
  color: inherit;
  text-align: left;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
  cursor: pointer;
  transition: all 0.3s ease;
}

.step-row.child {
  margin-left: 18px;
  width: calc(100% - 18px);
  border-style: dashed;
  padding-left: 18px;
}

.step-row.running {
  border-color: rgba(var(--v-theme-primary), 0.55);
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-primary), 0.55);
}

.step-row.blocked {
  opacity: 0.72;
}

.tree-branch {
  position: absolute;
  left: -12px;
  top: -12px;
  width: 20px;
  height: 34px;
  border-left: 1px solid rgba(var(--v-theme-primary), 0.35);
  border-bottom: 1px solid rgba(var(--v-theme-primary), 0.35);
  border-bottom-left-radius: 8px;
}

.step-row:hover {
  border-color: rgba(var(--v-theme-primary), 0.45);
  background: rgba(var(--v-theme-primary), 0.08);
}

.step-title {
  font-size: 13px;
  font-weight: 650;
  line-height: 1.45;
}

.step-result {
  max-height: 72px;
  overflow: hidden;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.45;
}

.step-deps {
  margin-top: 3px;
  color: var(--work-muted);
  font-size: 11px;
  line-height: 1.35;
}

.token-box {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
}

.token-box strong,
.token-box span {
  display: block;
}

.token-box strong {
  margin-top: 5px;
  font-size: 22px;
}

.token-box span {
  color: var(--work-muted);
  font-size: 12px;
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

.step-dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-dialog-title span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-detail-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--work-muted);
  font-size: 13px;
}

.step-detail-text {
  max-height: 58vh;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: normal;
  font: inherit;
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .work-shell {
    grid-template-columns: 280px minmax(300px, 1fr);
  }
}

@media (max-width: 820px) {
  .work-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .work-task-pane {
    max-height: 210px;
    border-right: 0;
    border-bottom: 1px solid var(--work-border);
  }

  .detail-body {
    padding: 14px;
  }

  .input-panel,
  .dialog-row,
  .option-row,
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .raw-log-row {
    grid-template-columns: 1fr;
  }

  .execution-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
