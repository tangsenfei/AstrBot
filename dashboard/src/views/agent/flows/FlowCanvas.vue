<template>
  <div class="flow-canvas">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :default-viewport="{ zoom: 1, x: 0, y: 0 }"
      :min-zoom="0.1"
      :max-zoom="4"
      :snap-to-grid="true"
      :snap-grid="[16, 16]"
      :connection-mode="ConnectionMode.Loose"
      :delete-key-code="['Backspace', 'Delete']"
      :connect-on-click="false"
      :elevate-nodes-on-select="true"
      :auto-connect="false"
      fit-view-on-init
      @node-click="handleNodeClick"
      @pane-click="handlePaneClick"
      @nodes-change="handleNodesChange"
      @edges-change="handleEdgesChange"
      @connect="handleConnect"
      @dragover="handleDragOver"
      @drop="handleDrop"
      @node-drag-start="handleNodeDragStart"
      @node-drag-stop="handleNodeDragStop"
      class="vue-flow-container"
    >
      <Background :variant="BackgroundVariant.Dots" :gap="16" :size="0.8" />
      <Controls position="bottom-left" />
      <MiniMap position="bottom-right" :pannable="true" :zoomable="true" />

      <template #connection-line="connectionLineProps">
        <CustomConnectionLine v-bind="connectionLineProps" />
      </template>

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

    <div v-if="isDraggingNode" class="drag-indicator">
      <v-icon icon="mdi-cursor-move" size="16" class="mr-1" />
      拖拽中...
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { VueFlow, useVueFlow, ConnectionMode } from '@vue-flow/core';
import { Background, BackgroundVariant } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import { MiniMap } from '@vue-flow/minimap';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';
import '@vue-flow/minimap/dist/style.css';

import StartNode from './nodes/StartNode.vue';
import ListenNode from './nodes/ListenNode.vue';
import RouterNode from './nodes/RouterNode.vue';
import AndNode from './nodes/AndNode.vue';
import OrNode from './nodes/OrNode.vue';
import CrewNode from './nodes/CrewNode.vue';
import HumanNode from './nodes/HumanNode.vue';
import CustomConnectionLine from './CustomConnectionLine.vue';

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

const {
  fitView,
  zoomIn,
  zoomOut,
  project,
  addNodes,
  addEdges,
  removeNodes,
  removeEdges,
  getSelectedNodes,
  getSelectedEdges,
  findNode,
} = useVueFlow({
  id: 'flow-canvas',
});

const nodes = ref<any[]>([]);
const edges = ref<any[]>([]);
const isDraggingNode = ref(false);

watch(() => props.nodes, (newNodes) => {
  nodes.value = newNodes;
}, { immediate: true, deep: true });

watch(() => props.edges, (newEdges) => {
  edges.value = newEdges;
}, { immediate: true, deep: true });

watch(nodes, (newNodes) => {
  emit('update:nodes', newNodes);
}, { deep: true });

watch(edges, (newEdges) => {
  emit('update:edges', newEdges);
}, { deep: true });

function handleNodeClick(event: any) {
  emit('node-click', event.node);
}

function handlePaneClick() {
  emit('pane-click');
}

function handleNodesChange(changes: any[]) {
  emit('nodes-change', changes);
}

function handleEdgesChange(changes: any[]) {
  emit('edges-change', changes);
}

function handleNodeDragStart() {
  isDraggingNode.value = true;
}

function handleNodeDragStop() {
  isDraggingNode.value = false;
}

function handleConnect(params: any) {
  const sourceNode = findNode(params.source);
  const targetNode = findNode(params.target);

  if (!sourceNode || !targetNode) return;

  const duplicateEdge = edges.value.find(
    e => e.source === params.source && e.target === params.target
  );
  if (duplicateEdge) return;

  const newEdge = {
    id: `edge-${params.source}-${params.target}-${Date.now()}`,
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle: params.targetHandle,
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#6366f1', strokeWidth: 2 },
    markerEnd: {
      type: 'arrowclosed',
      color: '#6366f1',
    },
  };
  edges.value = [...edges.value, newEdge];
}

function handleDragOver(event: DragEvent) {
  event.preventDefault();
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move';
  }
}

function handleDrop(event: DragEvent) {
  event.preventDefault();

  const type = event.dataTransfer?.getData('application/vueflow');
  if (!type) return;

  const nodeLabel = event.dataTransfer?.getData('application/vueflow-label') || '';
  const nodeConfig = event.dataTransfer?.getData('application/vueflow-config');

  const { left, top } = (event.target as HTMLElement).getBoundingClientRect();
  const position = project({
    x: event.clientX - left,
    y: event.clientY - top,
  });

  position.x = Math.round(position.x / 16) * 16;
  position.y = Math.round(position.y / 16) * 16;

  const newNode = {
    id: `node-${type}-${Date.now()}`,
    type,
    position,
    data: {
      label: nodeLabel || getNodeLabel(type),
      config: nodeConfig ? JSON.parse(nodeConfig) : getDefaultConfig(type),
    },
  };

  nodes.value = [...nodes.value, newNode];
}

function getNodeLabel(type: string): string {
  const labels: Record<string, string> = {
    start: '开始',
    listen: '监听',
    router: '路由',
    and: '并行(AND)',
    or: '并行(OR)',
    crew: '团队',
    human: '人工',
  };
  return labels[type] || type;
}

function getDefaultConfig(type: string): any {
  const configs: Record<string, any> = {
    start: {},
    listen: { eventType: 'message', condition: '' },
    router: { branches: [] },
    and: {},
    or: {},
    crew: { crewName: '', inputMapping: {} },
    human: { prompt: '', options: [], timeout: 300 },
  };
  return configs[type] || {};
}

defineExpose({
  fitView,
  zoomIn,
  zoomOut,
  resetView: () => {
    fitView({ padding: 0.2 });
  },
  autoLayout: () => {
    const startNodes = nodes.value.filter(n => n.type === 'start');
    if (startNodes.length === 0) return;

    const visited = new Set<string>();
    const levels: Map<string, number> = new Map();
    const queue: { id: string; level: number }[] = [];

    startNodes.forEach(n => {
      queue.push({ id: n.id, level: 0 });
      levels.set(n.id, 0);
    });

    while (queue.length > 0) {
      const { id, level } = queue.shift()!;
      if (visited.has(id)) continue;
      visited.add(id);

      const outEdges = edges.value.filter(e => e.source === id);
      for (const edge of outEdges) {
        if (!levels.has(edge.target) || levels.get(edge.target)! < level + 1) {
          levels.set(edge.target, level + 1);
          queue.push({ id: edge.target, level: level + 1 });
        }
      }
    }

    const levelGroups = new Map<number, string[]>();
    for (const [nodeId, lvl] of levels) {
      if (!levelGroups.has(lvl)) levelGroups.set(lvl, []);
      levelGroups.get(lvl)!.push(nodeId);
    }

    const xSpacing = 220;
    const ySpacing = 120;

    for (const [lvl, nodeIds] of levelGroups) {
      const totalWidth = (nodeIds.length - 1) * xSpacing;
      nodeIds.forEach((nodeId, index) => {
        const node = nodes.value.find(n => n.id === nodeId);
        if (node) {
          node.position = {
            x: -totalWidth / 2 + index * xSpacing,
            y: lvl * ySpacing,
          };
        }
      });
    }

    nodes.value = [...nodes.value];
    setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
  },
});
</script>

<style scoped>
.flow-canvas {
  width: 100%;
  height: 100%;
  background-color: #fafbfc;
  position: relative;
}

.vue-flow-container {
  width: 100%;
  height: 100%;
}

:deep(.vue-flow__node) {
  border-radius: 12px;
  transition: box-shadow 0.2s ease, transform 0.1s ease;
}

:deep(.vue-flow__node:hover) {
  z-index: 10;
}

:deep(.vue-flow__node.selected) {
  z-index: 20;
}

:deep(.vue-flow__edge-path) {
  stroke: #6366f1;
  stroke-width: 2;
  transition: stroke 0.2s ease, stroke-width 0.2s ease;
}

:deep(.vue-flow__edge:hover .vue-flow__edge-path) {
  stroke: #4f46e5;
  stroke-width: 3;
}

:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: #4f46e5;
  stroke-width: 3;
}

:deep(.vue-flow__connection-line) {
  stroke: #6366f1;
  stroke-width: 2;
  stroke-dasharray: 5;
}

:deep(.vue-flow__handle) {
  width: 10px;
  height: 10px;
  border: 2px solid #6366f1;
  background: white;
  transition: all 0.15s ease;
}

:deep(.vue-flow__handle:hover) {
  width: 14px;
  height: 14px;
  background: #6366f1;
  border-color: #4f46e5;
}

:deep(.vue-flow__minimap) {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.vue-flow__controls) {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.drag-indicator {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(99, 102, 241, 0.9);
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  display: flex;
  align-items: center;
  z-index: 100;
  pointer-events: none;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-4px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
