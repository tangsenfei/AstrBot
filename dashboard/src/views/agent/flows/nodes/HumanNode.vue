<template>
  <div class="human-node" :class="{ selected }">
    <div class="node-header">
      <v-icon icon="mdi-account" color="#ef4444" size="18" />
      <span class="node-title">{{ data.label || '人工' }}</span>
    </div>
    <div class="node-body">
      <div class="info-item">
        <span class="label">提示信息:</span>
        <span class="value">{{ data.config?.prompt || '请确认' }}</span>
      </div>
    </div>
    <Handle type="target" :position="Position.Top" class="handle-target" />
    <Handle type="source" :position="Position.Bottom" class="handle-source" />
  </div>
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core';

defineProps<{
  data: any;
  selected: boolean;
}>();
</script>

<style scoped>
.human-node {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 2px solid #ef4444;
  border-radius: 12px;
  min-width: 160px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
}

.human-node.selected {
  border-color: #dc2626;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.3), 0 4px 16px rgba(239, 68, 68, 0.2);
}

.human-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.25);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(239, 68, 68, 0.2);
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #dc2626;
}

.node-body {
  padding: 8px 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  gap: 8px;
}

.info-item .label {
  color: #64748b;
  white-space: nowrap;
}

.info-item .value {
  color: #dc2626;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100px;
}

.handle-target {
  top: -6px;
}

.handle-source {
  bottom: -6px;
}
</style>
