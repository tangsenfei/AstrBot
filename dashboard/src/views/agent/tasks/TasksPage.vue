<template>
  <v-container fluid class="pa-6">
    <v-row>
      <v-col cols="12">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-clipboard-check" class="mr-2" />
            {{ $t('agent.tasks.title') }}
            <v-spacer />
            <v-btn color="primary" @click="openCreateDialog" class="mr-2">
              <v-icon start icon="mdi-plus" />
              {{ $t('agent.tasks.buttons.add') }}
            </v-btn>
            <v-btn variant="outlined" @click="loadTasks" :loading="loading" class="mr-2">
              <v-icon start icon="mdi-refresh" />
              {{ $t('agent.tasks.buttons.refresh') }}
            </v-btn>
          </v-card-title>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" md="3" sm="6">
        <v-card class="stat-card" color="blue-lighten-5">
          <v-card-text class="d-flex align-center">
            <v-avatar color="blue" size="48" class="mr-4">
              <v-icon icon="mdi-clipboard-list" color="white" />
            </v-avatar>
            <div>
              <div class="text-caption text-grey">总任务</div>
              <div class="text-h5 font-weight-bold">{{ stats.total_tasks || 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card class="stat-card" color="green-lighten-5">
          <v-card-text class="d-flex align-center">
            <v-avatar color="green" size="48" class="mr-4">
              <v-icon icon="mdi-check-circle" color="white" />
            </v-avatar>
            <div>
              <div class="text-caption text-grey">已完成</div>
              <div class="text-h5 font-weight-bold">{{ stats.status_counts?.completed || 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card class="stat-card" color="orange-lighten-5">
          <v-card-text class="d-flex align-center">
            <v-avatar color="orange" size="48" class="mr-4">
              <v-icon icon="mdi-run" color="white" />
            </v-avatar>
            <div>
              <div class="text-caption text-grey">运行中</div>
              <div class="text-h5 font-weight-bold">{{ stats.status_counts?.running || 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3" sm="6">
        <v-card class="stat-card" color="purple-lighten-5">
          <v-card-text class="d-flex align-center">
            <v-avatar color="purple" size="48" class="mr-4">
              <v-icon icon="mdi-account-group" color="white" />
            </v-avatar>
            <div>
              <div class="text-caption text-grey">会议任务</div>
              <div class="text-h5 font-weight-bold">{{ stats.meeting_tasks_count || 0 }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-text class="pb-2">
            <v-row align="center">
              <v-col cols="12" md="4">
                <v-tabs v-model="activeTab" color="primary">
                  <v-tab value="all">全部</v-tab>
                  <v-tab value="daily">日常</v-tab>
                  <v-tab value="crew">团队</v-tab>
                  <v-tab value="flow">流程</v-tab>
                  <v-tab value="meeting">会议</v-tab>
                </v-tabs>
              </v-col>
              <v-col cols="12" md="4">
                <v-select
                  v-model="statusFilter"
                  :items="statusOptions"
                  item-title="label"
                  item-value="value"
                  label="状态筛选"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="searchQuery"
                  placeholder="搜索任务..."
                  prepend-inner-icon="mdi-magnify"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-text v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
          </v-card-text>

          <v-card-text v-else-if="filteredTasks.length === 0" class="text-center py-8">
            <v-icon icon="mdi-clipboard-check-off" size="60" color="grey-lighten-1" class="mb-4" />
            <p class="text-grey">暂无任务</p>
          </v-card-text>

          <v-table v-else hover>
            <thead>
              <tr>
                <th>任务名称</th>
                <th>类型</th>
                <th>关联</th>
                <th>状态</th>
                <th>进度</th>
                <th>Token</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in paginatedTasks" :key="task.id">
                <td>
                  <div class="font-weight-medium">{{ task.name }}</div>
                  <div class="text-caption text-grey">{{ task.description || '-' }}</div>
                </td>
                <td>
                  <v-chip
                    :color="getTaskTypeColor(task.task_type, task.category)"
                    size="small">
                    <v-icon start :icon="getTaskTypeIcon(task.task_type, task.category)" size="14" />
                    {{ getTaskTypeLabel(task.task_type, task.category) }}
                  </v-chip>
                </td>
                <td>
                  <span v-if="task.crew_id" class="text-body-2">
                    <v-icon icon="mdi-account-group" size="14" class="mr-1" />
                    {{ task.crew_id }}
                  </span>
                  <span v-else-if="task.flow_id" class="text-body-2">
                    <v-icon icon="mdi-sitemap" size="14" class="mr-1" />
                    {{ task.flow_id }}
                  </span>
                  <span v-else-if="task.meeting_id" class="text-body-2">
                    <v-icon icon="mdi-video" size="14" class="mr-1" />
                    {{ task.meeting_id }}
                  </span>
                  <span v-else class="text-grey">-</span>
                </td>
                <td>
                  <v-chip
                    :color="getStatusColor(task.status)"
                    size="small"
                    variant="tonal"
                  >
                    {{ getStatusLabel(task.status) }}
                  </v-chip>
                </td>
                <td>
                  <v-progress-linear
                    :model-value="task.progress || 0"
                    :color="getStatusColor(task.status)"
                    height="6"
                    rounded
                    style="width: 80px"
                  />
                  <span class="text-caption">{{ task.progress || 0 }}%</span>
                </td>
                <td class="text-body-2">{{ formatTokens(task.total_tokens) }}</td>
                <td class="text-body-2">{{ formatDate(task.created_at) }}</td>
                <td>
                  <v-btn icon variant="text" size="small" @click="viewTaskDetail(task)">
                    <v-icon icon="mdi-eye" size="18" />
                  </v-btn>
                  <v-btn
                    v-if="task.status === 'running'"
                    icon variant="text" size="small"
                    color="warning"
                    @click="pauseTask(task)"
                  >
                    <v-icon icon="mdi-pause" size="18" />
                  </v-btn>
                  <v-btn
                    v-if="task.status === 'paused'"
                    icon variant="text" size="small"
                    color="success"
                    @click="resumeTask(task)"
                  >
                    <v-icon icon="mdi-play" size="18" />
                  </v-btn>
                  <v-btn
                    v-if="['pending', 'running', 'paused', 'waiting_feedback'].includes(task.status)"
                    icon variant="text" size="small"
                    color="error"
                    @click="cancelTask(task)"
                  >
                    <v-icon icon="mdi-stop" size="18" />
                  </v-btn>
                  <v-btn
                    v-if="['failed', 'cancelled'].includes(task.status)"
                    icon variant="text" size="small"
                    color="primary"
                    @click="retryTask(task)"
                  >
                    <v-icon icon="mdi-refresh" size="18" />
                  </v-btn>
                  <v-btn icon variant="text" size="small" color="error" @click="deleteTask(task)">
                    <v-icon icon="mdi-delete" size="18" />
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>

          <v-card-actions v-if="totalPages > 1" class="justify-center">
            <v-pagination
              v-model="currentPage"
              :length="totalPages"
              :total-visible="5"
              density="compact"
            />
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog v-model="showCreateDialog" max-width="600">
      <v-card>
        <v-card-title>
          <v-icon icon="mdi-plus-circle" class="mr-2" />
          新建任务
        </v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newTask.name"
            label="任务名称"
            :rules="[v => !!v || '请输入任务名称']"
            class="mb-3"
          />
          <v-textarea
            v-model="newTask.description"
            label="任务描述"
            rows="2"
            auto-grow
            class="mb-3"
          />
          <v-select
            v-model="newTask.task_type"
            :items="taskTypeOptions"
            item-title="label"
            item-value="value"
            label="任务类型"
            class="mb-3"
          />

          <v-select
            v-if="newTask.task_type === 'crew'"
            v-model="newTask.crew_id"
            :items="availableCrews"
            item-title="name"
            item-value="name"
            label="选择团队"
            :rules="[v => !!v || '请选择团队']"
            class="mb-3"
          />

          <v-select
            v-if="newTask.task_type === 'flow'"
            v-model="newTask.flow_id"
            :items="availableFlows"
            item-title="name"
            item-value="id"
            label="选择流程"
            :rules="[v => !!v || '请选择流程']"
            class="mb-3"
          />

          <v-select
            v-if="newTask.task_type === 'meeting'"
            v-model="newTask.meeting_id"
            :items="availableMeetings"
            item-title="name"
            item-value="id"
            label="选择会议"
            :rules="[v => !!v || '请选择会议']"
            class="mb-3"
          />

          <v-textarea
            v-model="newTaskInput"
            label="输入数据（JSON格式）"
            rows="3"
            auto-grow
            placeholder='{"key": "value"}'
            class="mb-3"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showCreateDialog = false">取消</v-btn>
          <v-btn color="primary" @click="createTask" :loading="creating" :disabled="!newTask.name">
            创建
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showDetailDialog" max-width="800">
      <v-card v-if="selectedTask">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-clipboard-text" class="mr-2" />
          {{ selectedTask.name }}
          <v-spacer />
          <v-chip :color="getStatusColor(selectedTask.status)" size="small" variant="tonal">
            {{ getStatusLabel(selectedTask.status) }}
          </v-chip>
        </v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="6">
              <div class="text-caption text-grey">任务类型</div>
              <v-chip :color="getTaskTypeColor(selectedTask.task_type, selectedTask.category)" size="small" variant="tonal" label>
                <v-icon start :icon="getTaskTypeIcon(selectedTask.task_type, selectedTask.category)" size="14" />
                {{ getTaskTypeLabel(selectedTask.task_type, selectedTask.category) }}
              </v-chip>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">进度</div>
              <v-progress-linear :model-value="selectedTask.progress || 0" :color="getStatusColor(selectedTask.status)" height="8" rounded class="mt-2" />
              <span class="text-caption">{{ selectedTask.progress || 0 }}%</span>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">描述</div>
              <div class="text-body-2">{{ selectedTask.description || '无' }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">Token 消耗</div>
              <div class="text-body-2">{{ formatTokens(selectedTask.total_tokens) }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-grey">创建时间</div>
              <div class="text-body-2">{{ formatDate(selectedTask.created_at) }}</div>
            </v-col>
            <v-col cols="6" v-if="selectedTask.completed_at">
              <div class="text-caption text-grey">完成时间</div>
              <div class="text-body-2">{{ formatDate(selectedTask.completed_at) }}</div>
            </v-col>
            <v-col cols="12" v-if="selectedTask.error">
              <div class="text-caption text-grey">错误信息</div>
              <v-alert type="error" variant="tonal" density="compact" class="mt-1">
                {{ selectedTask.error }}
              </v-alert>
            </v-col>
            <v-col cols="12" v-if="selectedTask.result">
              <div class="text-caption text-grey">执行结果</div>
              <v-alert type="success" variant="tonal" density="compact" class="mt-1">
                {{ selectedTask.result }}
              </v-alert>
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showDetailDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <div v-if="activeCards.length" class="active-cards-bar pa-3 mb-4">
      <div class="text-subtitle-2 font-weight-medium mb-2">⏳ 待处理审核</div>
      <InteractionCardComponent
        v-for="card in activeCards"
        :key="card.interaction_id"
        :card="card"
        :resolved="card._resolved"
        @respond="fetchPendingCards"
      />
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import axios from 'axios';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';

const loading = ref(false);
const creating = ref(false);
const tasks = ref<any[]>([]);
const stats = ref<any>({});
const activeTab = ref('all');
const statusFilter = ref<string | null>(null);
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = 20;

const showCreateDialog = ref(false);
const showDetailDialog = ref(false);
const selectedTask = ref<any>(null);

const newTask = ref({
  name: '',
  description: '',
  task_type: 'crew',
  crew_id: '',
  flow_id: '',
  meeting_id: '',
});
const newTaskInput = ref('');

const availableCrews = ref<any[]>([]);
const availableFlows = ref<any[]>([]);
const availableMeetings = ref<any[]>([]);

const taskTypeOptions = [
  { label: '团队任务', value: 'crew' },
  { label: '流程任务', value: 'flow' },
  { label: '会议任务', value: 'meeting' },
];

const statusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '运行中', value: 'running' },
  { label: '已暂停', value: 'paused' },
  { label: '等待反馈', value: 'waiting_feedback' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' },
];

const filteredTasks = computed(() => {
  let result = tasks.value;
  if (activeTab.value === 'daily') {
    result = result.filter(t => t.category === 'daily');
  } else if (activeTab.value !== 'all') {
    result = result.filter(t => t.task_type === activeTab.value);
  }
  if (statusFilter.value) {
    result = result.filter(t => t.status === statusFilter.value);
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(t =>
      t.name.toLowerCase().includes(q) ||
      (t.description || '').toLowerCase().includes(q)
    );
  }
  return result;
});

const totalPages = computed(() => Math.ceil(filteredTasks.value.length / pageSize));

const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredTasks.value.slice(start, start + pageSize);
});

function getTaskTypeLabel(type: string, category?: string): string {
  if (category === 'daily') return '日常任务';
  const labels: Record<string, string> = { crew: '团队', flow: '流程', meeting: '会议' };
  return labels[type] || type;
}

function getTaskTypeColor(type: string, category?: string): string {
  if (category === 'daily') return 'primary';
  const colors: Record<string, string> = { crew: 'cyan', flow: 'indigo', meeting: 'purple' };
  return colors[type] || 'grey';
}

function getTaskTypeIcon(type: string, category?: string): string {
  if (category === 'daily') return 'mdi-chat-processing';
  const icons: Record<string, string> = { crew: 'mdi-account-group', flow: 'mdi-sitemap', meeting: 'mdi-video' };
  return icons[type] || 'mdi-clipboard';
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '待执行', running: '运行中', paused: '已暂停',
    waiting_feedback: '等待反馈', completed: '已完成', failed: '失败', cancelled: '已取消',
  };
  return labels[status] || status;
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'grey', running: 'blue', paused: 'orange',
    waiting_feedback: 'amber', completed: 'green', failed: 'red', cancelled: 'grey-darken-1',
  };
  return colors[status] || 'grey';
}

function formatTokens(tokens: number): string {
  if (!tokens) return '0';
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${tokens}`;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleString('zh-CN');
  } catch {
    return dateStr;
  }
}

async function loadTasks() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/tasks', {
      params: { page_size: 100 },
    });
    if (response.data.status === 'ok') {
      tasks.value = response.data.data?.tasks || [];
    }
  } catch (error) {
    console.error('Failed to load tasks:', error);
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    const response = await axios.get('/api/plug/agent/tasks/stats');
    if (response.data.status === 'ok') {
      stats.value = response.data.data || {};
    }
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}

async function loadAvailableResources() {
  try {
    const [crewsRes, flowsRes, meetingsRes] = await Promise.allSettled([
      axios.get('/api/plug/agent/crews'),
      axios.get('/api/plug/agent/flows'),
      axios.get('/api/plug/agent/roundtables'),
    ]);
    if (crewsRes.status === 'fulfilled' && crewsRes.value.data.status === 'ok') {
      availableCrews.value = crewsRes.value.data.data || [];
    }
    if (flowsRes.status === 'fulfilled' && flowsRes.value.data.status === 'ok') {
      availableFlows.value = flowsRes.value.data.data || [];
    }
    if (meetingsRes.status === 'fulfilled' && meetingsRes.value.data.status === 'ok') {
      availableMeetings.value = meetingsRes.value.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load resources:', error);
  }
}

function openCreateDialog() {
  newTask.value = { name: '', description: '', task_type: 'crew', crew_id: '', flow_id: '', meeting_id: '' };
  newTaskInput.value = '';
  showCreateDialog.value = true;
  loadAvailableResources();
}

async function createTask() {
  if (!newTask.value.name) return;
  creating.value = true;
  try {
    let inputData = {};
    if (newTaskInput.value) {
      try {
        inputData = JSON.parse(newTaskInput.value);
      } catch {
        inputData = { raw: newTaskInput.value };
      }
    }
    const payload: any = {
      name: newTask.value.name,
      description: newTask.value.description,
      task_type: newTask.value.task_type,
      input: inputData,
    };
    if (newTask.value.task_type === 'crew' && newTask.value.crew_id) {
      payload.crew_id = newTask.value.crew_id;
    }
    if (newTask.value.task_type === 'flow' && newTask.value.flow_id) {
      payload.flow_id = newTask.value.flow_id;
    }
    if (newTask.value.task_type === 'meeting' && newTask.value.meeting_id) {
      payload.meeting_id = newTask.value.meeting_id;
    }
    await axios.post('/api/plug/agent/tasks/add', payload);
    showCreateDialog.value = false;
    await loadTasks();
    await loadStats();
  } catch (error: any) {
    console.error('Failed to create task:', error);
    alert(error.response?.data?.message || '创建任务失败');
  } finally {
    creating.value = false;
  }
}

function viewTaskDetail(task: any) {
  selectedTask.value = task;
  showDetailDialog.value = true;
}

async function pauseTask(task: any) {
  try {
    await axios.post(`/api/plug/agent/tasks/${task.id}/pause`);
    await loadTasks();
  } catch (error: any) {
    alert(error.response?.data?.message || '暂停失败');
  }
}

async function resumeTask(task: any) {
  try {
    await axios.post(`/api/plug/agent/tasks/${task.id}/resume`);
    await loadTasks();
  } catch (error: any) {
    alert(error.response?.data?.message || '恢复失败');
  }
}

async function cancelTask(task: any) {
  try {
    await axios.post(`/api/plug/agent/tasks/${task.id}/cancel`);
    await loadTasks();
    await loadStats();
  } catch (error: any) {
    alert(error.response?.data?.message || '取消失败');
  }
}

async function retryTask(task: any) {
  try {
    await axios.post(`/api/plug/agent/tasks/${task.id}/retry`);
    await loadTasks();
    await loadStats();
  } catch (error: any) {
    alert(error.response?.data?.message || '重试失败');
  }
}

async function deleteTask(task: any) {
  if (!confirm(`确定删除任务 "${task.name}" 吗？`)) return;
  try {
    await axios.delete(`/api/plug/agent/tasks/${task.id}`);
    await loadTasks();
    await loadStats();
  } catch (error: any) {
    alert(error.response?.data?.message || '删除失败');
  }
}

watch(activeTab, () => { currentPage.value = 1; });

const activeCards = ref<any[]>([]);
let pollTimer: ReturnType<typeof setInterval> | null = null;

async function fetchPendingCards() {
  try {
    const resp = await axios.get('/api/interaction/pending');
    if (resp.data?.status === 'ok' && resp.data?.data?.cards) {
      activeCards.value = resp.data.data.cards.map((c: any) => ({ ...c, _resolved: null }));
    }
  } catch (e) { /* ignore */ }
}

onMounted(() => {
  loadTasks();
  loadStats();
  fetchPendingCards();
  pollTimer = setInterval(fetchPendingCards, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
});
</script>

<style scoped>
.stat-card {
  border-radius: 12px;
  transition: transform 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}
</style>
