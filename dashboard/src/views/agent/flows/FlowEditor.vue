<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    fullscreen
    scrim="black"
    class="flow-editor-dialog"
  >
    <v-card class="d-flex flex-column">
      <v-toolbar density="comfortable" color="surface" class="border-b">
        <v-btn icon variant="text" @click="handleBack">
          <v-icon icon="mdi-arrow-left" />
        </v-btn>
        <v-toolbar-title class="ml-2">
          {{ isEditing ? $t('agent.flows.editor.editTitle') : $t('agent.flows.editor.addTitle') }}
        </v-toolbar-title>
        <v-spacer />

        <v-text-field
          v-model="flowName"
          :placeholder="$t('agent.flows.editor.flowName')"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 300px"
          class="mr-4"
        />

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

      <v-card-text class="flex-grow-1 pa-0 d-flex" style="overflow: hidden">
        <div
          class="node-palette-container border-e"
          style="width: 280px; min-width: 280px; overflow-y: auto; background: rgb(var(--v-theme-surface));"
        >
          <NodePalette @drag-start="handleDragStart" />
        </div>

        <div class="flex-grow-1 d-flex flex-column">
          <v-toolbar density="compact" color="surface-variant" class="border-b">
            <v-btn icon variant="text" @click="zoomIn" :title="$t('agent.flows.editor.zoomIn')">
              <v-icon icon="mdi-magnify-plus" />
            </v-btn>
            <v-btn icon variant="text" @click="zoomOut" :title="$t('agent.flows.editor.zoomOut')">
              <v-icon icon="mdi-magnify-minus" />
            </v-btn>
            <v-btn icon variant="text" @click="fitView" :title="$t('agent.flows.editor.fitView')">
              <v-icon icon="mdi-fit-to-screen" />
            </v-btn>
            <v-btn icon variant="text" @click="resetView" :title="$t('agent.flows.editor.resetView')">
              <v-icon icon="mdi-refresh" />
            </v-btn>
            <v-divider vertical class="mx-2" />
            <v-btn icon variant="text" @click="autoLayout" color="primary" :title="$t('agent.flows.editor.autoLayout')">
              <v-icon icon="mdi-sitemap-outline" />
            </v-btn>
            <v-divider vertical class="mx-2" />
            <v-btn
              icon
              variant="text"
              @click="deleteSelected"
              :disabled="!hasSelection"
              color="error"
            >
              <v-icon icon="mdi-delete" />
            </v-btn>
            <v-spacer />
            <v-chip size="small" variant="tonal" color="primary">
              {{ $t('agent.flows.editor.nodes') }}: {{ nodes.length }}
            </v-chip>
            <v-chip size="small" variant="tonal" color="secondary" class="ml-2">
              {{ $t('agent.flows.editor.edges') }}: {{ edges.length }}
            </v-chip>
          </v-toolbar>

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
      </v-card-text>

      <v-dialog v-model="showPropertyDialog" max-width="520" persistent>
        <v-card v-if="selectedNode">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-cog" class="mr-2" color="primary" />
            {{ selectedNode.data?.label || selectedNode.type }} - 属性配置
            <v-spacer />
            <v-btn icon variant="text" @click="closePropertyDialog">
              <v-icon icon="mdi-close" />
            </v-btn>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4" style="max-height: 60vh; overflow-y: auto;">
            <PropertyPanel
              :node="selectedNode"
              @update:node="handleUpdateNode"
            />
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-4">
            <v-spacer />
            <v-btn variant="outlined" @click="closePropertyDialog">
              {{ $t('common.close') }}
            </v-btn>
            <v-btn color="primary" @click="applyPropertyAndClose">
              <v-icon start icon="mdi-check" />
              确认
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
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

const saving = ref(false);
const flowName = ref('');
const flowDescription = ref('');
const showPropertyDialog = ref(false);

const canvasRef = ref();
const nodes = ref<any[]>([]);
const edges = ref<any[]>([]);
const selectedNode = ref<any>(null);

const hasSelection = computed(() => selectedNode.value !== null);

watch(() => props.flow, (newFlow) => {
  if (newFlow) {
    flowName.value = newFlow.name || '';
    flowDescription.value = newFlow.description || '';
    nodes.value = (newFlow.nodes || []).map((n: any) => ({
      ...n,
      id: n.id || `node-${n.type}-${Date.now()}`,
      type: n.type,
      position: n.position || { x: 0, y: 0 },
      data: n.data || { label: n.name || n.type, config: n.config || {} },
    }));
    edges.value = (newFlow.edges || []).map((e: any) => ({
      ...e,
      id: e.id || `edge-${e.source}-${e.target}`,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#6366f1', strokeWidth: 2 },
      markerEnd: { type: 'arrowclosed', color: '#6366f1' },
    }));
  } else {
    resetEditor();
  }
}, { immediate: true });

function resetEditor() {
  flowName.value = '';
  flowDescription.value = '';
  nodes.value = [];
  edges.value = [];
  selectedNode.value = null;
  showPropertyDialog.value = false;
}

function handleDragStart(event: DragEvent, nodeType: string) {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  }
}

function handleNodeClick(node: any) {
  selectedNode.value = node;
  showPropertyDialog.value = true;
}

function handlePaneClick() {
  selectedNode.value = null;
  showPropertyDialog.value = false;
}

function handleNodesChange(changes: any[]) {}

function handleEdgesChange(changes: any[]) {}

function handleUpdateNode(updatedNode: any) {
  const index = nodes.value.findIndex(n => n.id === updatedNode.id);
  if (index !== -1) {
    nodes.value[index] = { ...updatedNode };
    selectedNode.value = nodes.value[index];
  }
}

function closePropertyDialog() {
  showPropertyDialog.value = false;
}

function applyPropertyAndClose() {
  showPropertyDialog.value = false;
}

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

function autoLayout() {
  canvasRef.value?.autoLayout();
}

function deleteSelected() {
  if (selectedNode.value) {
    nodes.value = nodes.value.filter(n => n.id !== selectedNode.value.id);
    edges.value = edges.value.filter(e =>
      e.source !== selectedNode.value.id && e.target !== selectedNode.value.id
    );
    selectedNode.value = null;
    showPropertyDialog.value = false;
  }
}

function validateFlow() {
  const startNodes = nodes.value.filter(n => n.type === 'start');
  if (startNodes.length === 0) {
    alert(t('agent.flows.editor.validation.noStart'));
    return;
  }
  if (startNodes.length > 1) {
    alert(t('agent.flows.editor.validation.multipleStart'));
    return;
  }

  const nodeIds = new Set(nodes.value.map(n => n.id));
  for (const edge of edges.value) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      alert(t('agent.flows.editor.validation.invalidEdge'));
      return;
    }
  }

  alert(t('agent.flows.editor.validation.success'));
}

function simulateFlow() {
  alert(t('agent.flows.editor.simulateHint'));
}

function handleBack() {
  emit('update:modelValue', false);
}

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
      nodes: nodes.value.map(n => ({
        id: n.id,
        name: n.data?.label || n.type,
        type: n.type,
        config: n.data?.config || {},
        position: n.position || { x: 0, y: 0 },
      })),
      edges: edges.value.map(e => ({
        id: e.id,
        source: e.source,
        target: e.target,
        condition: e.condition || e.data?.condition || {},
      })),
      enabled: true,
    };
    emit('save', flowData);
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

.node-palette-container {
  flex-shrink: 0;
}
</style>
