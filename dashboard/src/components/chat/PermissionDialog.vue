<template>
  <v-dialog :model-value="!!request" max-width="560" persistent>
    <v-card>
      <v-card-title>{{ request?.title || 'CLI Agent 权限请求' }}</v-card-title>
      <v-card-text>
        <p class="permission-body">{{ request?.body || 'Agent 请求执行需要授权的操作。' }}</p>
        <pre v-if="payloadText" class="permission-payload">{{ payloadText }}</pre>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="$emit('respond', 'deny')">拒绝</v-btn>
        <v-btn variant="tonal" color="primary" @click="$emit('respond', 'allow_always')">
          始终允许
        </v-btn>
        <v-btn color="primary" @click="$emit('respond', 'allow')">允许</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PermissionRequest } from '@/composables/useCliAgentStream';

const props = defineProps<{ request: PermissionRequest | null }>();
defineEmits<{ respond: [decision: string] }>();

const payloadText = computed(() => {
  if (!props.request?.payload) return '';
  return JSON.stringify(props.request.payload, null, 2);
});
</script>

<style scoped>
.permission-body {
  margin: 0 0 12px;
  color: rgba(var(--v-theme-on-surface), 0.78);
}

.permission-payload {
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}
</style>
