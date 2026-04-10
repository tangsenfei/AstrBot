<template>


  <div class="flow-canvas">


    <VueFlow


      v-model:nodes="nodes"


      v-model:edges="edges"


      :default-viewport="{ zoom: 1, x: 0, y: 0 }"


      :min-zoom="0.2"


      :max-zoom="4"


      :snap-to-grid="true"


      :snap-grid="[20, 20]"


      :connection-mode="ConnectionMode.Loose"


      :delete-key-code="['Backspace', 'Delete']"


      fit-view-on-init


      @node-click="handleNodeClick"


      @pane-click="handlePaneClick"


      @nodes-change="handleNodesChange"


      @edges-change="handleEdgesChange"


      @connect="handleConnect"


      @dragover="handleDragOver"


      @drop="handleDrop"


      class="vue-flow-container"


    >


      <!-- 背景 -->


      <Background :variant="BackgroundVariant.Dots" :gap="20" :size="1" />





      <!-- 控制-->


      <Controls />





      <!-- 小地-->


      <MiniMap />





      <!-- 自定义节-->


      <template #node-start="nodeProps">


        <StartNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-listen="nodeProps">


        <ListenNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-router="nodeProps">


        <RouterNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-and="nodeProps">


        <AndNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-or="nodeProps">


        <OrNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-crew="nodeProps">


        <CrewNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


      <template #node-human="nodeProps">


        <HumanNode :data="nodeProps.data" :selected="nodeProps.selected" />


      </template>


    </VueFlow>


  </div>


</template>





<script setup lang="ts">


import { ref, watch, markRaw } from 'vue';


import { VueFlow, useVueFlow, ConnectionMode } from '@vue-flow/core';


import { Background, BackgroundVariant } from '@vue-flow/background';


import { Controls } from '@vue-flow/controls';


import { MiniMap } from '@vue-flow/minimap';


import '@vue-flow/core/dist/style.css';


import '@vue-flow/core/dist/theme-default.css';


import '@vue-flow/controls/dist/style.css';


import '@vue-flow/minimap/dist/style.css';





// 自定义节点组


import StartNode from './nodes/StartNode.vue';


import ListenNode from './nodes/ListenNode.vue';


import RouterNode from './nodes/RouterNode.vue';


import AndNode from './nodes/AndNode.vue';


import OrNode from './nodes/OrNode.vue';


import CrewNode from './nodes/CrewNode.vue';


import HumanNode from './nodes/HumanNode.vue';





const props = defineProps<{


  nodes: any[];


  edges: any[];


}>();





const emit = defineEmits<{


  (e: 'update:nodes', nodes: any[]): void;


  (e: 'update:edges', edges: any[]): void;


  (e: 'node-click', node: any): void;


  (e: 'pane-click'): void;


  (e: 'nodes-change', changes: any[]): void;


  (e: 'edges-change', changes: any[]): void;


}>();





// Vue Flow 实例


const { fitView, zoomIn, zoomOut, project, addNodes } = useVueFlow();





// 本地节点和边


const nodes = ref<any[]>([]);


const edges = ref<any[]>([]);





// 监听 props 变化


watch(() => props.nodes, (newNodes) => {


  nodes.value = newNodes;


}, { immediate: true, deep: true });





watch(() => props.edges, (newEdges) => {


  edges.value = newEdges;


}, { immediate: true, deep: true });





// 监听本地变化并同步到父组


watch(nodes, (newNodes) => {


  emit('update:nodes', newNodes);


}, { deep: true });





watch(edges, (newEdges) => {


  emit('update:edges', newEdges);


}, { deep: true });





// 处理节点点击


function handleNodeClick(event: any) {


  emit('node-click', event.node);


}





// 处理画布点击


function handlePaneClick() {


  emit('pane-click');


}





// 处理节点变化


function handleNodesChange(changes: any[]) {


  emit('nodes-change', changes);


}





// 处理边变


function handleEdgesChange(changes: any[]) {


  emit('edges-change', changes);


}





// 处理连接


function handleConnect(params: any) {


  const newEdge = {


    id: `edge-${Date.now()}`,


    source: params.source,


    target: params.target,


    sourceHandle: params.sourceHandle,


    targetHandle: params.targetHandle,


    type: 'smoothstep',


    animated: true,


  };


  edges.value = [...edges.value, newEdge];


}





// 处理拖拽悬停


function handleDragOver(event: DragEvent) {


  event.preventDefault();


  if (event.dataTransfer) {


    event.dataTransfer.dropEffect = 'move';


  }


}





// 处理放置


function handleDrop(event: DragEvent) {


  event.preventDefault();





  const type = event.dataTransfer?.getData('application/vueflow');


  if (!type) return;





  const { left, top } = (event.target as HTMLElement).getBoundingClientRect();


  const position = project({


    x: event.clientX - left,


    y: event.clientY - top,


  });





  const newNode = {


    id: `node-${Date.now()}`,


    type,


    position,


    data: {


      label: getNodeLabel(type),


      config: getDefaultConfig(type),


    },


  };





  nodes.value = [...nodes.value, newNode];


}





// 获取节点标签


function getNodeLabel(type: string): string {


  const labels: Record<string, string> = {


    start: '开始',


    listen: '监听',


    router: '路由',


    and: '并行(AND)',


    or: '并行(OR)',


    crew: 'Crew',


    human: '人工',


  };


  return labels[type] || type;


}





// 获取默认配置


function getDefaultConfig(type: string): any {


  const configs: Record<string, any> = {


    start: {},


    listen: {


      eventType: 'message',


      condition: '',


    },


    router: {


      branches: [],


    },


    and: {},


    or: {},


    crew: {


      crewName: '',


      inputMapping: {},


    },


    human: {


      prompt: '',


      options: [],


      timeout: 300,


    },


  };


  return configs[type] || {};


}





// 暴露方法给父组件


defineExpose({


  fitView,


  zoomIn,


  zoomOut,


  resetView: () => {


    fitView();


  },


});


</script>





<style scoped>


.flow-canvas {


  width: 100%;


  height: 100%;


  background-color: #f5f5f5;


}





.vue-flow-container {


  width: 100%;


  height: 100%;


}





/* Vue Flow 自定义样式 */


:deep(.vue-flow__node) {


  border-radius: 8px;


  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);


}





:deep(.vue-flow__edge-path) {


  stroke-width: 2;


}





:deep(.vue-flow__edge.selected .vue-flow__edge-path) {


  stroke: #1976d2;


  stroke-width: 3;


}


</style>


