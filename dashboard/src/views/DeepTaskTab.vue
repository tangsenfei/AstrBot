<template>
  <div class="deep-task-tab">
    <v-card class="rounded-lg" variant="flat">
      <v-card-text class="text-center py-16">
        <v-icon size="80" color="grey-lighten-1">mdi-robot-outline</v-icon>
        <h3 class="text-h5 mt-4 text-medium-emphasis">{{ tm('deep.comingSoon') }}</h3>
        <p class="text-body-2 text-medium-emphasis mt-2">{{ tm('deep.description') }}</p>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { useModuleI18n } from '@/i18n/composables'

const { tm } = useModuleI18n('features/task-management')
</script>

<style scoped>
.deep-task-tab {
  /* no extra padding */
}
</style>
