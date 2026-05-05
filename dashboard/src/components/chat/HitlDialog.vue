<template>
  <v-dialog :model-value="modelValue" max-width="720" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="hitl-dialog-card">
      <v-card-title class="hitl-dialog-title">
        <v-icon icon="mdi-hand-back-right-outline" size="20" color="warning" />
        <span>{{ card?.title || '人工处理' }}</span>
        <v-spacer />
        <v-btn icon size="small" variant="text" @click="emit('update:modelValue', false)">
          <v-icon icon="mdi-close" />
        </v-btn>
      </v-card-title>
      <v-card-text>
        <InteractionCardComponent
          v-if="card"
          :card="card"
          :is-dark="isDark"
          @respond="onRespond"
        />
        <div v-else class="empty-hitl">当前任务没有待处理的人工交互</div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import InteractionCardComponent from './InteractionCardComponent.vue';

defineProps<{
  modelValue: boolean;
  card?: any | null;
  isDark?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'respond', payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }): void;
}>();

function onRespond(payload: { interaction_id: string; action_key: string; field_values: Record<string, any> }) {
  emit('respond', payload);
  emit('update:modelValue', false);
}
</script>

<style scoped>
.hitl-dialog-card {
  border-radius: 8px;
}

.hitl-dialog-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.empty-hitl {
  padding: 24px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
