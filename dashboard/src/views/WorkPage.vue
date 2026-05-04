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
        @interaction-respond="handleInteractionRespond"
      />
    </aside>

    <main class="work-detail-pane">
      <template v-if="selectedTask">
        <header class="detail-header">
          <div>
            <div class="detail-title">{{ selectedTask.name }}</div>
            <div class="detail-subtitle">
              {{ taskKindLabel(selectedTask.work_task_kind || selectedTask.task_type) }}
              · {{ statusLabel(selectedTask.status) }}
              · {{ selectedTask.progress || 0 }}%
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
          <v-tab value="progress">
            <v-icon start size="16">mdi-timeline-text-outline</v-icon>
            进展
          </v-tab>
          <v-tab value="artifacts" :disabled="!isCompleted(selectedTask)">
            <v-icon start size="16">mdi-package-variant-closed</v-icon>
            交付物
          </v-tab>
          <v-tab value="logs">
            <v-icon start size="16">mdi-text-box-search-outline</v-icon>
            日志
          </v-tab>
        </v-tabs>

        <section class="detail-body">
          <WorkProgressTimeline
            v-if="detailTab === 'progress'"
            :task="selectedTask"
            :logs="logs"
            :active-cards="interactionCards"
            :is-dark="isDark"
            :max-items="MAX_VISIBLE_LOGS"
            @interaction-respond="handleInteractionRespond"
          />

          <div v-else-if="detailTab === 'artifacts'" class="artifact-list">
            <article v-for="artifact in artifacts" :key="artifact.id" class="artifact-item">
              <div class="artifact-title">
                <v-icon size="18">mdi-file-document-outline</v-icon>
                <span>{{ artifact.title }}</span>
              </div>
              <pre>{{ artifact.content || artifact.file_path || '暂无内容' }}</pre>
            </article>
            <div v-if="!artifacts.length" class="empty-state">任务完成后会在这里显示交付结果</div>
          </div>

          <div v-else class="raw-log-list">
            <div v-for="log in logs" :key="log.id" class="raw-log-row">
              <span>{{ formatDate(log.created_at) }}</span>
              <strong>{{ log.level }}</strong>
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
      <div class="pane-title small">子任务进度</div>
      <div v-if="selectedTask" class="step-list">
        <div v-for="step in steps" :key="step.id || step.description" class="step-row">
          <v-icon :color="stepColor(step.status)" :icon="stepIcon(step.status)" size="18" />
          <div>
            <div class="step-title">{{ step.description || step.name }}</div>
            <div v-if="step.result" class="step-result">{{ step.result }}</div>
          </div>
        </div>
        <div v-if="!steps.length" class="empty-state compact">暂无步骤</div>
      </div>
      <div v-if="selectedTask" class="token-box">
        <div>Token 消耗</div>
        <strong>{{ formatTokens(selectedTask.total_tokens) }}</strong>
        <span>输入 {{ formatTokens(selectedTask.input_tokens) }} · 输出 {{ formatTokens(selectedTask.output_tokens) }}</span>
      </div>
    </aside>

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
            <v-select v-model="taskForm.work_task_kind" :items="kindOptions" label="任务类型" variant="outlined" />
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
          <div class="dialog-row">
            <v-select
              v-if="taskForm.work_task_kind === 'single_agent'"
              v-model="taskForm.executor_config.agent_id"
              :items="agents"
              item-title="name"
              item-value="id"
              label="执行智能体（可选）"
              variant="outlined"
              clearable
            />
            <v-select
              v-if="taskForm.work_task_kind === 'multi_agent'"
              v-model="taskForm.executor_config.crew_id"
              :items="crews"
              item-title="name"
              item-value="id"
              label="执行团队（可选）"
              variant="outlined"
              clearable
            />
            <v-select
              v-if="taskForm.work_task_kind === 'workflow'"
              v-model="taskForm.executor_config.flow_id"
              :items="flows"
              item-title="name"
              item-value="id"
              label="业务流程"
              variant="outlined"
            />
          </div>
          <div class="option-row">
            <v-checkbox v-model="taskForm.plan_config.enabled" label="先规划并进入人工确认" density="compact" hide-details />
            <v-checkbox v-model="taskForm.review_config.enabled" label="执行后审查" density="compact" hide-details />
            <v-text-field
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
import WorkProgressTimeline from '@/components/work/WorkProgressTimeline.vue';
import { useCustomizerStore } from '@/stores/customizer';

const customizer = useCustomizerStore();
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');

const loading = ref(false);
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
const detailTab = ref('progress');
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
const MAX_VISIBLE_LOGS = 120;

const agents = ref<any[]>([]);
const crews = ref<any[]>([]);
const flows = ref<any[]>([]);

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

function defaultTaskForm() {
  return {
    name: '',
    description: '',
    work_task_kind: 'single_agent',
    work_scope: selectedScope.value,
    work_project_id: selectedProjectId.value,
    work_daily_dir_id: selectedDailyDirId.value,
    executor_config: { agent_id: '', crew_id: '', flow_id: '' },
    plan_config: { enabled: false, effort: 'medium' },
    review_config: { enabled: false, max_rework: 1 },
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
  if (flowRes.status === 'fulfilled' && flowRes.value.data?.status === 'ok') flows.value = flowRes.value.data.data || [];
}

async function loadTasks() {
  const requestId = ++taskListRequestId;
  const params: any = { page_size: 50, work_scope: selectedScope.value, include_hitl_cards: false };
  if (selectedScope.value === 'project' && selectedProjectId.value) params.project_id = selectedProjectId.value;
  if (selectedScope.value === 'daily' && selectedDailyDirId.value) params.daily_dir_id = selectedDailyDirId.value;
  const response = await axios.get('/api/plug/work/tasks', { params });
  if (requestId !== taskListRequestId) return;
  if (response.data?.status === 'ok') {
    tasks.value = response.data.data?.tasks || [];
  }
}

async function loadSelectedTask() {
  if (!selectedTaskId.value) return;
  const requestId = ++selectedTaskRequestId;
  if (selectedTaskLoading) {
    pendingSelectedReload = true;
    return;
  }
  selectedTaskLoading = true;
  const taskId = selectedTaskId.value;
  try {
    const response = await axios.get(`/api/plug/work/tasks/${taskId}`, {
      params: { logs_limit: MAX_VISIBLE_LOGS },
    });
    if (requestId !== selectedTaskRequestId || taskId !== selectedTaskId.value) return;
    if (response.data?.status === 'ok') {
      selectedTask.value = response.data.data;
      logs.value = (selectedTask.value.logs || []).slice(-MAX_VISIBLE_LOGS);
      artifacts.value = selectedTask.value.artifacts || [];
      interactionCards.value = selectedTask.value.hitl_cards || [];
      if (isCompleted(selectedTask.value) && detailTab.value === 'progress') detailTab.value = 'artifacts';
    }
  } finally {
    selectedTaskLoading = false;
    if (pendingSelectedReload && selectedTaskId.value) {
      pendingSelectedReload = false;
      loadSelectedTask();
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
  closeEventSource();
}

function selectTask(taskId: string) {
  if (selectedTaskId.value === taskId) return;
  selectedTaskRequestId += 1;
  pendingSelectedReload = false;
  selectedTaskId.value = taskId;
  detailTab.value = 'progress';
  interactionCards.value = [];
  closeEventSource();
  loadSelectedTask();
  openEventSource(taskId);
}

function openEventSource(taskId: string) {
  closeEventSource();
  try {
    eventSource = new EventSource(`/api/plug/work/tasks/${encodeURIComponent(taskId)}/events`);
    const reload = () => {
      if (sseDebounceTimer) clearTimeout(sseDebounceTimer);
      sseDebounceTimer = setTimeout(() => loadSelectedTask(), 500);
    };
    for (const name of ['phase', 'text_delta', 'tool_call', 'tool_result', 'reasoning', 'token', 'artifact', 'interaction', 'done']) {
      eventSource.addEventListener(name, reload);
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
  await Promise.all([loadTasks(), loadSelectedTask()]);
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
  grid-template-columns: 210px 320px minmax(360px, 1fr) 300px;
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
  overflow: auto;
  border-right: 1px solid var(--work-border);
  background: var(--work-panel);
}

.work-category-pane,
.work-progress-pane {
  padding: 14px;
}

.work-progress-pane {
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
}

.task-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-bottom: 1px solid var(--work-border);
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
  min-height: 66px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--work-border);
  background: var(--work-panel);
}

.detail-title {
  font-size: 18px;
  font-weight: 800;
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
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-row {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--work-border);
  border-radius: 8px;
  background: var(--work-panel-soft);
}

.step-title {
  font-size: 13px;
  font-weight: 650;
}

.step-result {
  max-height: 70px;
  overflow: hidden;
  margin-top: 4px;
  font-size: 12px;
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
  word-break: break-word;
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
  margin: 0;
}

@media (max-width: 1180px) {
  .work-shell {
    grid-template-columns: 190px 280px minmax(320px, 1fr);
  }

  .work-progress-pane {
    display: none;
  }
}

@media (max-width: 820px) {
  .work-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto 1fr;
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
}
</style>
