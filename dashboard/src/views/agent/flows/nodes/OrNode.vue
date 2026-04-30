<template>
  <div class="or-node" :class="{ selected }">
    <div class="node-header">
      <v-icon icon="mdi-set-all" color="#a855f7" size="18" />
      <span class="node-title">{{ data.label || '并行(OR)' }}</span>
    </div>
    <div class="node-body">
      <div class="hint">任一分支完成后继续</div>
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
.or-node {
  background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%);
  border: 2px solid #a855f7;
  border-radius: 12px;
  min-width: 160px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(168, 85, 247, 0.15);
}

.or-node.selected {
  border-color: #9333ea;
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.3), 0 4px 16px rgba(168, 85, 247, 0.2);
}

.or-node:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(168, 85, 247, 0.25);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(168, 85, 247, 0.2);
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #9333ea;
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
