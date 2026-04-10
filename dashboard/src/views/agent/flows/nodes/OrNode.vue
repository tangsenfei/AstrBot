<template>

  <div class="or-node" :class="{ selected }">

    <div class="node-header">

      <v-icon icon="mdi-set-all" color="purple" size="20" />

      <span class="node-title">{{ data.label || '并行(OR)' }}</span>

    </div>

    <div class="node-body">

      <div class="hint">任一分支完成后继续</div>

    </div>

    <!-- 连接-->

    <Handle type="target" :position="Position.Top" />

    <Handle type="source" :position="Position.Bottom" />

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

  background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);

  border: 2px solid #ab47bc;

  border-radius: 8px;

  min-width: 150px;

  transition: all 0.2s;

}



.or-node.selected {

  border-color: #7b1fa2;

  box-shadow: 0 0 0 3px rgba(171, 71, 188, 0.3);

}



.or-node:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.node-header {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 12px;

  border-bottom: 1px solid rgba(171, 71, 188, 0.2);

}



.node-title {

  font-size: 14px;

  font-weight: 600;

  color: #7b1fa2;

}



.node-body {

  padding: 8px 12px;

}



.hint {

  font-size: 11px;

  color: #666;

  text-align: center;

}

</style>

