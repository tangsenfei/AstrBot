<template>

  <v-card

    class="knowledge-card"

    hover

  >

    <v-card-text class="pb-2">

      <!-- 标题 -->

      <div class="d-flex align-start justify-space-between mb-2">

        <div class="flex-grow-1">

          <div class="text-h6 text-truncate" :title="knowledgeBase.name">

            {{ knowledgeBase.name }}

          </div>

        </div>

        <v-chip

          :color="statusColor"

          size="x-small"

          class="ml-2"

        >

          {{ statusLabel }}

        </v-chip>

      </div>



      <!-- 描述 -->

      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">

        {{ knowledgeBase.description || $t('agent.knowledge.card.noDescription') }}

      </p>



      <!-- 统计信息 -->

      <div class="d-flex flex-wrap ga-2 mb-3">

        <v-chip size="x-small" variant="outlined" color="primary">

          <v-icon start icon="mdi-file-document-multiple" size="small" />

          {{ $t('agent.knowledge.card.sources', { count: knowledgeBase.source_count || 0 }) }}

        </v-chip>

        <v-chip size="x-small" variant="outlined" color="info">

          <v-icon start icon="mdi-vector-polygon" size="small" />

          {{ knowledgeBase.collection_name }}

        </v-chip>

      </div>



      <!-- 嵌入模型 -->

      <div class="d-flex align-center mb-2">

        <v-icon icon="mdi-brain" size="small" class="mr-1" />

        <span class="text-caption text-grey">

          {{ knowledgeBase.embedding_model || $t('agent.knowledge.card.noModel') }}

        </span>

      </div>



      <!-- 创建时间 -->

      <div class="d-flex align-center">

        <v-icon icon="mdi-clock-outline" size="small" class="mr-1" />

        <span class="text-caption text-grey">

          {{ formatDate(knowledgeBase.created_at) }}

        </span>

      </div>

    </v-card-text>



    <v-divider />



    <!-- 操作按钮 -->

    <v-card-actions class="pa-2">

      <v-btn

        icon

        size="small"

        variant="text"

        color="success"

        @click="$emit('add-source', knowledgeBase)"

        :title="$t('agent.knowledge.card.addSource')"

      >

        <v-icon icon="mdi-plus-circle" />

      </v-btn>

      <v-btn

        icon

        size="small"

        variant="text"

        color="info"

        @click="$emit('test', knowledgeBase)"

        :title="$t('agent.knowledge.card.test')"

      >

        <v-icon icon="mdi-magnify" />

      </v-btn>

      <v-btn

        icon

        size="small"

        variant="text"

        color="primary"

        @click="$emit('edit', knowledgeBase)"

        :title="$t('agent.knowledge.card.edit')"

      >

        <v-icon icon="mdi-pencil" />

      </v-btn>

      <v-btn

        icon

        size="small"

        variant="text"

        color="error"

        @click="$emit('delete', knowledgeBase)"

        :title="$t('agent.knowledge.card.delete')"

      >

        <v-icon icon="mdi-delete" />

      </v-btn>

    </v-card-actions>

  </v-card>

</template>



<script setup lang="ts">

import { computed } from 'vue';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  knowledgeBase: any;

}>();



const emit = defineEmits<{

  (e: 'edit', knowledgeBase: any): void;

  (e: 'add-source', knowledgeBase: any): void;

  (e: 'test', knowledgeBase: any): void;

  (e: 'delete', knowledgeBase: any): void;

}>();



const { t } = useI18n();



// 计算属性

const statusColor = computed(() => {

  if (props.knowledgeBase.source_count > 0) {

    return 'success';

  }

  return 'warning';

});



const statusLabel = computed(() => {

  if (props.knowledgeBase.source_count > 0) {

    return t('agent.knowledge.status.active');

  }

  return t('agent.knowledge.status.empty');

});



// 格式化日期

function formatDate(dateStr: string) {

  if (!dateStr) return '-';

  const date = new Date(dateStr);

  return date.toLocaleString();

}

</script>



<style scoped>

.knowledge-card {

  height: 100%;

  display: flex;

  flex-direction: column;

  transition: all 0.3s ease;

}



.knowledge-card:hover {

  transform: translateY(-2px);

  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

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

