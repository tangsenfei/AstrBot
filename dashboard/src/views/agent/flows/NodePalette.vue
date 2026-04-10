<template>

  <v-card flat class="h-100 d-flex flex-column">

    <!-- 标题 -->

    <v-card-title class="pa-4 border-b">

      <v-icon icon="mdi-shape" class="mr-2" />

      {{ $t('agent.flows.palette.title') }}

    </v-card-title>



    <!-- 搜索 -->

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



    <!-- 节点列表 -->

    <v-card-text class="flex-grow-1 overflow-y-auto pa-2">

      <v-expansion-panels v-model="expandedPanels" multiple>

        <!-- 开始节-->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>



        <!-- 监听节点 -->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>



        <!-- 路由节点 -->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>



        <!-- 并行节点 -->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>



        <!-- Crew 节点 -->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>



        <!-- 人工节点 -->

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

              @dragstart="handleDragStart($event, node.type)"

            >

              <v-card hover class="pa-3">

                <div class="d-flex align-center">

                  <v-icon :icon="node.icon" :color="node.color" class="mr-2" />

                  <div>

                    <div class="text-subtitle-2">{{ node.label }}</div>

                    <div class="text-caption text-grey">{{ node.description }}</div>

                  </div>

                </div>

              </v-card>

            </div>

          </v-expansion-panel-text>

        </v-expansion-panel>

      </v-expansion-panels>

    </v-card-text>



    <!-- 提示信息 -->

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



// 搜索

const searchQuery = ref('');

const expandedPanels = ref(['start', 'listen', 'router', 'parallel', 'crew', 'human']);



// 节点定义

const startNodes = computed(() => [

  {

    type: 'start',

    label: t('agent.flows.palette.nodes.start.label'),

    description: t('agent.flows.palette.nodes.start.description'),

    icon: 'mdi-play-circle',

    color: 'success',

  },

]);



const listenNodes = computed(() => [

  {

    type: 'listen',

    label: t('agent.flows.palette.nodes.listen.label'),

    description: t('agent.flows.palette.nodes.listen.description'),

    icon: 'mdi-ear-hearing',

    color: 'info',

  },

]);



const routerNodes = computed(() => [

  {

    type: 'router',

    label: t('agent.flows.palette.nodes.router.label'),

    description: t('agent.flows.palette.nodes.router.description'),

    icon: 'mdi-source-branch',

    color: 'warning',

  },

]);



const parallelNodes = computed(() => [

  {

    type: 'and',

    label: t('agent.flows.palette.nodes.and.label'),

    description: t('agent.flows.palette.nodes.and.description'),

    icon: 'mdi-set-center',

    color: 'purple',

  },

  {

    type: 'or',

    label: t('agent.flows.palette.nodes.or.label'),

    description: t('agent.flows.palette.nodes.or.description'),

    icon: 'mdi-set-all',

    color: 'purple',

  },

]);



const crewNodes = computed(() => [

  {

    type: 'crew',

    label: t('agent.flows.palette.nodes.crew.label'),

    description: t('agent.flows.palette.nodes.crew.description'),

    icon: 'mdi-account-group',

    color: 'cyan',

  },

]);



const humanNodes = computed(() => [

  {

    type: 'human',

    label: t('agent.flows.palette.nodes.human.label'),

    description: t('agent.flows.palette.nodes.human.description'),

    icon: 'mdi-account',

    color: 'error',

  },

]);



// 过滤节点

function filterNodes(nodes: any[]) {

  if (!searchQuery.value) return nodes;

  const query = searchQuery.value.toLowerCase();

  return nodes.filter(node =>

    node.label.toLowerCase().includes(query) ||

    node.description.toLowerCase().includes(query)

  );

}



const filteredStartNodes = computed(() => filterNodes(startNodes.value));

const filteredListenNodes = computed(() => filterNodes(listenNodes.value));

const filteredRouterNodes = computed(() => filterNodes(routerNodes.value));

const filteredParallelNodes = computed(() => filterNodes(parallelNodes.value));

const filteredCrewNodes = computed(() => filterNodes(crewNodes.value));

const filteredHumanNodes = computed(() => filterNodes(humanNodes.value));



// 处理拖拽开

function handleDragStart(event: DragEvent, nodeType: string) {

  if (event.dataTransfer) {

    event.dataTransfer.setData('application/vueflow', nodeType);

    event.dataTransfer.effectAllowed = 'move';

  }

  emit('drag-start', event, nodeType);

}

</script>



<style scoped>

.node-item {

  cursor: grab;

}



.node-item:active {

  cursor: grabbing;

}



.node-item :deep(.v-card) {

  transition: transform 0.1s, box-shadow 0.1s;

}



.node-item :deep(.v-card:hover) {

  transform: translateX(4px);

  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

}

</style>

