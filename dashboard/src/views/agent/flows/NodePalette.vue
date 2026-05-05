<template>
  <v-card flat class="h-100 d-flex flex-column">
    <v-card-title class="pa-4 border-b">
      <v-icon icon="mdi-shape" class="mr-2" />
      {{ $t('agent.flows.palette.title') }}
    </v-card-title>

    <v-card-text class="pb-2">
      <v-text-field
        v-model="searchQuery"
        :placeholder="$t('agent.flows.palette.search')"
        prepend-inner-icon="mdi-magnify"
        variant="outlined"
        density="compact"
        hide-details
        clearable
      />
    </v-card-text>

    <v-card-text class="flex-grow-1 overflow-y-auto pa-2">
      <v-expansion-panels v-model="expandedPanels" multiple>
        <v-expansion-panel value="start">
          <v-expansion-panel-title>
            <v-icon icon="mdi-play-circle" color="success" class="mr-2" />
            {{ $t('agent.flows.palette.categories.start') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredStartNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="listen">
          <v-expansion-panel-title>
            <v-icon icon="mdi-ear-hearing" color="info" class="mr-2" />
            {{ $t('agent.flows.palette.categories.listen') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredListenNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="router">
          <v-expansion-panel-title>
            <v-icon icon="mdi-source-branch" color="warning" class="mr-2" />
            {{ $t('agent.flows.palette.categories.router') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredRouterNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="parallel">
          <v-expansion-panel-title>
            <v-icon icon="mdi-call-split" color="purple" class="mr-2" />
            {{ $t('agent.flows.palette.categories.parallel') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredParallelNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="crew">
          <v-expansion-panel-title>
            <v-icon icon="mdi-account-group" color="cyan" class="mr-2" />
            {{ $t('agent.flows.palette.categories.crew') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredCrewNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="human">
          <v-expansion-panel-title>
            <v-icon icon="mdi-account" color="error" class="mr-2" />
            {{ $t('agent.flows.palette.categories.human') }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredHumanNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <v-expansion-panel value="work">
          <v-expansion-panel-title>
            <v-icon icon="mdi-briefcase-outline" color="primary" class="mr-2" />
            Work
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredWorkNodes"
              :key="node.type"
              class="node-item mb-2"
              draggable="true"
              @dragstart="handleDragStart($event, node)"
              @dragend="handleDragEnd"
            >
              <div class="node-card" :style="{ borderLeftColor: node.colorHex }">
                <v-icon :icon="node.icon" :color="node.color" class="mr-2" size="20" />
                <div class="flex-grow-1">
                  <div class="text-subtitle-2 font-weight-medium">{{ node.label }}</div>
                  <div class="text-caption text-grey">{{ node.description }}</div>
                </div>
                <v-icon icon="mdi-drag" size="16" color="grey-lighten-1" />
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>

    <v-card-text class="pt-0 pb-4">
      <v-alert type="info" variant="tonal" density="compact">
        {{ $t('agent.flows.palette.dragHint') }}
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';

const emit = defineEmits<{
  (e: 'drag-start', event: DragEvent, nodeType: string): void;
}>();

const { t } = useI18n();

const searchQuery = ref('');
const expandedPanels = ref(['start', 'listen', 'router', 'parallel', 'crew', 'human', 'work']);

const startNodes = computed(() => [
  { type: 'start', label: t('agent.flows.palette.nodes.start.label'), description: t('agent.flows.palette.nodes.start.description'), icon: 'mdi-play-circle', color: 'success', colorHex: '#4caf50' },
]);

const listenNodes = computed(() => [
  { type: 'listen', label: t('agent.flows.palette.nodes.listen.label'), description: t('agent.flows.palette.nodes.listen.description'), icon: 'mdi-ear-hearing', color: 'info', colorHex: '#3b82f6' },
]);

const routerNodes = computed(() => [
  { type: 'router', label: t('agent.flows.palette.nodes.router.label'), description: t('agent.flows.palette.nodes.router.description'), icon: 'mdi-source-branch', color: 'warning', colorHex: '#f59e0b' },
]);

const parallelNodes = computed(() => [
  { type: 'and', label: t('agent.flows.palette.nodes.and.label'), description: t('agent.flows.palette.nodes.and.description'), icon: 'mdi-set-center', color: 'purple', colorHex: '#8b5cf6' },
  { type: 'or', label: t('agent.flows.palette.nodes.or.label'), description: t('agent.flows.palette.nodes.or.description'), icon: 'mdi-set-all', color: 'purple', colorHex: '#a855f7' },
]);

const crewNodes = computed(() => [
  { type: 'crew', label: t('agent.flows.palette.nodes.crew.label'), description: t('agent.flows.palette.nodes.crew.description'), icon: 'mdi-account-group', color: 'cyan', colorHex: '#06b6d4' },
]);

const humanNodes = computed(() => [
  { type: 'human', label: t('agent.flows.palette.nodes.human.label'), description: t('agent.flows.palette.nodes.human.description'), icon: 'mdi-account', color: 'error', colorHex: '#ef4444' },
]);

const workNodes = computed(() => [
  { type: 'agent_task', label: 'Agent 任务', description: '配置单 Agent、团队或任务助手分配执行', icon: 'mdi-account-cog-outline', color: 'primary', colorHex: '#2196f3' },
  { type: 'sub_flow', label: '子流程', description: '引用其他流程作为子流程执行', icon: 'mdi-subdirectory-arrow-right', color: 'indigo', colorHex: '#4f46e5' },
  { type: 'hitl', label: 'HITL 交互', description: '选择人工确认/补充/审批模板', icon: 'mdi-account-question-outline', color: 'warning', colorHex: '#f59e0b' },
  { type: 'review', label: '审查', description: '配置审查 Agent 和返工策略', icon: 'mdi-clipboard-check-outline', color: 'teal', colorHex: '#14b8a6' },
  { type: 'deliverable', label: '交付物', description: '整理最终交付文件或交付记录', icon: 'mdi-package-variant-closed', color: 'success', colorHex: '#22c55e' },
]);

function filterNodes(nodes: any[]) {
  if (!searchQuery.value) return nodes;
  const query = searchQuery.value.toLowerCase();
  return nodes.filter(node =>
    node.label.toLowerCase().includes(query) || node.description.toLowerCase().includes(query)
  );
}

const filteredStartNodes = computed(() => filterNodes(startNodes.value));
const filteredListenNodes = computed(() => filterNodes(listenNodes.value));
const filteredRouterNodes = computed(() => filterNodes(routerNodes.value));
const filteredParallelNodes = computed(() => filterNodes(parallelNodes.value));
const filteredCrewNodes = computed(() => filterNodes(crewNodes.value));
const filteredHumanNodes = computed(() => filterNodes(humanNodes.value));
const filteredWorkNodes = computed(() => filterNodes(workNodes.value));

function handleDragStart(event: DragEvent, node: any) {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', node.type);
    event.dataTransfer.setData('application/vueflow-label', node.label);
    event.dataTransfer.effectAllowed = 'move';

    const ghost = document.createElement('div');
    ghost.className = 'drag-ghost';
    ghost.innerHTML = `<span style="color:${node.colorHex}">●</span> ${node.label}`;
    ghost.style.cssText = `
      position: absolute; top: -1000px; left: -1000px;
      padding: 6px 12px; background: white; border: 2px solid ${node.colorHex};
      border-radius: 8px; font-size: 13px; white-space: nowrap;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    document.body.appendChild(ghost);
    event.dataTransfer.setDragImage(ghost, 12, 12);
    setTimeout(() => document.body.removeChild(ghost), 0);
  }
  emit('drag-start', event, node.type);
}

function handleDragEnd() {}
</script>

<style scoped>
.node-item {
  cursor: grab;
  transition: transform 0.15s ease;
}

.node-item:active {
  cursor: grabbing;
  transform: scale(0.97);
}

.node-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid;
  border-radius: 8px;
  background: white;
  transition: all 0.2s ease;
}

.node-card:hover {
  border-color: #94a3b8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transform: translateX(2px);
}
</style>
