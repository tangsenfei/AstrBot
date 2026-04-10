<template>
  <v-container fluid class="pa-6">
    <v-card class="mb-6">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-brain" class="mr-2" />
        {{ t('nicebot.memory_management.title') }}
      </v-card-title>
      <v-card-subtitle>
        {{ t('nicebot.memory_management.description') }}
      </v-card-subtitle>
    </v-card>

    <v-card>
      <v-card-text>
        <v-tabs v-model="activeTab">
          <v-tab value="overview">{{ t('nicebot.memory_management.tabs.overview') }}</v-tab>
          <v-tab value="short_term">{{ t('nicebot.memory_management.tabs.short_term') }}</v-tab>
          <v-tab value="long_term">{{ t('nicebot.memory_management.tabs.long_term') }}</v-tab>
          <v-tab value="settings">{{ t('nicebot.memory_management.tabs.settings') }}</v-tab>
        </v-tabs>

        <v-window v-model="activeTab" class="mt-4">
          <v-window-item value="overview">
            <v-row>
              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <v-icon icon="mdi-clock-fast" size="48" color="primary" class="mb-2" />
                    <div class="text-h6">{{ t('nicebot.memory_management.stats.short_term') }}</div>
                    <div class="text-h4 text-primary">{{ shortTermCount }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <v-icon icon="mdi-database" size="48" color="success" class="mb-2" />
                    <div class="text-h6">{{ t('nicebot.memory_management.stats.long_term') }}</div>
                    <div class="text-h4 text-success">{{ longTermCount }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-text class="text-center">
                    <v-icon icon="mdi-account-group" size="48" color="info" class="mb-2" />
                    <div class="text-h6">{{ t('nicebot.memory_management.stats.users') }}</div>
                    <div class="text-h4 text-info">{{ userCount }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </v-window-item>

          <v-window-item value="short_term">
            <v-card variant="outlined">
              <v-card-title class="d-flex justify-space-between align-center">
                <span>{{ t('nicebot.memory_management.short_term.title') }}</span>
                <v-btn color="primary" variant="text" prepend-icon="mdi-refresh">
                  {{ t('nicebot.memory_management.actions.refresh') }}
                </v-btn>
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" class="mb-4">
                  {{ t('nicebot.memory_management.short_term.hint') }}
                </v-alert>
                <v-data-table
                  :headers="shortTermHeaders"
                  :items="shortTermMemories"
                  :loading="loading"
                >
                  <template v-slot:item.actions="{ item }">
                    <v-btn icon="mdi-eye" variant="text" size="small" />
                    <v-btn icon="mdi-delete" variant="text" size="small" color="error" />
                  </template>
                </v-data-table>
              </v-card-text>
            </v-card>
          </v-window-item>

          <v-window-item value="long_term">
            <v-card variant="outlined">
              <v-card-title class="d-flex justify-space-between align-center">
                <span>{{ t('nicebot.memory_management.long_term.title') }}</span>
                <div>
                  <v-btn color="primary" variant="text" prepend-icon="mdi-download">
                    {{ t('nicebot.memory_management.actions.export') }}
                  </v-btn>
                  <v-btn color="primary" variant="text" prepend-icon="mdi-upload">
                    {{ t('nicebot.memory_management.actions.import') }}
                  </v-btn>
                </div>
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" class="mb-4">
                  {{ t('nicebot.memory_management.long_term.hint') }}
                </v-alert>
                <v-data-table
                  :headers="longTermHeaders"
                  :items="longTermMemories"
                  :loading="loading"
                >
                  <template v-slot:item.actions="{ item }">
                    <v-btn icon="mdi-eye" variant="text" size="small" />
                    <v-btn icon="mdi-pencil" variant="text" size="small" />
                    <v-btn icon="mdi-delete" variant="text" size="small" color="error" />
                  </template>
                </v-data-table>
              </v-card-text>
            </v-card>
          </v-window-item>

          <v-window-item value="settings">
            <v-card variant="outlined">
              <v-card-title>{{ t('nicebot.memory_management.settings.title') }}</v-card-title>
              <v-card-text>
                <v-switch
                  v-model="settings.enabled"
                  :label="t('nicebot.memory_management.settings.enabled')"
                  color="primary"
                />
                <v-slider
                  v-model="settings.maxShortTerm"
                  :label="t('nicebot.memory_management.settings.max_short_term')"
                  :min="5"
                  :max="50"
                  :step="5"
                  thumb-label
                  class="mb-4"
                />
                <v-slider
                  v-model="settings.maxLongTerm"
                  :label="t('nicebot.memory_management.settings.max_long_term')"
                  :min="100"
                  :max="1000"
                  :step="100"
                  thumb-label
                  class="mb-4"
                />
                <v-text-field
                  v-model="settings.retentionDays"
                  :label="t('nicebot.memory_management.settings.retention_days')"
                  type="number"
                  :min="1"
                  :max="365"
                />
                <v-btn color="primary" class="mt-4">
                  {{ t('nicebot.memory_management.actions.save') }}
                </v-btn>
              </v-card-text>
            </v-card>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const activeTab = ref('overview');
const loading = ref(false);

const shortTermCount = ref(0);
const longTermCount = ref(0);
const userCount = ref(0);

const settings = reactive({
  enabled: true,
  maxShortTerm: 20,
  maxLongTerm: 500,
  retentionDays: 30
});

const shortTermHeaders = [
  { title: 'ID', key: 'id' },
  { title: t('nicebot.memory_management.table.user'), key: 'user' },
  { title: t('nicebot.memory_management.table.content'), key: 'content' },
  { title: t('nicebot.memory_management.table.created'), key: 'createdAt' },
  { title: t('nicebot.memory_management.table.actions'), key: 'actions', sortable: false }
];

const longTermHeaders = [
  { title: 'ID', key: 'id' },
  { title: t('nicebot.memory_management.table.user'), key: 'user' },
  { title: t('nicebot.memory_management.table.category'), key: 'category' },
  { title: t('nicebot.memory_management.table.content'), key: 'content' },
  { title: t('nicebot.memory_management.table.created'), key: 'createdAt' },
  { title: t('nicebot.memory_management.table.actions'), key: 'actions', sortable: false }
];

const shortTermMemories = ref([]);
const longTermMemories = ref([]);
</script>
