<template>
  <div class="interaction-card-wrapper">
    <v-card class="interaction-card" :class="[`card-${resolvedStatus || 'active'}`, { 'is-dark': isDark }]" variant="outlined">
      <v-card-text class="pa-3">
        <div class="d-flex align-center mb-2">
          <v-icon :icon="typeIcon" :color="typeColor" size="20" class="mr-2" />
          <span class="text-subtitle-2 font-weight-medium">{{ card.title }}</span>
          <v-chip v-if="resolvedStatus" size="x-small" :color="statusColor" variant="flat" class="ml-2">
            {{ statusLabel }}
          </v-chip>
        </div>

        <div class="card-body text-body-2 mb-3" style="white-space: pre-wrap; line-height: 1.6;">
          {{ card.body }}
        </div>

        <div v-if="card.fields && card.fields.length && !resolvedStatus" class="card-fields mb-3">
          <div v-for="field in card.fields" :key="field.key" class="mb-2">
            <label class="text-caption d-block mb-1">{{ field.label }}{{ field.required ? ' *' : '' }}</label>
            <v-textarea
              v-if="field.field_type === 'textarea'"
              v-model="fieldValues[field.key]"
              :placeholder="field.default || ''"
              rows="2"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-text-field
              v-else-if="field.field_type === 'text'"
              v-model="fieldValues[field.key]"
              :placeholder="field.default || ''"
              density="compact"
              variant="outlined"
              hide-details
            />
          </div>
        </div>

        <div class="card-actions d-flex ga-2 justify-end" v-if="!resolvedStatus">
          <v-btn
            v-for="action in card.actions"
            :key="action.key"
            :color="action.style === 'danger' ? 'error' : action.style === 'primary' ? 'primary' : undefined"
            :variant="action.style === 'primary' ? 'flat' : 'outlined'"
            size="small"
            :loading="loadingAction === action.key"
            @click="handleAction(action)"
          >
            {{ action.label }}
          </v-btn>
        </div>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

const props = defineProps<{
  card: {
    interaction_id: string;
    type: string;
    title: string;
    body: string;
    fields: Array<{ key: string; label: string; field_type: string; required: boolean; default?: string }>;
    actions: Array<{ key: string; label: string; style: string }>;
    timeout_seconds?: number;
  };
  isDark?: boolean;
  resolved?: { status: string; message: string } | null;
}>();

const emit = defineEmits<{
  (e: 'respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

const loadingAction = ref<string | null>(null);
const fieldValues = ref<Record<string, any>>({});
const resolvedLocally = ref<string | null>(null);
const resolvedStatus = computed(() => resolvedLocally.value || props.resolved?.status || null);

const typeIcon = computed(() => {
  const map: Record<string, string> = {
    task_confirm: 'mdi-check-circle-outline',
    plan_approval: 'mdi-clipboard-check-outline',
    workflow_human: 'mdi-account-question-outline',
    error_recovery: 'mdi-alert-circle-outline',
    clarification: 'mdi-help-circle-outline',
  };
  return map[props.card.type] || 'mdi-message-outline';
});

const typeColor = computed(() => {
  const map: Record<string, string> = {
    task_confirm: 'primary',
    plan_approval: 'info',
    workflow_human: 'warning',
    error_recovery: 'error',
    clarification: 'info',
  };
  return map[props.card.type] || 'grey';
});

const statusColor = computed(() => {
  const map: Record<string, string> = {
    confirmed: 'success',
    cancelled: 'grey',
    rejected: 'error',
    modified: 'warning',
  };
  return map[resolvedStatus.value || ''] || 'grey';
});

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    confirmed: '已确认',
    cancelled: '已取消',
    rejected: '已拒绝',
    modified: '已修改',
  };
  return map[resolvedStatus.value || ''] || '';
});

async function handleAction(action: { key: string; label: string }) {
  loadingAction.value = action.key;
  try {
    const response = await fetch('/api/interaction/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interaction_id: props.card.interaction_id,
        action_key: action.key,
        field_values: fieldValues.value,
      }),
    });
    if (response.ok) {
      resolvedLocally.value = action.key === 'confirm' ? 'confirmed' : action.key === 'cancel' ? 'cancelled' : 'rejected';
      emit('respond', {
        interaction_id: props.card.interaction_id,
        action_key: action.key,
        field_values: fieldValues.value,
      });
    }
  } catch (e) {
    console.error('Interaction respond failed:', e);
  } finally {
    loadingAction.value = null;
  }
}
</script>

<style scoped>
.interaction-card-wrapper { margin: 4px 0; }
.interaction-card {
  border-radius: 8px;
  transition: opacity 0.3s;
}
.interaction-card.card-confirmed,
.interaction-card.card-cancelled,
.interaction-card.card-rejected { opacity: 0.65; }
.card-body {
  color: rgba(var(--v-theme-on-surface), 0.87);
  font-size: 14px;
}
.card-fields { max-width: 400px; }
</style>
