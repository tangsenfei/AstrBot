<template>
  <div class="interaction-card-wrapper">
    <v-card
      class="interaction-card"
      :class="[`card-${resolvedStatus || 'active'}`, { 'is-dark': isDark }]"
      variant="outlined"
    >
      <v-card-text class="pa-3">
        <div class="d-flex align-center mb-2">
          <v-icon :icon="typeIcon" :color="typeColor" size="20" class="mr-2" />
          <span class="text-subtitle-2 font-weight-medium">{{ card.title }}</span>
          <v-chip
            v-if="resolvedStatus"
            size="x-small"
            :color="statusColor"
            variant="flat"
            class="ml-2"
          >
            {{ statusLabel }}
          </v-chip>
        </div>

        <div class="card-body text-body-2 mb-3" style="white-space: pre-wrap; line-height: 1.6;">
          {{ card.body }}
        </div>

        <div v-if="!resolvedStatus && visibleFields.length" class="card-fields mb-3">
          <div v-for="field in visibleFields" :key="field.key" class="field-row">
            <label class="text-caption d-block mb-1">
              {{ field.label }}{{ field.required ? ' *' : '' }}
            </label>
            <div v-if="field.description" class="text-caption text-medium-emphasis mb-1" style="line-height: 1.4;">
              {{ field.description }}
            </div>
            <v-textarea
              v-if="field.field_type === 'textarea'"
              v-model="fieldValues[field.key]"
              :placeholder="field.custom_placeholder || fieldPlaceholder(field)"
              rows="3"
              density="compact"
              variant="outlined"
              hide-details
              auto-grow
            />
            <div v-else-if="field.field_type === 'select'" class="d-flex align-center ga-2">
              <v-select
                v-model="fieldValues[field.key]"
                :items="fieldOptions(field)"
                density="compact"
                variant="outlined"
                hide-details
                class="flex-grow-1"
                @update:modelValue="(v: any) => onFieldSelect(field.key, v)"
              />
              <v-text-field
                v-if="field.allow_custom && fieldValues[field.key] === '自定义'"
                v-model="customFieldValues[field.key]"
                :placeholder="field.custom_placeholder || '请输入自定义内容'"
                density="compact"
                variant="outlined"
                hide-details
                class="flex-grow-1"
              />
            </div>
            <div v-else-if="field.field_type === 'multiselect'" class="d-flex flex-column ga-1">
              <v-select
                v-model="fieldValues[field.key]"
                :items="fieldOptions(field)"
                density="compact"
                variant="outlined"
                hide-details
                multiple
                chips
                closable-chips
              />
              <v-text-field
                v-if="field.allow_custom && fieldValues[field.key]?.includes('自定义')"
                v-model="customFieldValues[field.key]"
                :placeholder="field.custom_placeholder || '请输入自定义内容，回车添加'"
                density="compact"
                variant="outlined"
                hide-details
                @keydown.enter.prevent="addCustomToMulti(field.key)"
              >
                <template v-slot:append-inner>
                  <v-btn size="x-small" variant="text" icon="mdi-plus" @click="addCustomToMulti(field.key)" />
                </template>
              </v-text-field>
            </div>
            <v-text-field
              v-else
              v-model="fieldValues[field.key]"
              :placeholder="field.custom_placeholder || fieldPlaceholder(field)"
              density="compact"
              variant="outlined"
              hide-details
            />
            <div v-if="field.recommended && !fieldValues[field.key]" class="text-caption text-primary mt-1" style="cursor: pointer;" @click="fieldValues[field.key] = field.recommended">
              💡 推荐：{{ field.recommended }}
            </div>
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
import { ref, computed, watch } from 'vue';

const props = defineProps<{
  card: {
    interaction_id: string;
    type: string;
    title: string;
    body: string;
    fields: Array<{
      key: string;
      label: string;
      field_type: string;
      required: boolean;
      default?: string;
      options?: string[];
      description?: string;
      recommended?: string;
      allow_custom?: boolean;
      custom_placeholder?: string;
    }>;
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
const customFieldValues = ref<Record<string, any>>({});
const revealFields = ref(false);
const resolvedStatus = computed(() => props.resolved?.status || null);
const visibleFields = computed(() => {
  const fields = props.card.fields || [];
  if (!fields.length) return [];
  if (revealFields.value) return fields;
  return fields.filter((field) => field.required);
});

watch(() => props.card?.interaction_id, () => {
  const next: Record<string, any> = {};
  const customNext: Record<string, any> = {};
  for (const field of props.card?.fields || []) {
    if (field.field_type === 'multiselect') {
      next[field.key] = Array.isArray(field.default) ? field.default : (field.default ? [field.default] : []);
    } else {
      next[field.key] = field.default ?? field.recommended ?? '';
    }
    customNext[field.key] = '';
  }
  fieldValues.value = next;
  customFieldValues.value = customNext;
  revealFields.value = false;
}, { immediate: true });

const typeIcon = computed(() => {
  const map: Record<string, string> = {
    task_confirm: 'mdi-check-circle-outline',
    plan_approval: 'mdi-clipboard-check-outline',
    workflow_human: 'mdi-account-question-outline',
    error_recovery: 'mdi-alert-circle-outline',
    clarification: 'mdi-help-circle-outline',
    permission: 'mdi-shield-key-outline',
    info_request: 'mdi-information-outline',
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
    permission: 'warning',
    info_request: 'info',
  };
  return map[props.card.type] || 'grey';
});

const statusColor = computed(() => {
  const map: Record<string, string> = {
    approved: 'success',
    cancelled: 'grey',
    rejected: 'error',
    rejected_with_feedback: 'warning',
  };
  return map[resolvedStatus.value || ''] || 'grey';
});

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    approved: '已通过',
    cancelled: '已取消',
    rejected: '已驳回',
    rejected_with_feedback: '已驳回（已修改）',
  };
  return map[resolvedStatus.value || ''] || '';
});

async function handleAction(action: { key: string; label: string }) {
  const fields = props.card.fields || [];
  const shouldRevealFields = fields.length > 0 && (
    action.key === 'modify' ||
    action.key === 'retry' ||
    action.key === 'clarify_more' ||
    fields.some((field) => field.required && !fieldValues.value[field.key])
  );
  if (shouldRevealFields && !revealFields.value) {
    revealFields.value = true;
    return;
  }
  const missing = fields.find((field) => field.required && !String(fieldValues.value[field.key] ?? '').trim());
  if (missing) {
    revealFields.value = true;
    return;
  }
  loadingAction.value = action.key;
  try {
    const submitValues: Record<string, any> = {};
    for (const [key, val] of Object.entries(fieldValues.value)) {
      if (Array.isArray(val)) {
        const cleaned = val
          .map((v: any) => v === '自定义' ? (customFieldValues.value[key] || v) : v)
          .filter((v: any) => v !== '自定义');
        submitValues[key] = cleaned;
      } else if (val === '自定义' && customFieldValues.value[key]) {
        submitValues[key] = customFieldValues.value[key];
      } else {
        submitValues[key] = val;
      }
    }
    const response = await fetch(`/api/plug/hitl/${encodeURIComponent(props.card.interaction_id)}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action_key: action.key,
        field_values: submitValues,
      }),
    });
    if (response.ok) {
      emit('respond', {
        interaction_id: props.card.interaction_id,
        action_key: action.key,
        field_values: submitValues,
      });
    }
  } catch (e) {
    console.error('Interaction respond failed:', e);
  } finally {
    loadingAction.value = null;
  }
}

function fieldOptions(field: { options?: string[]; allow_custom?: boolean }) {
  const opts = [...(field.options || [])];
  if (field.allow_custom && !opts.includes('自定义')) {
    opts.push('自定义');
  }
  return opts;
}

function onFieldSelect(key: string, value: any) {
  if (value === '自定义') {
    customFieldValues.value[key] = '';
  }
}

function addCustomToMulti(key: string) {
  const custom = customFieldValues.value[key]?.trim();
  if (!custom) return;
  const current = fieldValues.value[key] || [];
  if (!current.includes(custom)) {
    fieldValues.value[key] = [...current, custom];
  }
  const idx = current.indexOf('自定义');
  if (idx >= 0) {
    const updated = [...fieldValues.value[key]];
    updated.splice(updated.indexOf('自定义'), 1);
    fieldValues.value[key] = updated;
  }
  customFieldValues.value[key] = '';
}

function fieldPlaceholder(field: { label: string; field_type: string }) {
  if (field.field_type === 'textarea') return `请输入${field.label}...`;
  return field.label;
}
</script>

<style scoped>
.interaction-card-wrapper { margin: 4px 0; }
.interaction-card {
  border-radius: 8px;
  transition: opacity 0.3s;
}
.interaction-card.card-approved,
.interaction-card.card-cancelled,
.interaction-card.card-rejected { opacity: 0.65; }
.card-body {
  color: rgba(var(--v-theme-on-surface), 0.87);
  font-size: 14px;
}

.field-row + .field-row {
  margin-top: 10px;
}
</style>
