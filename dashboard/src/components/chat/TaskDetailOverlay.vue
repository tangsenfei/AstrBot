<template>
  <v-overlay v-model="visible" contained class="align-center justify-center" persistent>
    <v-card max-width="420" class="task-detail-card">
      <v-card-title class="d-flex align-center pa-3">
        <v-icon :icon="statusIcon" :color="statusColor" size="20" class="mr-2" />
        <span class="text-subtitle-1 text-truncate">{{ task.name }}</span>
        <v-spacer />
        <v-btn icon size="x-small" variant="text" @click="emit('close')">
          <v-icon size="16">mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-3">
        <div class="mb-3">
          <v-chip :color="statusColor" size="small" variant="flat" class="mr-2">{{ statusLabel }}</v-chip>
          <v-progress-linear :model-value="progress" :color="statusColor" height="6" rounded class="mt-2" />
          <div v-if="currentStep" class="text-caption text-grey mt-1">
            {{ currentStep.activeForm || currentStep.content }}
          </div>
        </div>

        <div v-if="task.description" class="text-body-2 mb-3 text-medium-emphasis">{{ task.description }}</div>

        <div v-if="steps.length > 0" class="steps-section mb-3">
          <div class="text-caption font-weight-medium mb-2">执行步骤</div>
          <div
            v-for="step in steps"
            :key="step.content"
            class="step-item pa-2 mb-1 rounded d-flex align-start"
            :class="{ 'step-done': step.status === 'completed', 'step-running': step.status === 'in_progress', 'step-failed': step.status === 'failed' }"
          >
            <v-icon :icon="stepIcon(step)" :color="stepColor(step)" size="16" class="mr-2 mt-1" />
            <div class="flex-grow-1">
              <div class="text-body-2">{{ step.content }}</div>
              <div v-if="step.result && step.status === 'completed'" class="text-caption text-grey mt-1" style="white-space: pre-wrap; max-height: 80px; overflow-y: auto;">
                {{ step.result.substring(0, 200) }}
              </div>
              <div v-if="step.status === 'failed'" class="mt-1">
                <v-btn size="x-small" variant="outlined" color="warning" @click="retryStep(step)">重试</v-btn>
              </div>
            </div>
          </div>
        </div>

        <div v-if="activeCard" class="interaction-section mb-3">
          <InteractionCardComponent
            :card="activeCard"
            :is-dark="false"
            :resolved="cardResolved"
            @respond="onCardRespond"
          />
        </div>

        <div class="input-section">
          <div class="text-caption font-weight-medium mb-1">补充信息</div>
          <v-textarea
            v-model="inputText"
            rows="2"
            density="compact"
            variant="outlined"
            placeholder="输入补充要求后提交..."
            hide-details
            class="mb-2"
          />
          <v-btn size="x-small" variant="outlined" :disabled="!inputText.trim()" @click="submitInput">提交</v-btn>
        </div>
      </v-card-text>
    </v-card>
  </v-overlay>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import axios from 'axios';
import InteractionCardComponent from '@/components/chat/InteractionCardComponent.vue';

const props = defineProps<{ task: any }>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'input-submitted', taskId: string, text: string): void;
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const visible = ref(true);
const inputText = ref('');
const activeCard = ref<any>(null);
const cardResolved = ref<any>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const steps = computed(() => {
  if (Array.isArray(props.task.steps)) return props.task.steps;
  if (Array.isArray(props.task.todo_steps)) return props.task.todo_steps;
  if (typeof props.task.steps === 'string') {
    try { return JSON.parse(props.task.steps); } catch { return []; }
  }
  return [];
});

const progress = computed(() => {
  if (props.task.status === 'completed') return 100;
  if (steps.value.length === 0) return 0;
  const done = steps.value.filter((s: any) => s.status === 'completed').length;
  return Math.round((done / steps.value.length) * 100);
});

const currentStep = computed(() => {
  return steps.value.find((s: any) => s.status === 'in_progress') || null;
});

const statusLabels: Record<string, string> = {
  pending: '等待中', running: '执行中', completed: '已完成',
  failed: '失败', paused: '已暂停', cancelled: '已取消', waiting_feedback: '等待确认',
};
const statusLabel = computed(() => statusLabels[props.task.status] || props.task.status);

const statusColor = computed(() => {
  if (props.task.status === 'completed') return 'success';
  if (props.task.status === 'failed') return 'error';
  if (props.task.status === 'waiting_feedback') return 'warning';
  return 'primary';
});

const statusIcon = computed(() => {
  if (props.task.status === 'completed') return 'mdi-check-circle';
  if (props.task.status === 'running') return 'mdi-progress-clock';
  return 'mdi-information';
});

function stepIcon(step: any) {
  if (step.status === 'completed') return 'mdi-check-circle';
  if (step.status === 'in_progress') return 'mdi-loading';
  if (step.status === 'failed') return 'mdi-alert-circle';
  return 'mdi-circle-outline';
}

function stepColor(step: any) {
  if (step.status === 'completed') return 'success';
  if (step.status === 'in_progress') return 'primary';
  if (step.status === 'failed') return 'error';
  return 'grey';
}

async function fetchPendingCards() {
  try {
    const resp = await axios.get('/api/interaction/pending');
    if (resp.data?.status === 'ok' && resp.data?.data?.cards) {
      const cards = resp.data.data.cards;
      const taskCard = cards.find(
        (c: any) => c.interaction_id && c.interaction_id.includes(props.task.id)
      );
      if (taskCard && !activeCard.value) {
        activeCard.value = taskCard;
      } else if (!taskCard && activeCard.value && !cardResolved.value) {
        activeCard.value = null;
      }
    }
  } catch (e) { /* ignore */ }
}

function onCardRespond(payload: any) {
  cardResolved.value = {
    status: payload.action_key === 'approve' ? 'approved' : payload.action_key === 'modify' ? 'rejected_with_feedback' : 'rejected',
    message: payload.action_key === 'approve' ? '已通过' : '已处理',
  };
  emit('interaction-respond', payload);
}

function retryStep(step: any) {
  step.status = 'pending';
}

function submitInput() {
  if (!inputText.value.trim()) return;
  emit('input-submitted', props.task.id, inputText.value.trim());
  inputText.value = '';
}

onMounted(() => {
  fetchPendingCards();
  pollTimer = setInterval(fetchPendingCards, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
});
</script>

<style scoped>
.task-detail-card { max-height: 80vh; overflow-y: auto; }
.step-item { border-left: 3px solid transparent; }
.step-done { border-left-color: rgba(var(--v-theme-success), 0.5); background: rgba(var(--v-theme-success), 0.03); }
.step-running { border-left-color: rgba(var(--v-theme-primary), 0.5); background: rgba(var(--v-theme-primary), 0.03); }
.step-failed { border-left-color: rgba(var(--v-theme-error), 0.5); background: rgba(var(--v-theme-error), 0.03); }
</style>
