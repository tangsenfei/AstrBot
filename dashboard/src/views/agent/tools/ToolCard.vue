<template>

  <v-card

    class="tool-card"

    :class="{ 'tool-disabled': !tool.enabled }"

    hover

  >

    <v-card-text class="pb-2">

      <!-- 标题和状态-->

      <div class="d-flex align-start justify-space-between mb-2">

        <div class="flex-grow-1">

          <div class="text-h6 text-truncate" :title="tool.name">

            {{ tool.name }}

          </div>

          <v-chip

            :color="sourceColor"

            size="x-small"

            class="mt-1"

          >

            {{ sourceLabel }}

          </v-chip>

        </div>

        <v-switch

          v-model="tool.enabled"

          color="success"

          hide-details

          density="compact"

          class="ml-2 mt-0"

          @change="handleToggle"

        />

      </div>



      <!-- 描述 -->

      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">

        {{ tool.description || $t('agent.tools.card.noDescription') }}

      </p>



      <!-- 参数数量 -->

      <div v-if="paramCount > 0" class="d-flex align-center mb-2">

        <v-icon icon="mdi-code-json" size="small" class="mr-1" />

        <span class="text-caption text-grey">

          {{ $t('agent.tools.card.params', { count: paramCount }) }}

        </span>

      </div>



      <!-- 标签 -->

      <div v-if="tool.tags && tool.tags.length > 0" class="mb-3">

        <v-chip

          v-for="tag in tool.tags.slice(0, 3)"

          :key="tag"

          size="x-small"

          variant="outlined"

          class="mr-1 mb-1"

        >

          {{ tag }}

        </v-chip>

        <v-chip

          v-if="tool.tags.length > 3"

          size="x-small"

          variant="outlined"

          class="mr-1 mb-1"

        >

          +{{ tool.tags.length - 3 }}

        </v-chip>

      </div>

    </v-card-text>



    <v-divider />



    <!-- 操作按钮 -->

    <v-card-actions class="pa-2">

      <v-btn

        icon

        size="small"

        variant="text"

        color="info"

        @click="$emit('test', tool)"

        :title="$t('agent.tools.card.test')"

      >

        <v-icon icon="mdi-bug-play" />

      </v-btn>

      <v-btn

        icon

        size="small"

        variant="text"

        color="primary"

        @click="$emit('edit', tool)"

        :title="$t('agent.tools.card.edit')"

        :disabled="!canEdit"

      >

        <v-icon icon="mdi-pencil" />

      </v-btn>

      <v-btn

        icon

        size="small"

        variant="text"

        color="error"

        @click="$emit('delete', tool)"

        :title="$t('agent.tools.card.delete')"

        :disabled="!canDelete"

      >

        <v-icon icon="mdi-delete" />

      </v-btn>

      <v-spacer />

      <v-btn

        icon

        size="small"

        variant="text"

        @click="showDetails = !showDetails"

      >

        <v-icon :icon="showDetails ? 'mdi-chevron-up' : 'mdi-chevron-down'" />

      </v-btn>

    </v-card-actions>



    <!-- 详情展开 -->

    <v-expand-transition>

      <div v-show="showDetails">

        <v-divider />

        <v-card-text class="pt-2">

          <!-- 参数列表 -->

          <div v-if="tool.parameters && Object.keys(tool.parameters).length > 0">

            <div class="text-subtitle-2 mb-2">{{ $t('agent.tools.card.parameters') }}</div>

            <v-list density="compact" class="bg-grey-lighten-4 rounded">

              <v-list-item

                v-for="(param, key) in tool.parameters"

                :key="key"

                class="px-2"

              >

                <template v-slot:prepend>

                  <v-chip size="x-small" color="primary" variant="flat" class="mr-2">

                    {{ param.type || 'any' }}

                  </v-chip>

                </template>

                <v-list-item-title class="text-body-2">{{ key }}</v-list-item-title>

                <v-list-item-subtitle v-if="param.description" class="text-caption">

                  {{ param.description }}

                </v-list-item-subtitle>

              </v-list-item>

            </v-list>

          </div>



          <!-- 元数据-->

          <div v-if="tool.metadata" class="mt-3">

            <div class="text-subtitle-2 mb-2">{{ $t('agent.tools.card.metadata') }}</div>

            <v-list density="compact" class="bg-grey-lighten-4 rounded">

              <v-list-item

                v-for="(value, key) in tool.metadata"

                :key="key"

                class="px-2"

              >

                <v-list-item-title class="text-body-2">{{ key }}</v-list-item-title>

                <v-list-item-subtitle class="text-caption">{{ value }}</v-list-item-subtitle>

              </v-list-item>

            </v-list>

          </div>

        </v-card-text>

      </div>

    </v-expand-transition>

  </v-card>

</template>



<script setup lang="ts">

import { ref, computed } from 'vue';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  tool: any;

}>();



const emit = defineEmits<{

  (e: 'edit', tool: any): void;

  (e: 'test', tool: any): void;

  (e: 'delete', tool: any): void;

  (e: 'toggle', tool: any): void;

}>();



const { t } = useI18n();

const showDetails = ref(false);



// 计算属性

const sourceColor = computed(() => {

  switch (props.tool.source) {

    case 'builtin':

      return 'primary';

    case 'mcp':

      return 'success';

    case 'custom':

      return 'warning';

    case 'api_wrapper':

      return 'info';

    default:

      return 'grey';

  }

});



const sourceLabel = computed(() => {

  switch (props.tool.source) {

    case 'builtin':

      return t('agent.tools.sources.builtin');

    case 'mcp':

      return t('agent.tools.sources.mcp');

    case 'custom':

      return t('agent.tools.sources.custom');

    case 'api_wrapper':

      return t('agent.tools.sources.apiWrapper');

    default:

      return props.tool.source;

  }

});



const paramCount = computed(() => {

  if (!props.tool.parameters) return 0;

  return Object.keys(props.tool.parameters).length;

});



const canEdit = computed(() => {

  return props.tool.source !== 'builtin';

});



const canDelete = computed(() => {

  return props.tool.source !== 'builtin';

});



// 方法

function handleToggle() {

  emit('toggle', props.tool);

}

</script>



<style scoped>

.tool-card {

  height: 100%;

  display: flex;

  flex-direction: column;

  transition: all 0.3s ease;

}



.tool-card:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

}



.tool-disabled {

  opacity: 0.7;

}



.description-text {

  display: -webkit-box;

  -webkit-line-clamp: 2;

  -webkit-box-orient: vertical;

  overflow: hidden;

  min-height: 40px;

}



.v-card-actions {

  margin-top: auto;

}

</style>

