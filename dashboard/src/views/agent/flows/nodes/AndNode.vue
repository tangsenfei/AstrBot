<template>
  <div class="and-node" :class="{ selected }">
    <div class="node-header">
      <v-icon icon="mdi-set-center" color="#8b5cf6" size="18" />
      <span class="node-title">{{ data.label || '并行(AND)' }}</span>
    </div>
    <div class="node-body">
      <div class="hint">所有分支都完成后继续</div>
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
.and-node {
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
  border: 2px solid #8b5cf6;
  border-radius: 12px;
  min-width: 160px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(139, 92, 246, 0.15);
}

.and-node.selected {
  border-color: #7c3aed;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.3), 0 4px 16px rgba(139, 92, 246, 0.2);
}

.and-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(139, 92, 246, 0.25);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(139, 92, 246, 0.2);
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #7c3aed;
}

.node-body {
  padding: 8px 12px;
}

.hint {
  font-size: 11px;
  color: #64748b;
  text-align: center;
}

.handle-target {
  top: -6px;
}

.handle-source {
  bottom: -6px;
}
</style>
