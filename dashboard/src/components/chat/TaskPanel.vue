<template>
  <div class="task-panel">
    <div class="panel-header">
      <span class="text-subtitle-2 font-weight-medium">
        <v-icon icon="mdi-clipboard-list" size="18" class="mr-1" /> Work 任务
      </span>
      <v-btn icon="mdi-refresh" size="x-small" variant="text" :loading="loading" @click="fetchTasks" />
      <v-btn icon size="x-small" variant="text" @click="$emit('close')">
        <v-icon size="16">mdi-close</v-icon>
      </v-btn>
    </div>

    <WorkTaskList
      class="task-list"
      :tasks="tasks"
      :selected-task-id="selectedTask?.id || null"
      :loading="loading"
      :is-dark="isDark"
      compact
      @select="selectTask"
      @interaction-respond="handleInteractionRespond"
    />

    <TaskDetailOverlay
      v-if="selectedTask"
      :task="selectedTask"
      @close="selectedTask = null"
      @input-submitted="onInputSubmitted"
      @interaction-respond="handleInteractionRespond"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, inject, type ComputedRef } from 'vue';
import axios from 'axios';
import TaskDetailOverlay from './TaskDetailOverlay.vue';
import WorkTaskList from '@/components/work/WorkTaskList.vue';

defineEmits(['close']);

const tasks = ref<any[]>([]);
const loading = ref(true);
const selectedTask = ref<any>(null);
const injectedIsDark = inject<ComputedRef<boolean> | null>('isDark', null);
const isDark = injectedIsDark?.value || false;
let pollTimer: ReturnType<typeof setInterval> | null = null;

async function selectTask(taskId: string) {
  const fallback = tasks.value.find((task) => task.id === taskId) || null;
  selectedTask.value = fallback;
  try {
    const resp = await axios.get(`/api/plug/work/tasks/${encodeURIComponent(taskId)}`, {
      params: { logs_limit: 80 },
    });
    if (resp.data?.status === 'ok') {
      selectedTask.value = resp.data.data;
    }
  } catch (e) {
    console.error('Failed to load work task:', e);
  }
}

async function fetchTasks() {
  loading.value = true;
  try {
    const resp = await axios.get('/api/plug/work/tasks', {
      params: { page_size: 50, include_hitl_cards: false },
    });
    if (resp.data?.status === 'ok') {
      tasks.value = resp.data.data?.tasks || [];
      if (selectedTask.value) {
        const fresh = tasks.value.find((task) => task.id === selectedTask.value.id);
        if (fresh) selectedTask.value = { ...selectedTask.value, ...fresh };
      }
    }
  } catch (e) { /* ignore */ }
  loading.value = false;
}

function onInputSubmitted(taskId: string, text: string) {
  axios.post(`/api/plug/work/tasks/${taskId}/input`, { text })
    .then(() => fetchTasks())
    .catch((e) => console.error('Failed to submit input:', e));
}

async function handleInteractionRespond() {
  await fetchTasks();
}

onMounted(() => {
  fetchTasks();
  pollTimer = setInterval(fetchTasks, 5000);
});

onBeforeUnmount(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
});
</script>

<style scoped>
.task-panel {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}

.panel-header {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
}

.task-list {
  padding-bottom: 16px;
}
</style>
