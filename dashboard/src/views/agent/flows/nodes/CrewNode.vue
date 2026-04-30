<template>
  <div class="crew-node" :class="{ selected }">
    <div class="node-header">
      <v-icon icon="mdi-account-group" color="#0891b2" size="18" />
      <span class="node-title">{{ data.label || '团队' }}</span>
    </div>
    <div class="node-body">
      <div class="info-item">
        <span class="label">团队:</span>
        <span class="value">{{ data.config?.crewName || '未选择' }}</span>
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
.crew-node {
  background: linear-gradient(135deg, #ecfeff 0%, #cffafe 100%);
  border: 2px solid #06b6d4;
  border-radius: 12px;
  min-width: 160px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.15);
}

.crew-node.selected {
  border-color: #0891b2;
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.3), 0 4px 16px rgba(6, 182, 212, 0.2);
}

.crew-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(6, 182, 212, 0.25);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(6, 182, 212, 0.2);
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #0891b2;
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
  color: #0891b2;
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
