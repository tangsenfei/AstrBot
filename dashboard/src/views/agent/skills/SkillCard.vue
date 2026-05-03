<template>
  <v-card
    class="skill-card"
    hover
    @click="$emit('viewDetail', skill)"
  >
    <v-card-text class="pb-2">
      <div class="d-flex align-start justify-space-between mb-2">
        <div class="flex-grow-1">
          <div class="text-h6 text-truncate" :title="skill.name">
            {{ skill.name }}
          </div>
          <div class="d-flex align-center mt-1">
            <v-chip
              :color="categoryColor"
              size="x-small"
              class="mr-2"
            >
              {{ categoryLabel }}
            </v-chip>
            <v-chip
              v-if="isBuiltin"
              color="secondary"
              size="x-small"
              variant="flat"
              class="mr-2"
            >
              {{ $t('agent.skills.card.builtinTag') }}
            </v-chip>
            <v-chip
              v-if="builtinTypeLabel"
              size="x-small"
              variant="tonal"
              color="secondary"
              class="mr-2"
            >
              {{ builtinTypeLabel }}
            </v-chip>
            <v-chip
              v-if="skill.version"
              size="x-small"
              variant="outlined"
            >
              v{{ skill.version }}
            </v-chip>
          </div>
        </div>
        <v-icon
          :icon="disclosureIcon"
          :color="disclosureColor"
          size="small"
          class="ml-2"
        />
      </div>

      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">
        {{ skill.description || $t('agent.skills.card.noDescription') }}
      </p>

      <div class="d-flex align-center mb-2">
        <v-icon icon="mdi-eye" size="small" class="mr-1" />
        <span class="text-caption text-grey">
          {{ $t('agent.skills.card.disclosureLevel') }}: {{ disclosureLabel }}
        </span>
      </div>

      <div v-if="preapprovedToolsCount > 0" class="d-flex align-center mb-2">
        <v-icon icon="mdi-check-circle" size="small" class="mr-1" color="success" />
        <span class="text-caption text-grey">
          {{ $t('agent.skills.card.preapprovedTools', { count: preapprovedToolsCount }) }}
        </span>
      </div>

      <div v-if="workflowStepsCount > 0" class="d-flex align-center mb-2">
        <v-icon icon="mdi-flowchart" size="small" class="mr-1" color="info" />
        <span class="text-caption text-grey">
          {{ $t('agent.skills.card.workflow') }}: {{ workflowStepsCount }} {{ $t('agent.workflow.steps') }}
        </span>
      </div>

      <div v-if="skill.tags && skill.tags.length > 0" class="mb-3">
        <v-chip
          v-for="tag in skill.tags.slice(0, 3)"
          :key="tag"
          size="x-small"
          variant="outlined"
          class="mr-1 mb-1"
        >
          {{ tag }}
        </v-chip>
        <v-chip
          v-if="skill.tags.length > 3"
          size="x-small"
          variant="outlined"
          class="mr-1 mb-1"
        >
          +{{ skill.tags.length - 3 }}
        </v-chip>
      </div>
    </v-card-text>

    <v-divider />

    <v-card-actions class="pa-2" @click.stop>
      <v-btn
        icon
        size="small"
        variant="text"
        color="info"
        @click="$emit('test', skill)"
        :title="$t('agent.skills.card.test')"
      >
        <v-icon icon="mdi-bug-play" />
      </v-btn>
      <v-btn
        v-if="!isBuiltin"
        icon
        size="small"
        variant="text"
        color="primary"
        @click="$emit('edit', skill)"
        :title="$t('agent.skills.card.edit')"
      >
        <v-icon icon="mdi-pencil" />
      </v-btn>
      <v-btn
        v-if="!isBuiltin"
        icon
        size="small"
        variant="text"
        color="error"
        @click="$emit('delete', skill)"
        :title="$t('agent.skills.card.delete')"
      >
        <v-icon icon="mdi-delete" />
      </v-btn>
      <v-spacer />
      <v-btn
        icon
        size="small"
        variant="text"
        @click.stop="$emit('viewDetail', skill)"
      >
        <v-icon icon="mdi-information-outline" />
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps<{
  skill: any;
}>();

const emit = defineEmits<{
  (e: 'edit', skill: any): void;
  (e: 'test', skill: any): void;
  (e: 'delete', skill: any): void;
  (e: 'viewDetail', skill: any): void;
}>();

const { t } = useI18n();

const isBuiltin = computed(() => {
  return props.skill.source === 'builtin';
});

const builtinTypeLabel = computed(() => {
  if (!isBuiltin.value) return '';
  const builtinType = props.skill.metadata?.builtin_type;
  if (builtinType === 'flow_generator') {
    return t('agent.skills.card.builtinTypeFlowGenerator');
  }
  if (builtinType === 'expert_agent') {
    return t('agent.skills.card.builtinTypeExpertAgent');
  }
  return '';
});

const categoryColor = computed(() => {
  switch (props.skill.source) {
    case 'builtin':
      return 'secondary';
    case 'astrbot':
      return 'primary';
    case 'claudcode':
      return 'success';
    case 'crewai':
      return 'warning';
    case 'custom':
    default:
      return 'grey';
  }
});

const categoryLabel = computed(() => {
  return t(`agent.skills.sources.${props.skill.source}`) || props.skill.source;
});

const disclosureColor = computed(() => {
  switch (props.skill.disclosure_level) {
    case 'metadata':
      return 'grey';
    case 'instructions':
      return 'warning';
    case 'resources':
      return 'success';
    default:
      return 'grey';
  }
});

const disclosureIcon = computed(() => {
  switch (props.skill.disclosure_level) {
    case 'metadata':
      return 'mdi-database';
    case 'instructions':
      return 'mdi-file-document';
    case 'resources':
      return 'mdi-folder-open';
    default:
      return 'mdi-help-circle';
  }
});

const disclosureLabel = computed(() => {
  return t(`agent.skills.disclosureLevels.${props.skill.disclosure_level}`) || props.skill.disclosure_level;
});

const preapprovedToolsCount = computed(() => {
  return props.skill.preapproved_tools?.length || 0;
});

const workflowStepsCount = computed(() => {
  return props.skill.workflow?.steps?.length || 0;
});
</script>

<style scoped>
.skill-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  cursor: pointer;
}

.skill-card:hover {
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
