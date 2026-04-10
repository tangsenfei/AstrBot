<template>

  <v-card flat class="h-100 d-flex flex-column">

    <!-- 标题 -->

    <v-card-title class="pa-4 border-b">

      <v-icon icon="mdi-cog" class="mr-2" />

      {{ $t('agent.flows.properties.title') }}

    </v-card-title>



    <!-- 无选中节点提示 -->

    <v-card-text v-if="!node" class="flex-grow-1 d-flex align-center justify-center">

      <div class="text-center">

        <v-icon icon="mdi-cursor-default-click" size="60" color="grey-lighten-1" class="mb-4" />

        <p class="text-grey">{{ $t('agent.flows.properties.noSelection') }}</p>

      </div>

    </v-card-text>



    <!-- 属性表-->

    <v-card-text v-else class="flex-grow-1 overflow-y-auto pa-4">

      <v-form>

        <!-- 基本信息 -->

        <div class="text-subtitle-1 font-weight-medium mb-3">

          {{ $t('agent.flows.properties.basic') }}

        </div>

        <v-text-field

          v-model="localNode.data.label"

          :label="$t('agent.flows.properties.nodeName')"

          variant="outlined"

          density="compact"

          class="mb-3"

          @update:model-value="handleUpdate"

        />



        <!-- 根据节点类型显示不同配置 -->

        <template v-if="node.type === 'start'">

          <v-alert type="info" variant="tonal" density="compact">

            {{ $t('agent.flows.properties.startHint') }}

          </v-alert>

        </template>



        <template v-else-if="node.type === 'listen'">

          <div class="text-subtitle-1 font-weight-medium mb-3 mt-4">

            {{ $t('agent.flows.properties.listenConfig') }}

          </div>

          <v-select

            v-model="localNode.data.config.eventType"

            :items="eventTypeOptions"

            :label="$t('agent.flows.properties.eventType')"

            variant="outlined"

            density="compact"

            class="mb-3"

            @update:model-value="handleUpdate"

          />

          <v-textarea

            v-model="localNode.data.config.condition"

            :label="$t('agent.flows.properties.condition')"

            :hint="$t('agent.flows.properties.conditionHint')"

            variant="outlined"

            rows="3"

            auto-grow

            class="mb-3"

            @update:model-value="handleUpdate"

          />

        </template>



        <template v-else-if="node.type === 'router'">

          <div class="text-subtitle-1 font-weight-medium mb-3 mt-4">

            {{ $t('agent.flows.properties.routerConfig') }}

          </div>

          <v-alert type="info" variant="tonal" density="compact" class="mb-3">

            {{ $t('agent.flows.properties.routerHint') }}

          </v-alert>

          <div class="mb-3">

            <div class="d-flex align-center mb-2">

              <span class="text-subtitle-2">{{ $t('agent.flows.properties.branches') }}</span>

              <v-spacer />

              <v-btn

                size="small"

                variant="text"

                color="primary"

                @click="addBranch"

              >

                <v-icon start icon="mdi-plus" />

                {{ $t('agent.flows.properties.addBranch') }}

              </v-btn>

            </div>

            <v-card

              v-for="(branch, index) in localNode.data.config.branches"

              :key="index"

              variant="outlined"

              class="mb-2 pa-3"

            >

              <div class="d-flex align-center mb-2">

                <span class="text-caption">{{ $t('agent.flows.properties.branch') }} {{ index + 1 }}</span>

                <v-spacer />

                <v-btn

                  icon

                  size="x-small"

                  variant="text"

                  color="error"

                  @click="removeBranch(index)"

                >

                  <v-icon icon="mdi-close" />

                </v-btn>

              </div>

              <v-text-field

                v-model="branch.name"

                :label="$t('agent.flows.properties.branchName')"

                variant="outlined"

                density="compact"

                class="mb-2"

                @update:model-value="handleUpdate"

              />

              <v-textarea

                v-model="branch.condition"

                :label="$t('agent.flows.properties.branchCondition')"

                variant="outlined"

                rows="2"

                auto-grow

                @update:model-value="handleUpdate"

              />

            </v-card>

          </div>

        </template>



        <template v-else-if="node.type === 'and' || node.type === 'or'">

          <v-alert type="info" variant="tonal" density="compact">

            {{ node.type === 'and' ? $t('agent.flows.properties.andHint') : $t('agent.flows.properties.orHint') }}

          </v-alert>

        </template>



        <template v-else-if="node.type === 'crew'">

          <div class="text-subtitle-1 font-weight-medium mb-3 mt-4">

            {{ $t('agent.flows.properties.crewConfig') }}

          </div>

          <v-select

            v-model="localNode.data.config.crewName"

            :items="crewOptions"

            :label="$t('agent.flows.properties.selectCrew')"

            :loading="loadingCrews"

            variant="outlined"

            density="compact"

            class="mb-3"

            @update:model-value="handleUpdate"

          />

          <v-textarea

            v-model="inputMappingText"

            :label="$t('agent.flows.properties.inputMapping')"

            :hint="$t('agent.flows.properties.inputMappingHint')"

            variant="outlined"

            rows="3"

            auto-grow

            class="mb-3"

            @update:model-value="handleInputMappingUpdate"

          />

        </template>



        <template v-else-if="node.type === 'human'">

          <div class="text-subtitle-1 font-weight-medium mb-3 mt-4">

            {{ $t('agent.flows.properties.humanConfig') }}

          </div>

          <v-textarea

            v-model="localNode.data.config.prompt"

            :label="$t('agent.flows.properties.prompt')"

            :hint="$t('agent.flows.properties.promptHint')"

            variant="outlined"

            rows="3"

            auto-grow

            class="mb-3"

            @update:model-value="handleUpdate"

          />

          <v-text-field

            v-model="optionsText"

            :label="$t('agent.flows.properties.options')"

            :hint="$t('agent.flows.properties.optionsHint')"

            variant="outlined"

            density="compact"

            class="mb-3"

            @update:model-value="handleOptionsUpdate"

          />

          <v-text-field

            v-model.number="localNode.data.config.timeout"

            :label="$t('agent.flows.properties.timeout')"

            :suffix="$t('agent.flows.properties.seconds')"

            type="number"

            variant="outlined"

            density="compact"

            class="mb-3"

            @update:model-value="handleUpdate"

          />

        </template>

      </v-form>

    </v-card-text>



    <!-- 操作按钮 -->

    <v-card-actions v-if="node" class="pa-4 border-t">

      <v-spacer />

      <v-btn

        color="error"

        variant="outlined"

        @click="handleDelete"

      >

        <v-icon start icon="mdi-delete" />

        {{ $t('agent.flows.properties.deleteNode') }}

      </v-btn>

    </v-card-actions>

  </v-card>

</template>



<script setup lang="ts">

import { ref, watch, computed } from 'vue';

import axios from 'axios';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  node: any;

}>();



const emit = defineEmits<{

  (e: 'update:node', node: any): void;

  (e: 'delete', nodeId: string): void;

}>();



const { t } = useI18n();



// 本地节点数据

const localNode = ref<any>(null);



// 加载状

const loadingCrews = ref(false);



// Crew 选项

const crewOptions = ref<any[]>([]);



// 事件类型选项

const eventTypeOptions = computed(() => [

  { title: t('agent.flows.properties.eventTypes.message'), value: 'message' },

  { title: t('agent.flows.properties.eventTypes.command'), value: 'command' },

  { title: t('agent.flows.properties.eventTypes.schedule'), value: 'schedule' },

]);



// 输入映射文本

const inputMappingText = computed({

  get: () => JSON.stringify(localNode.value?.data?.config?.inputMapping || {}, null, 2),

  set: () => {},

});



// 选项文本

const optionsText = computed({

  get: () => (localNode.value?.data?.config?.options || []).join(', '),

  set: () => {},

});



// 监听节点变化

watch(() => props.node, (newNode) => {

  if (newNode) {

    localNode.value = JSON.parse(JSON.stringify(newNode));

    

    // 如果是 Crew 节点，加载 Crew 列表

    if (newNode.type === 'crew') {

      loadCrews();

    }

  } else {

    localNode.value = null;

  }

}, { immediate: true, deep: true });



// 加载 Crew 列表

async function loadCrews() {

  loadingCrews.value = true;

  try {

    const response = await axios.get('/api/plug/agent/crews');

    if (response.data.status === 'ok') {

      crewOptions.value = (response.data.data || []).map((crew: any) => ({

        title: crew.name,

        value: crew.name,

      }));

    }

  } catch (error) {

    console.error('Failed to load crews:', error);

  } finally {

    loadingCrews.value = false;

  }

}



// 处理更新

function handleUpdate() {

  emit('update:node', localNode.value);

}



// 处理输入映射更新

function handleInputMappingUpdate(value: string) {

  try {

    localNode.value.data.config.inputMapping = JSON.parse(value);

    handleUpdate();

  } catch (e) {

    // JSON 解析错误，忽

  }

}



// 处理选项更新

function handleOptionsUpdate(value: string) {

  localNode.value.data.config.options = value.split(',').map((s: string) => s.trim()).filter(Boolean);

  handleUpdate();

}



// 添加分支

function addBranch() {

  if (!localNode.value.data.config.branches) {

    localNode.value.data.config.branches = [];

  }

  localNode.value.data.config.branches.push({

    name: `${t('agent.flows.properties.branch')} ${localNode.value.data.config.branches.length + 1}`,

    condition: '',

  });

  handleUpdate();

}



// 移除分支

function removeBranch(index: number) {

  localNode.value.data.config.branches.splice(index, 1);

  handleUpdate();

}



// 删除节点

function handleDelete() {

  if (localNode.value) {

    emit('delete', localNode.value.id);

  }

}

</script>



<style scoped>

.v-card {

  border-radius: 0;

}

</style>

