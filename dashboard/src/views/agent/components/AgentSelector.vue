<template>
  <div class="agent-selector">
    <v-text-field
      v-model="searchQuery"
      prepend-inner-icon="mdi-magnify"
      placeholder="搜索智能体..."
      variant="outlined"
      density="compact"
      hide-details
      clearable
      class="mb-3"
    />

    <div class="category-chips mb-3">
      <v-chip
        size="small"
        :variant="selectedCategory === 'all' ? 'flat' : 'outlined'"
        :color="selectedCategory === 'all' ? 'primary' : 'default'"
        @click="selectedCategory = 'all'"
        class="mr-1"
      >
        全部
      </v-chip>
      <v-chip
        size="small"
        :variant="selectedCategory === 'builtin' ? 'flat' : 'outlined'"
        :color="selectedCategory === 'builtin' ? 'success' : 'default'"
        @click="selectedCategory = 'builtin'"
        class="mr-1"
      >
        内置
      </v-chip>
      <v-chip
        size="small"
        :variant="selectedCategory === 'expert' ? 'flat' : 'outlined'"
        :color="selectedCategory === 'expert' ? 'purple' : 'default'"
        @click="selectedCategory = 'expert'"
        class="mr-1"
      >
        专家团
      </v-chip>
      <v-chip
        size="small"
        :variant="selectedCategory === 'custom' ? 'flat' : 'outlined'"
        :color="selectedCategory === 'custom' ? 'orange' : 'default'"
        @click="selectedCategory = 'custom'"
      >
        自定义
      </v-chip>
    </div>

    <div v-if="showExpertCategories && selectedCategory === 'expert'" class="expert-categories mb-3">
      <v-chip
        v-for="cat in expertCategories"
        :key="cat"
        size="x-small"
        :variant="selectedExpertCategory === cat ? 'flat' : 'tonal'"
        :color="selectedExpertCategory === cat ? 'purple' : 'default'"
        @click="selectedExpertCategory = selectedExpertCategory === cat ? '' : cat"
        class="mr-1 mb-1"
      >
        {{ cat }}
      </v-chip>
    </div>

    <div v-if="loading" class="text-center py-4">
      <v-progress-circular indeterminate size="24" color="primary" />
    </div>

    <div v-else-if="filteredAgents.length === 0" class="text-center py-4">
      <v-icon icon="mdi-robot-off" size="40" color="grey-lighten-1" class="mb-2" />
      <p class="text-grey text-body-2">无匹配智能体</p>
    </div>

    <div v-else class="agent-grid">
      <div
        v-for="agent in filteredAgents"
        :key="agent.value"
        class="agent-card"
        :class="{ selected: isSelected(agent.value) }"
        @click="toggleAgent(agent)"
      >
        <div class="d-flex align-center">
          <v-avatar
            :color="getAgentColor(agent)"
            size="32"
            class="mr-3"
          >
            <v-icon
              :icon="isSelected(agent.value) ? 'mdi-check' : getAgentIcon(agent)"
              :color="isSelected(agent.value) ? 'white' : undefined"
              size="18"
            />
          </v-avatar>
          <div class="flex-grow-1" style="min-width: 0">
            <div class="text-subtitle-2 font-weight-medium text-truncate">{{ agent.title }}</div>
            <div class="text-caption text-grey text-truncate">{{ agent.soul || agent.agentType }}</div>
          </div>
          <v-chip
            v-if="agent.agentType === 'builtin'"
            size="x-small"
            color="success"
            variant="tonal"
            class="ml-1 flex-shrink-0"
          >
            内置
          </v-chip>
          <v-chip
            v-else-if="agent.agentType === 'expert'"
            size="x-small"
            color="purple"
            variant="tonal"
            class="ml-1 flex-shrink-0"
          >
            专家
          </v-chip>
        </div>
      </div>
    </div>

    <v-divider class="my-3" v-if="modelValue.length > 0" />

    <div v-if="modelValue.length > 0" class="selected-agents">
      <div class="text-caption text-grey mb-2">已选 ({{ modelValue.length }})</div>
      <div class="d-flex flex-wrap ga-2">
        <v-chip
          v-for="(agentId, index) in modelValue"
          :key="agentId"
          closable
          :color="getAgentChipColor(agentId)"
          variant="tonal"
          size="small"
          @click:close="removeAgent(index)"
        >
          {{ getAgentName(agentId) }}
        </v-chip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import axios from 'axios';

const props = withDefaults(defineProps<{
  modelValue: string[];
  loading?: boolean;
  showExpertCategories?: boolean;
}>(), {
  loading: false,
  showExpertCategories: true,
});

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void;
}>();

const searchQuery = ref('');
const selectedCategory = ref('all');
const selectedExpertCategory = ref('');
const agents = ref<any[]>([]);
const expertCategories = ref<string[]>([]);
const loading = ref(false);

const filteredAgents = computed(() => {
  let result = agents.value;

  if (selectedCategory.value !== 'all') {
    result = result.filter(a => a.agentType === selectedCategory.value);
  }

  if (selectedExpertCategory.value && selectedCategory.value === 'expert') {
    result = result.filter(a => a.expertCategory === selectedExpertCategory.value);
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(a =>
      a.title.toLowerCase().includes(q) ||
      (a.soul || '').toLowerCase().includes(q)
    );
  }

  return result;
});

function isSelected(agentValue: string): boolean {
  return props.modelValue.includes(agentValue);
}

function toggleAgent(agent: any) {
  const newValue = [...props.modelValue];
  const index = newValue.indexOf(agent.value);
  if (index === -1) {
    newValue.push(agent.value);
  } else {
    newValue.splice(index, 1);
  }
  emit('update:modelValue', newValue);
}

function removeAgent(index: number) {
  const newValue = [...props.modelValue];
  newValue.splice(index, 1);
  emit('update:modelValue', newValue);
}

function getAgentName(agentId: string): string {
  const agent = agents.value.find(a => a.value === agentId);
  return agent?.title || agentId;
}

function getAgentColor(agent: any): string {
  if (isSelected(agent.value)) return 'primary';
  switch (agent.agentType) {
    case 'builtin': return 'success';
    case 'expert': return 'purple';
    case 'custom': return 'orange';
    default: return 'grey';
  }
}

function getAgentIcon(agent: any): string {
  switch (agent.agentType) {
    case 'builtin': return 'mdi-cog';
    case 'expert': return 'mdi-star';
    default: return 'mdi-robot';
  }
}

function getAgentChipColor(agentId: string): string {
  const agent = agents.value.find(a => a.value === agentId);
  if (!agent) return 'default';
  switch (agent.agentType) {
    case 'builtin': return 'success';
    case 'expert': return 'purple';
    case 'custom': return 'orange';
    default: return 'primary';
  }
}

async function loadAgents() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/agents');
    if (response.data.status === 'ok') {
      const rawAgents = response.data.data || [];
      agents.value = rawAgents.map((agent: any) => ({
        title: agent.name,
        value: agent.id || agent.name,
        soul: agent.soul || '-',
        agentType: agent.agent_type || 'custom',
        expertCategory: agent.metadata?.category || '',
        isMeetingAssistant: agent.metadata?.is_meeting_assistant === true,
      }));

      const cats = new Set<string>();
      rawAgents.forEach((agent: any) => {
        if (agent.agent_type === 'expert' && agent.metadata?.category) {
          cats.add(agent.metadata.category);
        }
      });
      expertCategories.value = Array.from(cats).sort();
    }
  } catch (error) {
    console.error('Failed to load agents:', error);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAgents();
});
</script>

<style scoped>
.category-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.expert-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 80px;
  overflow-y: auto;
  padding: 4px 0;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.agent-card {
  padding: 10px 12px;
  border: 2px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
}

.agent-card:hover {
  border-color: #93c5fd;
  background: #f0f9ff;
}

.agent-card.selected {
  border-color: #3b82f6;
  background: #eff6ff;
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.2);
}

.selected-agents {
  padding: 4px 0;
}
</style>
