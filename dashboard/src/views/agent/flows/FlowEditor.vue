<template>

  <v-dialog

    :model-value="modelValue"

    @update:model-value="$emit('update:modelValue', $event)"

    fullscreen

    scrim="black"

    class="flow-editor-dialog"

  >

    <v-card class="d-flex flex-column">

      <!-- 顶部工具-->

      <v-toolbar density="comfortable" color="surface" class="border-b">

        <v-btn icon variant="text" @click="handleBack">

          <v-icon icon="mdi-arrow-left" />

        </v-btn>

        <v-toolbar-title class="ml-2">

          {{ isEditing ? $t('agent.flows.editor.editTitle') : $t('agent.flows.editor.addTitle') }}

        </v-toolbar-title>

        <v-spacer />

        

        <!-- 流程名称 -->

        <v-text-field

          v-model="flowName"

          :placeholder="$t('agent.flows.editor.flowName')"

          variant="outlined"

          density="compact"

          hide-details

          style="max-width: 300px"

          class="mr-4"

        />

        

        <!-- 操作按钮 -->

        <v-btn

          variant="outlined"

          @click="validateFlow"

          :disabled="!flowName"

          class="mr-2"

        >

          <v-icon start icon="mdi-check-circle" />

          {{ $t('agent.flows.editor.validate') }}

        </v-btn>

        <v-btn

          variant="outlined"

          @click="simulateFlow"

          :disabled="!flowName"

          class="mr-2"

        >

          <v-icon start icon="mdi-play-circle" />

          {{ $t('agent.flows.editor.simulate') }}

        </v-btn>

        <v-btn

          color="primary"

          @click="handleSave"

          :loading="saving"

          :disabled="!flowName"

        >

          <v-icon start icon="mdi-content-save" />

          {{ $t('common.save') }}

        </v-btn>

      </v-toolbar>



      <!-- 主内容区-->

      <v-card-text class="flex-grow-1 pa-0 d-flex" style="overflow: hidden">

        <!-- 左侧节点库面-->

        <v-navigation-drawer

          v-model="showPalette"

          location="left"

          width="280"

          class="border-e"

          permanent

        >

          <NodePalette

            @drag-start="handleDragStart"

          />

        </v-navigation-drawer>



        <!-- 中间画布区域 -->

        <div class="flex-grow-1 d-flex flex-column">

          <!-- 画布工具-->

          <v-toolbar density="compact" color="surface-variant" class="border-b">

            <v-btn icon variant="text" @click="showPalette = !showPalette">

              <v-icon :icon="showPalette ? 'mdi-chevron-left' : 'mdi-chevron-right'" />

            </v-btn>

            <v-btn icon variant="text" @click="showProperties = !showProperties">

              <v-icon :icon="showProperties ? 'mdi-chevron-right' : 'mdi-chevron-left'" />

            </v-btn>

            <v-divider vertical class="mx-2" />

            <v-btn icon variant="text" @click="zoomIn">

              <v-icon icon="mdi-magnify-plus" />

            </v-btn>

            <v-btn icon variant="text" @click="zoomOut">

              <v-icon icon="mdi-magnify-minus" />

            </v-btn>

            <v-btn icon variant="text" @click="fitView">

              <v-icon icon="mdi-fit-to-screen" />

            </v-btn>

            <v-btn icon variant="text" @click="resetView">

              <v-icon icon="mdi-refresh" />

            </v-btn>

            <v-divider vertical class="mx-2" />

            <v-btn

              icon

              variant="text"

              @click="deleteSelected"

              :disabled="!hasSelection"

            >

              <v-icon icon="mdi-delete" />

            </v-btn>

            <v-spacer />

            <v-chip size="small" variant="tonal">

              {{ $t('agent.flows.editor.nodes') }}: {{ nodes.length }}

            </v-chip>

            <v-chip size="small" variant="tonal" class="ml-2">

              {{ $t('agent.flows.editor.edges') }}: {{ edges.length }}

            </v-chip>

          </v-toolbar>



          <!-- 画布 -->

          <FlowCanvas

            ref="canvasRef"

            v-model:nodes="nodes"

            v-model:edges="edges"

            @node-click="handleNodeClick"

            @pane-click="handlePaneClick"

            @nodes-change="handleNodesChange"

            @edges-change="handleEdgesChange"

          />

        </div>



        <!-- 右侧属性面-->

        <v-navigation-drawer

          v-model="showProperties"

          location="right"

          width="360"

          class="border-s"

          permanent

        >

          <PropertyPanel

            :node="selectedNode"

            @update:node="handleUpdateNode"

          />

        </v-navigation-drawer>

      </v-card-text>

    </v-card>

  </v-dialog>

</template>



<script setup lang="ts">

import { ref, watch, computed } from 'vue';

import NodePalette from './NodePalette.vue';

import FlowCanvas from './FlowCanvas.vue';

import PropertyPanel from './PropertyPanel.vue';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  modelValue: boolean;

  flow: any;

  isEditing: boolean;

}>();



const emit = defineEmits<{

  (e: 'update:modelValue', value: boolean): void;

  (e: 'save', flowData: any): void;

}>();



const { t } = useI18n();



// 状

const saving = ref(false);

const flowName = ref('');

const flowDescription = ref('');

const showPalette = ref(true);

const showProperties = ref(true);



// 画布引用

const canvasRef = ref();



// 节点和边

const nodes = ref<any[]>([]);

const edges = ref<any[]>([]);



// 选中的节

const selectedNode = ref<any>(null);



// 是否有选中

const hasSelection = computed(() => selectedNode.value !== null);



// 监听 Flow 变化

watch(() => props.flow, (newFlow) => {

  if (newFlow) {

    flowName.value = newFlow.name || '';

    flowDescription.value = newFlow.description || '';

    nodes.value = newFlow.nodes || [];

    edges.value = newFlow.edges || [];

  } else {

    resetEditor();

  }

}, { immediate: true });



// 重置编辑

function resetEditor() {

  flowName.value = '';

  flowDescription.value = '';

  nodes.value = [];

  edges.value = [];

  selectedNode.value = null;

}



// 处理拖拽开

function handleDragStart(event: DragEvent, nodeType: string) {

  if (event.dataTransfer) {

    event.dataTransfer.setData('application/vueflow', nodeType);

    event.dataTransfer.effectAllowed = 'move';

  }

}



// 处理节点点击

function handleNodeClick(node: any) {

  selectedNode.value = node;

}



// 处理画布点击

function handlePaneClick() {

  selectedNode.value = null;

}



// 处理节点变化

function handleNodesChange(changes: any[]) {

  // 可以在这里处理节点变化的逻辑

}



// 处理边变

function handleEdgesChange(changes: any[]) {

  // 可以在这里处理边变化的逻辑

}



// 更新节点

function handleUpdateNode(updatedNode: any) {

  const index = nodes.value.findIndex(n => n.id === updatedNode.id);

  if (index !== -1) {

    nodes.value[index] = { ...updatedNode };

    selectedNode.value = nodes.value[index];

  }

}



// 缩放

function zoomIn() {

  canvasRef.value?.zoomIn();

}



function zoomOut() {

  canvasRef.value?.zoomOut();

}



function fitView() {

  canvasRef.value?.fitView();

}



function resetView() {

  canvasRef.value?.resetView();

}



// 删除选中

function deleteSelected() {

  if (selectedNode.value) {

    nodes.value = nodes.value.filter(n => n.id !== selectedNode.value.id);

    edges.value = edges.value.filter(e => 

      e.source !== selectedNode.value.id && e.target !== selectedNode.value.id

    );

    selectedNode.value = null;

  }

}



// 验证流程

function validateFlow() {

  // 检查是否有开始节

  const startNodes = nodes.value.filter(n => n.type === 'start');

  if (startNodes.length === 0) {

    alert(t('agent.flows.editor.validation.noStart'));

    return;

  }

  if (startNodes.length > 1) {

    alert(t('agent.flows.editor.validation.multipleStart'));

    return;

  }



  // 检查节点连

  const nodeIds = new Set(nodes.value.map(n => n.id));

  for (const edge of edges.value) {

    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {

      alert(t('agent.flows.editor.validation.invalidEdge'));

      return;

    }

  }



  alert(t('agent.flows.editor.validation.success'));

}



// 模拟执行

function simulateFlow() {

  alert(t('agent.flows.editor.simulateHint'));

}



// 返回

function handleBack() {

  emit('update:modelValue', false);

}



// 保存

async function handleSave() {

  if (!flowName.value) {

    alert(t('agent.flows.editor.validation.nameRequired'));

    return;

  }



  saving.value = true;

  try {

    const flowData = {

      name: flowName.value,

      description: flowDescription.value,

      nodes: nodes.value,

      edges: edges.value,

      enabled: true,

    };

    await emit('save', flowData);

  } finally {

    saving.value = false;

  }

}

</script>



<style scoped>

.flow-editor-dialog {

  z-index: 1000;

}



.flow-editor-dialog :deep(.v-overlay__content) {

  max-width: 100%;

  max-height: 100%;

}

</style>

