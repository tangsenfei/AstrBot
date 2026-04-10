<template>

  <div class="human-node" :class="{ selected }">

    <div class="node-header">

      <v-icon icon="mdi-account" color="error" size="20" />

      <span class="node-title">{{ data.label || '人工' }}</span>

    </div>

    <div class="node-body">

      <div class="info-item">

        <span class="label">超时:</span>

        <span class="value">{{ data.config?.timeout || 300 }}</span>

      </div>

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

.human-node {

  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);

  border: 2px solid #f44336;

  border-radius: 8px;

  min-width: 150px;

  transition: all 0.2s;

}



.human-node.selected {

  border-color: #c62828;

  box-shadow: 0 0 0 3px rgba(244, 67, 54, 0.3);

}



.human-node:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.node-header {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 12px;

  border-bottom: 1px solid rgba(244, 67, 54, 0.2);

}



.node-title {

  font-size: 14px;

  font-weight: 600;

  color: #c62828;

}



.node-body {

  padding: 8px 12px;

}



.info-item {

  display: flex;

  justify-content: space-between;

  font-size: 12px;

}



.info-item .label {

  color: #666;

}



.info-item .value {

  color: #c62828;

  font-weight: 500;

}

</style>

