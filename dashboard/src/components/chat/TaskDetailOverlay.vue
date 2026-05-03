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
        </div>

        <div v-if="task.description" class="text-body-2 mb-3 text-medium-emphasis">{{ task.description }}</div>

        <div v-if="steps.length > 0" class="steps-section mb-3">
          <div class="text-caption font-weight-medium mb-2">执行步骤</div>
          <div v-for="step in steps" :key="step.id" class="step-item pa-2 mb-1 rounded d-flex align-start"
            :class="{ 'step-done': step.status === 'done', 'step-running': step.status === 'running' }">
            <v-icon :icon="stepIcon(step)" :color="stepColor(step)" size="16" class="mr-2 mt-1" />
            <div class="flex-grow-1">
              <div class="text-body-2">{{ step.description }}</div>
              <div v-if="step.result && step.status === 'done'" class="text-caption text-grey mt-1" style="white-space: pre-wrap; max-height: 80px; overflow-y: auto;">
                {{ step.result.substring(0, 200) }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="task.interaction_id" class="interaction-section mb-3 pa-2 rounded" style="border: 1px solid rgba(var(--v-theme-warning), 0.4); background: rgba(var(--v-theme-warning), 0.04);">
          <div class="text-caption font-weight-medium mb-1">
            <v-icon icon="mdi-hand-back-right" size="14" color="warning" class="mr-1" />
            等待你的操作
          </div>
          <div class="text-caption text-medium-emphasis mb-2">{{ task.interaction_prompt || '请完成交互操作' }}</div>
          <div class="d-flex ga-2">
            <v-btn size="x-small" color="primary" variant="flat"
              @click="respond('confirm')">确认</v-btn>
            <v-btn size="x-small" color="error" variant="outlined"
              @click="respond('cancel')">取消</v-btn>
          </div>
        </div>

        <div class="input-section">
          <div class="text-caption font-weight-medium mb-1">补充信息</div>
          <v-textarea v-model="inputText" rows="2" density="compact" variant="outlined"
            placeholder="输入补充要求后提交..." hide-details class="mb-2" />
          <v-btn size="x-small" variant="outlined" :disabled="!inputText.trim()"
            @click="submitInput">提交</v-btn>
        </div>
      </v-card-text>
    </v-card>
  </v-overlay>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{ task: any }>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'input-submitted', taskId: string, text: string): void;
  (e: 'interaction-respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const visible = ref(true);
const inputText = ref('');

const steps = computed(() => {
  if (Array.isArray(props.task.steps)) return props.task.steps;
  if (typeof props.task.steps === 'string') {
    try { return JSON.parse(props.task.steps); } catch { return []; }
  }
  return [];
});

const progress = computed(() => {
  if (props.task.status === 'completed') return 100;
  if (steps.value.length === 0) return 0;
  const done = steps.value.filter((s: any) => s.status === 'done').length;
  return Math.round((done / steps.value.length) * 100);
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
  if (step.status === 'done') return 'mdi-check-circle';
  if (step.status === 'running') return 'mdi-loading';
  return 'mdi-circle-outline';
}

function stepColor(step: any) {
  if (step.status === 'done') return 'success';
  if (step.status === 'running') return 'primary';
  return 'grey';
}

function submitInput() {
  if (!inputText.value.trim()) return;
  emit('input-submitted', props.task.id, inputText.value.trim());
  inputText.value = '';
}

function respond(key: string) {
  emit('interaction-respond', {
    interaction_id: props.task.interaction_id,
    action_key: key,
    field_values: {},
  });
}
</script>

<style scoped>
.task-detail-card { max-height: 80vh; overflow-y: auto; }
.step-item { border-left: 3px solid transparent; }
.step-done { border-left-color: rgba(var(--v-theme-success), 0.5); background: rgba(var(--v-theme-success), 0.03); }
.step-running { border-left-color: rgba(var(--v-theme-primary), 0.5); background: rgba(var(--v-theme-primary), 0.03); }
</style>
