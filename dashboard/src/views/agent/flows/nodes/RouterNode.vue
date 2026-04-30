<template>
  <div class="router-node" :class="{ selected }">
    <div class="node-header">
      <v-icon icon="mdi-source-branch" color="#f59e0b" size="18" />
      <span class="node-title">{{ data.label || '路由' }}</span>
    </div>
    <div class="node-body">
      <div class="info-item">
        <span class="label">分支数量:</span>
        <span class="value">{{ data.config?.branches?.length || 0 }}</span>
      </div>
    </div>
    <Handle type="target" :position="Position.Top" class="handle-target" />
    <Handle type="source" :position="Position.Bottom" class="handle-source" id="default" />
    <Handle
      v-for="(branch, index) in data.config?.branches"
      :key="index"
      type="source"
      :position="Position.Bottom"
      :id="`branch-${index}`"
      :style="{ left: `${20 + index * 30}%` }"
      class="handle-source"
    />
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
.router-node {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 2px solid #f59e0b;
  border-radius: 12px;
  min-width: 160px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.15);
}

.router-node.selected {
  border-color: #d97706;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3), 0 4px 16px rgba(245, 158, 11, 0.2);
}

.router-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(245, 158, 11, 0.25);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(245, 158, 11, 0.2);
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #d97706;
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
  color: #d97706;
  font-weight: 500;
}

.handle-target {
  top: -6px;
}

.handle-source {
  bottom: -6px;
}
</style>
