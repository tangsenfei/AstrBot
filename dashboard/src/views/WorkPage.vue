<template>
  <div class="work-shell" :class="{ 'is-dark': isDark }">
    <aside class="work-category-pane">
      <div class="pane-header">
        <div>
          <div class="pane-title">Work</div>
          <div class="pane-subtitle">任务工作台</div>
        </div>
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="loading" @click="refreshAll" />
      </div>

      <button
        class="category-row"
        :class="{ active: selectedScope === 'daily' && !selectedDailyDirId }"
        type="button"
        @click="selectDaily(null)"
      >
        <v-icon size="18">mdi-calendar-check-outline</v-icon>
        <span>日常任务</span>
      </button>
      <div class="category-children">
        <button
          v-for="dir in dailyDirs"
          :key="dir.id"
          class="category-row child"
          :class="{ active: selectedScope === 'daily' && selectedDailyDirId === dir.id }"
          type="button"
          @click="selectDaily(dir.id)"
        >
          <v-icon size="16">mdi-folder-clock-outline</v-icon>
          <span>{{ dir.name }}</span>
        </button>
        <v-btn block size="small" variant="tonal" prepend-icon="mdi-plus" @click="openDailyDialog()">
          日常目录
        </v-btn>
      </div>

      <button
        class="category-row"
        :class="{ active: selectedScope === 'project' && !selectedProjectId }"
        type="button"
        @click="selectProject(null)"
      >
        <v-icon size="18">mdi-briefcase-outline</v-icon>
        <span>项目</span>
      </button>
      <div class="category-children">
        <button
          v-for="project in projects"
          :key="project.id"
          class="category-row child"
          :class="{ active: selectedScope === 'project' && selectedProjectId === project.id }"
          type="button"
          @click="selectProject(project.id)"
        >
          <v-icon size="16">mdi-folder-star-outline</v-icon>
          <span>{{ project.name }}</span>
        </button>
        <v-btn block size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openProjectDialog()">
          创建项目
        </v-btn>
      </div>
    </aside>

    <aside class="work-task-pane">
      <div class="task-toolbar">
        <v-btn color="primary" variant="flat" prepend-icon="mdi-plus" @click="openTaskDialog">
          新建任务
        </v-btn>
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
        :is-dark="isDark"
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
            <v-chip :color="statusColor(selectedTask.status)" size="small" variant="tonal">
              {{ statusLabel(selectedTask.status) }}
            </v-chip>
            <v-btn icon="mdi-refresh" size="small" variant="text" @click="loadSelectedTask" />
          </div>
        </header>

        <v-tabs v-model="detailTab" density="compact" class="detail-tabs">
          <v-tab value="logs">
            <v-icon start size="16">mdi-text-box-search-outline</v-icon>
            日志
          </v-tab>
          <v-tab value="artifacts" :disabled="!isCompleted(selectedTask)">
            <v-icon start size="16">mdi-package-variant-closed</v-icon>
            交付物
          </v-tab>
        </v-tabs>

        <section class="detail-body">
          <div v-if="detailTab === 'artifacts'" class="artifact-list">
            <article v-for="artifact in displayArtifacts" :key="artifact.id" class="artifact-item">
              <div class="artifact-title">
                <v-icon size="18">mdi-file-document-outline</v-icon>
                <span>{{ artifactTitle(artifact) }}</span>
              </div>
              <pre>{{ artifactText(artifact) }}</pre>
            </article>
            <div v-if="!displayArtifacts.length" class="empty-state">任务完成后会在这里显示交付结果</div>
          </div>

          <div v-else class="raw-log-list">
            <div v-for="log in displayLogs" :key="log.id" class="raw-log-row" :class="{ wide: log.kind === 'text' }">
              <span>{{ formatDate(log.created_at) }}</span>
              <strong>{{ log.label }}</strong>
              <p>{{ log.message }}</p>
            </div>
          </div>
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

    <aside class="work-progress-pane">
      <div class="progress-pane-header">
        <div class="pane-title small">任务进度</div>
      </div>
      <div v-if="selectedTask" class="step-list-wrap">
        <div v-if="stageSteps.length" class="stage-progress-bar">
          <div
            v-for="(stage, idx) in stageSteps"
            :key="stage.id"
            class="stage-chip"
            :class="{
              'stage-done': stage.status === 'done' || stage.status === 'completed',
              'stage-running': stage.status === 'running',
              'stage-pending': stage.status === 'pending',
              'stage-failed': stage.status === 'failed',
            }"
            @click="selectedStageIndex = idx"
          >
            <v-icon :icon="stage.status === 'done' || stage.status === 'completed' ? 'mdi-check-circle' : stage.status === 'running' ? 'mdi-progress-clock' : stage.status === 'failed' ? 'mdi-alert-circle' : 'mdi-circle-outline'" size="14" />
            <span class="stage-label">{{ stage.title || stage.description || stage.name }}</span>
          </div>
        </div>
        <div class="step-list">
          <transition-group name="step-list" tag="div">
            <button
              v-for="step in executionSteps"
              :key="step.id || step.description"
              class="step-row"
              :class="{ child: step.depth === 2, blocked: hasUnfinishedDependencies(step), running: step.status === 'running' }"
              type="button"
              @click="selectedStep = step"
            >
              <span v-if="step.depth === 2" class="tree-branch" />
              <v-icon :color="stepColor(step.status)" :icon="stepIcon(step.status)" size="18" />
              <div>
                <div class="step-title">{{ stepPreviewText(step.title || step.description || step.name) }}</div>
                <div v-if="step.dependencies?.length" class="step-deps">
                  <v-icon size="13" icon="mdi-arrow-right-thin" />
                  前置：{{ dependencyLabels(step.dependencies) }}
                </div>
                <div v-if="executorDisplay(step)" class="step-deps">
                  <v-icon size="13" icon="mdi-account-cog-outline" />
                  {{ executorDisplay(step) }}
                </div>
                <div v-if="step.result" class="step-result">{{ stepPreviewText(step.result) }}</div>
              </div>
            </button>
          </transition-group>
          <div v-if="!executionSteps.length" class="empty-state compact">暂无执行步骤</div>
        </div>
      </div>
      <div v-else class="empty-state compact progress-empty">选择任务后查看步骤</div>
    </aside>

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
          <div class="dialog-row">
            <v-select v-model="taskForm.executor_config.flow_id" :items="flows" item-title="name" item-value="id" label="任务流程" variant="outlined" />
            <v-select v-model="taskForm.work_scope" :items="scopeOptions" label="归属" variant="outlined" />
          </div>
          <v-select
            v-if="taskForm.work_scope === 'project'"
            v-model="taskForm.work_project_id"
            :items="projects"
            item-title="name"
            item-value="id"
            label="项目"
            variant="outlined"
          />
          <v-select
            v-else
            v-model="taskForm.work_daily_dir_id"
            :items="dailyDirs"
            item-title="name"
            item-value="id"
            label="日常目录"
            variant="outlined"
          />
          <div class="option-row">
            <v-checkbox v-model="taskForm.plan_config.enabled" label="人工审查规划" density="compact" hide-details />
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import axios from 'axios';
import WorkTaskList from '@/components/work/WorkTaskList.vue';
import HitlDialog from '@/components/chat/HitlDialog.vue';
import { useCustomizerStore } from '@/stores/customizer';

const customizer = useCustomizerStore();
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');

const loading = ref(false);
const detailLoading = ref(false);
const projects = ref<any[]>([]);
const dailyDirs = ref<any[]>([]);
const tasks = ref<any[]>([]);
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
const detailTab = ref('logs');
const searchQuery = ref('');
const statusFilter = ref<string | null>(null);
const kindFilter = ref<string | null>(null);
const supplementText = ref('');
const submittingInput = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;
let eventSource: EventSource | null = null;
let sseDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let selectedTaskRequestId = 0;
let taskListRequestId = 0;
let selectedTaskLoading = false;
let pendingSelectedReload = false;

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
  { title: '等待确认', value: 'waiting_feedback' },
  { title: '已完成', value: 'completed' },
  { title: '失败', value: 'failed' },
  { title: '已取消', value: 'cancelled' },
];
const kindOptions = [
  { title: '单智能体', value: 'single_agent' },
  { title: '多智能体', value: 'multi_agent' },
  { title: '业务流', value: 'workflow' },
];
const scopeOptions = [
  { title: '日常任务', value: 'daily' },
  { title: '项目', value: 'project' },
];

const filteredTasks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  return tasks.value.filter((task) => {
    if (statusFilter.value && task.status !== statusFilter.value) return false;
    if (kindFilter.value && task.work_task_kind !== kindFilter.value) return false;
    if (q && !`${task.name} ${task.description || ''}`.toLowerCase().includes(q)) return false;
    return true;
  });
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

const stepDialog = computed({
  get: () => Boolean(selectedStep.value),
  set: (value: boolean) => {
    if (!value) selectedStep.value = null;
  },
});

const displayArtifacts = computed(() => {
  return artifacts.value.filter((artifact) =>
    artifact && (artifact.file_path || artifact.content || artifact.artifact_type === 'file')
  );
});

const displayLogs = computed(() => aggregateLogs(logs.value));
const activeHitlCard = computed(() =>
  selectedTask.value?.active_hitl || selectedTask.value?.hitl_cards?.[0] || interactionCards.value?.[0] || null
);
const flattenedSteps = computed(() => flattenSteps(steps.value));
const selectedStageIndex = ref(0);
const stageSteps = computed(() =>
  flattenedSteps.value.filter((step: any) => /(?:^|:)stage_/.test(String(step.id || '')))
);
const executionSteps = computed(() =>
  flattenedSteps.value.filter((step: any) => !/(?:^|:)stage_/.test(String(step.id || '')))
);

function defaultTaskForm() {
  return {
    name: '',
    description: '',
    work_task_kind: 'workflow',
    work_scope: selectedScope.value,
    work_project_id: selectedProjectId.value,
    work_daily_dir_id: selectedDailyDirId.value,
    executor_config: { flow_id: BUILTIN_DAILY_FLOW_ID },
    plan_config: { enabled: true, effort: 'medium' },
    review_config: { enabled: false, max_rework: 3 },
  };
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadProjects(), loadDailyDirs(), loadResources()]);
    await loadTasks();
    if (selectedTaskId.value) await loadSelectedTask();
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
    if (!selectedDailyDirId.value && dailyDirs.value.length) {
      selectedDailyDirId.value = dailyDirs.value[0].id;
    }
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
  const requestId = ++taskListRequestId;
  const params: any = { page_size: 100, work_scope: selectedScope.value, include_hitl_cards: false };
  if (selectedScope.value === 'project' && selectedProjectId.value) params.project_id = selectedProjectId.value;
  if (selectedScope.value === 'daily' && selectedDailyDirId.value) params.daily_dir_id = selectedDailyDirId.value;
  const response = await axios.get('/api/plug/work/tasks', { params });
  if (requestId !== taskListRequestId) return;
  if (response.data?.status === 'ok') {
    tasks.value = response.data.data?.tasks || [];
  }
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
      params: { logs_limit: 5000 },
    });
    if (requestId !== selectedTaskRequestId || taskId !== selectedTaskId.value) return;
    if (response.data?.status === 'ok') {
      selectedTask.value = response.data.data;
      if (!mergeLogs || !eventSource) logs.value = selectedTask.value.logs || [];
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

function selectDaily(id: string | null) {
  selectedScope.value = 'daily';
  selectedDailyDirId.value = id;
  selectedProjectId.value = null;
  clearSelection();
  loadTasks();
}

function selectProject(id: string | null) {
  selectedScope.value = 'project';
  selectedProjectId.value = id;
  selectedDailyDirId.value = null;
  clearSelection();
  loadTasks();
}

function clearSelection() {
  selectedTaskRequestId += 1;
  pendingSelectedReload = false;
  selectedTaskId.value = null;
  selectedTask.value = null;
  logs.value = [];
  artifacts.value = [];
  interactionCards.value = [];
  selectedStep.value = null;
  selectedStageIndex.value = 0;
  closeEventSource();
}

async function selectTask(taskId: string) {
  if (selectedTaskId.value === taskId) return;
  selectedTaskRequestId += 1;
  pendingSelectedReload = false;
  selectedTaskId.value = taskId;
  detailTab.value = 'logs';
  interactionCards.value = [];
  selectedStep.value = null;
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
  closeEventSource();
  try {
    eventSource = new EventSource(`/api/plug/work/tasks/${encodeURIComponent(taskId)}/events`);
    const reload = () => {
      if (sseDebounceTimer) clearTimeout(sseDebounceTimer);
      sseDebounceTimer = setTimeout(() => loadSelectedTask(true), 500);
    };

    const appendLog = (event: MessageEvent) => {
      try {
        const log = JSON.parse(event.data);
        if (!log || !log.id) { reload(); return; }
        if (logs.value.find(l => l.id === log.id)) return;
        logs.value = [...logs.value, log].sort((a, b) => Number(a.seq || 0) - Number(b.seq || 0));
      } catch { reload(); }
    };

    eventSource.addEventListener('done', reload);
    eventSource.addEventListener('phase', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data?.status) selectedTask.value = { ...selectedTask.value, status: data.status, progress: data.progress || selectedTask.value?.progress };
      } catch {}
      reload();
    });
    for (const name of ['text_delta', 'tool_call', 'tool_result', 'reasoning', 'token', 'artifact', 'interaction']) {
      eventSource.addEventListener(name, appendLog);
    }
    eventSource.onerror = () => closeEventSource();
  } catch {
    closeEventSource();
  }
}

function closeEventSource() {
  if (sseDebounceTimer) {
    clearTimeout(sseDebounceTimer);
    sseDebounceTimer = null;
  }
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
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
    const payload = JSON.parse(JSON.stringify(taskForm));
    payload.flow_id = payload.executor_config?.flow_id;
    payload.work_task_kind = 'workflow';
    await axios.post('/api/plug/work/tasks', payload);
    taskDialog.value = false;
    await loadTasks();
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
    await loadSelectedTask();
  } finally {
    submittingInput.value = false;
  }
}

async function handleInteractionRespond() {
  hitlDialog.value = false;
  await Promise.all([loadTasks(), loadSelectedTask(true)]);
}

function isCompleted(task: any) {
  return ['completed', 'failed', 'cancelled'].includes(task?.status);
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '执行中',
    paused: '已暂停',
    waiting_feedback: '等待确认',
    completed: '已完成',
    failed: '失败',
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
  };
  return map[status] || status || '-';
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: 'grey',
    running: 'primary',
    waiting_feedback: 'warning',
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
    waiting_feedback: 'mdi-account-question-outline',
    completed: 'mdi-check-circle-outline',
    failed: 'mdi-alert-circle-outline',
    cancelled: 'mdi-cancel',
  };
  return map[status] || 'mdi-circle-outline';
}

function taskKindLabel(kind: string) {
  const map: Record<string, string> = {
    single_agent: '单智能体',
    multi_agent: '多智能体',
    workflow: '业务流',
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
    const name = resourceNameById(flows.value, config.flow_id || task?.flow_id);
    return name ? `执行流程：${name}` : '执行流程：已配置';
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
  if (status === 'failed') return 'mdi-alert-circle-outline';
  return 'mdi-circle-outline';
}

function stepColor(status: string) {
  if (status === 'done' || status === 'completed') return 'success';
  if (status === 'running') return 'primary';
  if (status === 'failed') return 'error';
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
  refreshAll();
  pollTimer = setInterval(() => {
    if (document.hidden) return;
    loadTasks();
    if (!eventSource) loadSelectedTask();
  }, 5000);
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  if (sseDebounceTimer) clearTimeout(sseDebounceTimer);
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
  grid-template-columns: 210px 320px minmax(360px, 1fr) 380px;
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

.work-category-pane,
.work-task-pane,
.work-progress-pane {
  min-height: 0;
  border-right: 1px solid var(--work-border);
  background: var(--work-panel);
}

.work-category-pane {
  overflow: auto;
}

.work-category-pane,
.work-progress-pane {
  padding: 14px;
}

.work-progress-pane {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 0;
  border-left: 1px solid var(--work-border);
}

.pane-header,
.detail-header,
.task-card-top,
.artifact-title,
.filter-row,
.dialog-row,
.option-row,
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
.category-row.active,
.task-card:hover,
.task-card.active {
  background: rgba(var(--v-theme-primary), 0.1);
}

.category-row.child {
  min-height: 34px;
  font-size: 13px;
}

.category-children {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0 14px 12px;
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

.filter-row,
.dialog-row,
.option-row {
  gap: 10px;
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
  padding: 18px max(18px, calc((100% - 880px) / 2));
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

.progress-pane-header {
  position: sticky;
  top: 0;
  z-index: 1;
  padding-bottom: 8px;
  background: var(--work-panel);
}

.step-list-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
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

.progress-empty {
  flex: 1;
}

@media (max-width: 1180px) {
  .work-shell {
    grid-template-columns: 170px 260px minmax(300px, 1fr) 320px;
  }
}

@media (max-width: 820px) {
  .work-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto 1fr auto;
  }

  .work-category-pane,
  .work-task-pane {
    max-height: 210px;
    border-right: 0;
    border-bottom: 1px solid var(--work-border);
  }

  .category-children {
    margin-left: 0;
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

  .work-progress-pane {
    max-height: 240px;
    border-left: 0;
    border-top: 1px solid var(--work-border);
  }
}
</style>
