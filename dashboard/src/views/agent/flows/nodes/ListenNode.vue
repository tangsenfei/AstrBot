<template>

  <div class="listen-node" :class="{ selected }">

    <div class="node-header">

      <v-icon icon="mdi-ear-hearing" color="info" size="20" />

      <span class="node-title">{{ data.label || '监听' }}</span>

    </div>

    <div class="node-body">

      <div class="info-item">

        <span class="label">事件类型:</span>

        <span class="value">{{ data.config?.eventType || 'message' }}</span>

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

.listen-node {

  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);

  border: 2px solid #2196f3;

  border-radius: 8px;

  min-width: 150px;

  transition: all 0.2s;

}



.listen-node.selected {

  border-color: #1565c0;

  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.3);

}



.listen-node:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.node-header {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 12px;

  border-bottom: 1px solid rgba(33, 150, 243, 0.2);

}



.node-title {

  font-size: 14px;

  font-weight: 600;

  color: #1565c0;

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

  color: #1565c0;

  font-weight: 500;

}

</style>

