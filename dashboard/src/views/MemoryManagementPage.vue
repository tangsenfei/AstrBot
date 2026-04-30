<template>
  <v-container fluid class="pa-4">
    <v-row class="mb-4">
      <v-col cols="12" sm="3">
        <v-select
          v-model="selectedAgent"
          :items="agentOptions"
          label="Agent"
          density="compact"
          variant="outlined"
          hide-details
          @update:model-value="onFilterChange"
        />
      </v-col>
      <v-col cols="12" sm="2">
        <v-select
          v-model="selectedTypes"
          :items="eventTypeOptions"
          label="Type"
          density="compact"
          variant="outlined"
          hide-details
          multiple
          @update:model-value="onFilterChange"
        />
      </v-col>
      <v-col cols="12" sm="3">
        <v-text-field
          v-model="searchText"
          label="Search events..."
          density="compact"
          variant="outlined"
          hide-details
          clearable
          @update:model-value="onSearchDebounce"
          append-inner-icon="mdi-magnify"
        />
      </v-col>
      <v-col cols="12" sm="2">
        <v-select
          v-model="timeRange"
          :items="timeRangeOptions"
          label="Time"
          density="compact"
          variant="outlined"
          hide-details
          @update:model-value="onFilterChange"
        />
      </v-col>
      <v-col cols="12" sm="2" class="d-flex align-center" style="gap: 8px">
        <v-btn
          color="primary"
          variant="text"
          :loading="loading"
          icon="mdi-refresh"
          @click="refreshEvents"
        />
        <v-btn
          variant="text"
          icon="mdi-download"
          @click="handleExport"
        />
      </v-col>
    </v-row>

    <v-row class="mb-4">
      <v-col v-for="stat in statCards" :key="stat.key" cols="6" sm="4" md="2">
        <v-card variant="outlined" class="pa-3 text-center">
          <div class="text-h4 font-weight-bold">{{ stat.value }}</div>
          <div class="text-caption text-grey">{{ stat.label }}</div>
        </v-card>
      </v-col>
    </v-row>

    <v-tabs v-model="activeTab" class="mb-4">
      <v-tab value="events">
        <v-icon start size="small">mdi-text-box-multiple</v-icon>
        Events
        <v-chip v-if="stats.events_total" size="x-small" class="ml-1">{{ stats.events_total }}</v-chip>
      </v-tab>
      <v-tab value="scenes">
        <v-icon start size="small">mdi-book-open-variant</v-icon>
        Episodic
      </v-tab>
      <v-tab value="claims">
        <v-icon start size="small">mdi-brain</v-icon>
        Semantic
      </v-tab>
      <v-tab value="rules">
        <v-icon start size="small">mdi-ruler-square</v-icon>
        Procedural
      </v-tab>
      <v-tab value="identity">
        <v-icon start size="small">mdi-card-account-details</v-icon>
        Identity
      </v-tab>
      <v-tab value="prompts">
        <v-icon start size="small">mdi-text-box-edit</v-icon>
        Prompts
      </v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <v-window-item value="events">
        <v-card>
          <v-card-text class="pa-0">
            <div v-if="events.length === 0 && !loading" class="text-center py-8 text-grey">
              <v-icon size="64" color="grey-lighten-1">mdi-text-box-multiple-outline</v-icon>
              <div class="mt-2">No events yet</div>
              <div class="text-caption">Events will be automatically recorded when agents start conversing</div>
            </div>

            <v-list v-else lines="two" class="pa-0">
              <template v-for="(event, idx) in events" :key="event.id">
                <v-list-item
                  @click="toggleEventDetail(event.id)"
                  :class="{ 'bg-grey-lighten-4': expandedEvents.has(event.id) }"
                >
                  <template #prepend>
                    <v-icon :color="eventTypeColor(event.type)" size="20">
                      {{ eventTypeIcon(event.type) }}
                    </v-icon>
                  </template>

                  <v-list-item-title class="d-flex align-center text-caption font-weight-medium">
                    <v-chip
                      :color="eventTypeColor(event.type)"
                      size="x-small"
                      variant="tonal"
                      class="mr-2"
                    >
                      {{ eventTypeLabel(event.type) }}
                    </v-chip>
                    {{ formatTime(event.created_at) }}
                  </v-list-item-title>

                  <v-list-item-subtitle class="text-body-2 mt-1">
                    <span class="text-grey-darken-2">{{ truncate(event.content, 120) }}</span>
                  </v-list-item-subtitle>
                </v-list-item>

                <v-divider v-if="idx < events.length - 1" />

                <v-expand-transition>
                  <v-card v-if="expandedEvents.has(event.id)" variant="flat" class="bg-grey-lighten-5 pa-4 mx-4 mb-2">
                    <div class="text-body-2 mb-2"><strong>Full Content</strong></div>
                    <pre class="text-body-2 mb-3" style="white-space: pre-wrap; word-break: break-all;">{{ event.content }}</pre>

                    <div v-if="Object.keys(event.metadata || {}).length > 0" class="mb-2">
                      <strong class="text-body-2">Metadata</strong>
                      <pre class="text-caption mt-1">{{ JSON.stringify(event.metadata, null, 2) }}</pre>
                    </div>

                    <div class="d-flex text-caption text-grey" style="gap: 16px">
                      <span>Agent: {{ event.agent_id }}</span>
                      <span>ID: {{ event.id }}</span>
                      <span v-if="event.scene_id">Scene: {{ event.scene_id }}</span>
                    </div>
                  </v-card>
                </v-expand-transition>
              </template>
            </v-list>
          </v-card-text>
        </v-card>

        <div class="d-flex justify-center mt-4" v-if="stats.events_total > pageSize">
          <v-pagination
            v-model="currentPage"
            :length="Math.ceil(stats.events_total / pageSize)"
            @update:model-value="refreshEvents"
            density="compact"
          />
        </div>
      </v-window-item>

      <v-window-item v-for="tab in placeholderTabs" :key="tab.value" :value="tab.value">
        <v-card class="text-center py-12 text-grey">
          <v-icon size="64" color="grey-lighten-1">mdi-clock-outline</v-icon>
          <div class="text-h6 mt-2">{{ tab.label }}</div>
          <div class="text-body-2 mt-1">Coming in a future phase</div>
        </v-card>
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  fetchEvents,
  fetchMemoryStats,
  type MemoryEvent,
  type MemoryStats,
} from '@/api/memory';

const activeTab = ref('events');
const loading = ref(false);
const events = ref<MemoryEvent[]>([]);
const stats = ref<MemoryStats>({
  events_total: 0, scenes_total: 0, claims_total: 0,
  rules_total: 0, identity_total: 0, active_prompts: 0,
  event_counts_by_agent: [],
});
const selectedAgent = ref<string>('');
const selectedTypes = ref<string[]>([]);
const searchText = ref('');
const timeRange = ref('7d');
const currentPage = ref(1);
const pageSize = 50;
const expandedEvents = ref<Set<string>>(new Set());

let searchTimer: ReturnType<typeof setTimeout> | null = null;

const agentOptions = computed(() => {
  const options = [{ title: 'All Agents', value: '' }];
  stats.value.event_counts_by_agent.forEach(a => {
    const name = a.agent_id === 'main' ? 'Main (NiceBot)' : a.agent_id;
    options.push({ title: name, value: a.agent_id });
  });
  return options;
});

const eventTypeOptions = [
  { title: 'User Message', value: 'user_message' },
  { title: 'Agent Reply', value: 'agent_reply' },
  { title: 'Tool Call', value: 'tool_call' },
  { title: 'Scheduled Task', value: 'scheduled_task' },
  { title: 'System Event', value: 'system_event' },
];

const timeRangeOptions = [
  { title: 'Today', value: '1d' },
  { title: 'Last 3 days', value: '3d' },
  { title: 'Last 7 days', value: '7d' },
  { title: 'Last 30 days', value: '30d' },
  { title: 'All', value: 'all' },
];

const placeholderTabs = [
  { value: 'scenes', label: 'Episodic Memory' },
  { value: 'claims', label: 'Semantic Memory' },
  { value: 'rules', label: 'Procedural Memory' },
  { value: 'identity', label: 'Identity Memory' },
  { value: 'prompts', label: 'Prompt Management' },
];

const statCards = computed(() => [
  { key: 'events', label: 'Total Events', value: stats.value.events_total },
  { key: 'scenes', label: 'Total Scenes', value: stats.value.scenes_total },
  { key: 'claims', label: 'Semantic Facts', value: stats.value.claims_total },
  { key: 'rules', label: 'Rules', value: stats.value.rules_total },
  { key: 'identity', label: 'Identity Items', value: stats.value.identity_total },
  { key: 'prompts', label: 'Active Prompts', value: stats.value.active_prompts },
]);

function eventTypeIcon(type: string): string {
  const map: Record<string, string> = {
    user_message: 'mdi-account',
    agent_reply: 'mdi-robot',
    tool_call: 'mdi-tools',
    scheduled_task: 'mdi-clock-outline',
    system_event: 'mdi-cog',
  };
  return map[type] || 'mdi-circle-small';
}

function eventTypeColor(type: string): string {
  const map: Record<string, string> = {
    user_message: 'blue',
    agent_reply: 'green',
    tool_call: 'orange',
    scheduled_task: 'purple',
    system_event: 'grey',
  };
  return map[type] || 'grey';
}

function eventTypeLabel(type: string): string {
  const map: Record<string, string> = {
    user_message: 'User Msg',
    agent_reply: 'Agent Reply',
    tool_call: 'Tool Call',
    scheduled_task: 'Scheduled',
    system_event: 'System',
  };
  return map[type] || type;
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max) + '...' : text;
}

function toggleEventDetail(eventId: string) {
  const s = new Set(expandedEvents.value);
  if (s.has(eventId)) {
    s.delete(eventId);
  } else {
    s.add(eventId);
  }
  expandedEvents.value = s;
}

async function refreshEvents() {
  loading.value = true;
  try {
    const { start_time, end_time } = getTimeRange();
    const res = await fetchEvents({
      agent_id: selectedAgent.value || undefined,
      type: selectedTypes.value.length > 0 ? selectedTypes.value.join(',') : undefined,
      search: searchText.value || undefined,
      start_time,
      end_time,
      page: currentPage.value,
      page_size: pageSize,
    });
    events.value = res.items;
    stats.value.events_total = res.total;
  } catch (e) {
    console.error('Failed to fetch events:', e);
  } finally {
    loading.value = false;
  }
}

async function loadStats() {
  try {
    stats.value = await fetchMemoryStats(selectedAgent.value || undefined);
  } catch (e) {
    console.error('Failed to load stats:', e);
  }
}

function onFilterChange() {
  currentPage.value = 1;
  refreshEvents();
  loadStats();
}

function onSearchDebounce() {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentPage.value = 1;
    refreshEvents();
  }, 500);
}

function getTimeRange() {
  if (timeRange.value === 'all') return { start_time: undefined, end_time: undefined };
  const now = new Date();
  const days = parseInt(timeRange.value.replace('d', ''));
  const start = new Date(now.getTime() - days * 86400000);
  return {
    start_time: start.toISOString(),
    end_time: now.toISOString(),
  };
}

function handleExport() {
  const params = new URLSearchParams();
  if (selectedAgent.value) params.set('agent_id', selectedAgent.value);
  if (selectedTypes.value.length > 0) params.set('type', selectedTypes.value.join(','));
  const { start_time, end_time } = getTimeRange();
  if (start_time) params.set('start_time', start_time);
  if (end_time) params.set('end_time', end_time);
  window.open(`/api/memory/events/export?${params.toString()}`, '_blank');
}

onMounted(() => {
  loadStats();
  refreshEvents();
});
</script>
