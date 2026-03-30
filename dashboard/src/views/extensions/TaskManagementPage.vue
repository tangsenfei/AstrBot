<template>
  <div class="task-management-page">
    <v-card class="rounded-lg mb-4" variant="flat">
      <v-tabs v-model="activeTab" color="primary" class="border-b">
        <v-tab value="simple">{{ tm('tabs.simple') }}</v-tab>
        <v-tab value="deep">{{ tm('tabs.deep') }}</v-tab>
        <v-tab value="deerflow">{{ tm('tabs.deerflow') }}</v-tab>
      </v-tabs>
    </v-card>

    <SimpleTaskTab v-if="activeTab === 'simple'" />
    <DeepTaskTab v-else-if="activeTab === 'deep'" />
    <DeerFlowTaskTab v-else-if="activeTab === 'deerflow'" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useModuleI18n } from '@/i18n/composables'
import SimpleTaskTab from './SimpleTaskTab.vue'
import DeepTaskTab from './DeepTaskTab.vue'
import DeerFlowTaskTab from './DeerFlowTaskTab.vue'

const { tm } = useModuleI18n('features/task-management')
const activeTab = ref('simple')
</script>

<style scoped>
.task-management-page {
  padding: 20px;
  padding-top: 8px;
  padding-bottom: 40px;
}
</style>
