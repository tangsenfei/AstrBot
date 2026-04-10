<template>

  <div class="router-node" :class="{ selected }">

    <div class="node-header">

      <v-icon icon="mdi-source-branch" color="warning" size="20" />

      <span class="node-title">{{ data.label || '路由' }}</span>

    </div>

    <div class="node-body">

      <div class="info-item">

        <span class="label">分支数量:</span>

        <span class="value">{{ data.config?.branches?.length || 0 }}</span>

      </div>

    </div>

    <!-- 连接-->

    <Handle type="target" :position="Position.Top" />

    <Handle type="source" :position="Position.Bottom" id="default" />

    <Handle

      v-for="(branch, index) in data.config?.branches"

      :key="index"

      type="source"

      :position="Position.Bottom"

      :id="`branch-${index}`"

      :style="{ left: `${20 + index * 30}%` }"

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

  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);

  border: 2px solid #ff9800;

  border-radius: 8px;

  min-width: 150px;

  transform: rotate(0deg);

  transition: all 0.2s;

}



.router-node.selected {

  border-color: #e65100;

  box-shadow: 0 0 0 3px rgba(255, 152, 0, 0.3);

}



.router-node:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.node-header {

  display: flex;

  align-items: center;

  gap: 8px;

  padding: 8px 12px;

  border-bottom: 1px solid rgba(255, 152, 0, 0.2);

}



.node-title {

  font-size: 14px;

  font-weight: 600;

  color: #e65100;

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

  color: #e65100;

  font-weight: 500;

}

</style>

