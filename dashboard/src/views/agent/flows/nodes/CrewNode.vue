<template>

  <div class="crew-node" :class="{ selected }">

    <div class="node-header">

      <v-icon icon="mdi-account-group" color="cyan" size="20" />

      <span class="node-title">{{ data.label || 'Crew' }}</span>

    </div>

    <div class="node-body">

      <div class="info-item">

        <span class="label">团队:</span>

        <span class="value">{{ data.config?.crewName || '未选择' }}</span>

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

.crew-node {

  background: linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 100%);

  border: 2px solid #00bcd4;

  border-radius: 8px;

  min-width: 150px;

  transition: all 0.2s;

}



.crew-node.selected {

  border-color: #00838f;

  box-shadow: 0 0 0 3px rgba(0, 188, 212, 0.3);

}



.crew-node:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.node-header {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 12px;

  border-bottom: 1px solid rgba(0, 188, 212, 0.2);

}



.node-title {

  font-size: 14px;

  font-weight: 600;

  color: #00838f;

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

  color: #00838f;

  font-weight: 500;

}

</style>

