<template>

  <div class="start-node" :class="{ selected }">

    <div class="node-content">

      <v-icon icon="mdi-play-circle" color="success" size="32" />

      <div class="node-label">{{ data.label || '开始' }}</div>

    </div>

    <!-- 输出连接-->

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

.start-node {

  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);

  border: 2px solid #4caf50;

  border-radius: 50%;

  width: 80px;

  height: 80px;

  display: flex;

  align-items: center;

  justify-content: center;

  position: relative;

  transition: all 0.2s;

}



.start-node.selected {

  border-color: #2e7d32;

  box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);

}



.start-node:hover {

  transform: scale(1.05);

}



.node-content {

  display: flex;

  flex-direction: column;

  align-items: center;

  gap: 4px;

}



.node-label {

  font-size: 12px;

  font-weight: 500;

  color: #2e7d32;

}

</style>

