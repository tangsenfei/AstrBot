<template>
  <v-card class="expert-card" hover>
    <v-card-text class="pb-2">
      <div class="d-flex align-start mb-3">
        <v-avatar :color="categoryColor" size="48" class="mr-3">
          <v-icon :icon="expert.icon" color="white" />
        </v-avatar>
        <div class="flex-grow-1">
          <div class="text-h6 text-truncate" :title="expert.name">
            {{ expert.name }}
          </div>
          <v-chip size="x-small" :color="categoryColor" variant="flat" class="mt-1">
            {{ categoryLabel }}
          </v-chip>
        </div>
      </div>

      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">
        {{ expert.role }}
      </p>

      <div class="d-flex flex-wrap" style="gap: 4px;">
        <v-chip
          v-for="tag in expert.tags.slice(0, 3)"
          :key="tag"
          size="x-small"
          variant="outlined"
          color="primary"
        >
          {{ tag }}
        </v-chip>
        <v-chip
          v-if="expert.tags.length > 3"
          size="x-small"
          variant="outlined"
          color="grey"
        >
          +{{ expert.tags.length - 3 }}
        </v-chip>
      </div>
    </v-card-text>

    <v-divider />

    <v-card-actions class="pa-2">
      <v-btn
        size="small"
        variant="text"
        color="info"
        @click="$emit('preview', expert)"
      >
        <v-icon icon="mdi-eye" start size="small" />
        {{ t('expertTeam.preview') }}
      </v-btn>
      <v-spacer />
      <v-btn
        size="small"
        variant="flat"
        color="primary"
        @click="$emit('create', expert)"
      >
        <v-icon icon="mdi-plus" start size="small" />
        {{ t('expertTeam.createAgent') }}
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ExpertTemplate } from './expertTemplates';
import { expertCategories } from './expertTemplates';

const props = defineProps<{
  expert: ExpertTemplate;
}>();

defineEmits<{
  (e: 'preview', expert: ExpertTemplate): void;
  (e: 'create', expert: ExpertTemplate): void;
}>();

const { t } = useI18n();

const categoryColorMap: Record<string, string> = {
  engineering: 'blue',
  product: 'orange',
  design: 'purple',
  marketing: 'green',
  security: 'red',
  finance: 'teal',
  game: 'indigo',
  specialized: 'amber',
};

const categoryColor = computed(() => categoryColorMap[props.expert.category] || 'grey');

const categoryLabel = computed(() => {
  const cat = expertCategories.find(c => c.key === props.expert.category);
  return cat ? t(cat.label) : props.expert.category;
});
</script>

<style scoped>
.expert-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  border-radius: 12px;
}

.expert-card:hover {
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
