<template>
  <v-container fluid class="pa-6">
    <v-row>
      <v-col cols="12">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-account-group" class="mr-2" />
            {{ $t('agent.crews.title') }}
            <v-spacer />
            <v-btn color="primary" @click="openAddEditor" class="mr-2">
              <v-icon start icon="mdi-plus" />
              {{ $t('agent.crews.buttons.add') }}
            </v-btn>
            <v-btn variant="outlined" @click="loadCrews" :loading="loading" class="mr-2">
              <v-icon start icon="mdi-refresh" />
              {{ $t('agent.crews.buttons.refresh') }}
            </v-btn>
            <v-menu>
              <template v-slot:activator="{ props }">
                <v-btn variant="outlined" v-bind="props">
                  <v-icon start icon="mdi-dots-vertical" />
                  {{ $t('agent.crews.buttons.more') }}
                </v-btn>
              </template>
              <v-list>
                <v-list-item @click="importCrews">
                  <template v-slot:prepend>
                    <v-icon icon="mdi-import" />
                  </template>
                  <v-list-item-title>{{ $t('agent.crews.buttons.import') }}</v-list-item-title>
                </v-list-item>
                <v-list-item @click="exportCrews">
                  <template v-slot:prepend>
                    <v-icon icon="mdi-export" />
                  </template>
                  <v-list-item-title>{{ $t('agent.crews.buttons.export') }}</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </v-card-title>
          <v-card-subtitle>
            {{ $t('agent.crews.subtitle') }}
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-text class="pb-2">
            <v-row align="center">
              <v-col cols="12" md="8">
                <v-tabs v-model="activeTab" color="primary">
                  <v-tab value="all">{{ $t('agent.crews.tabs.all') }}</v-tab>
                  <v-tab value="sequential">{{ $t('agent.crews.tabs.sequential') }}</v-tab>
                  <v-tab value="hierarchical">{{ $t('agent.crews.tabs.hierarchical') }}</v-tab>
                </v-tabs>
              </v-col>
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="searchQuery"
                  :placeholder="$t('agent.crews.search.placeholder')"
                  prepend-inner-icon="mdi-magnify"
                  variant="outlined"
                  density="compact"
                  hide-details
                  clearable
                />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-text v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
          </v-card-text>

          <v-card-text v-else-if="filteredCrews.length === 0" class="text-center py-8">
            <v-icon icon="mdi-account-group" size="60" color="grey-lighten-1" class="mb-4" />
            <p class="text-grey">{{ $t('agent.crews.empty') }}</p>
          </v-card-text>

          <v-container fluid v-else>
            <v-row>
              <v-col
                v-for="crew in filteredCrews"
                :key="crew.name"
                cols="12"
                sm="6"
                md="4"
                lg="3"
              >
                <CrewCard
                  :crew="crew"
                  @edit="openEditor"
                  @copy="copyCrew"
                  @delete="deleteCrew"
                />
              </v-col>
            </v-row>
          </v-container>
        </v-card>
      </v-col>
    </v-row>

    <CrewEditor
      v-model="showEditor"
      :crew="editingCrew"
      :is-editing="isEditing"
      @save="handleSaveCrew"
    />

    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ $t('agent.crews.import.title') }}</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="importFile"
            :label="$t('agent.crews.import.selectFile')"
            accept=".json"
            prepend-icon="mdi-file-json"
            show-size
          />
          <v-alert type="info" variant="tonal" class="mt-4">
            {{ $t('agent.crews.import.hint') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">
            {{ $t('agent.crews.import.button') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ $t('agent.crews.delete.title') }}</v-card-title>
        <v-card-text>
          {{ $t('agent.crews.delete.confirm', { name: deletingCrew?.name }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showDeleteDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="error" @click="confirmDelete" :loading="deleting">
            {{ $t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import CrewCard from './CrewCard.vue';
import CrewEditor from './CrewEditor.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const loading = ref(false);
const crews = ref<any[]>([]);
const activeTab = ref('all');
const searchQuery = ref('');

const showEditor = ref(false);
const editingCrew = ref<any>(null);
const isEditing = ref(false);

const showDeleteDialog = ref(false);
const deletingCrew = ref<any>(null);
const deleting = ref(false);

const showImportDialog = ref(false);
const importFile = ref<File | null>(null);
const importing = ref(false);

const filteredCrews = computed(() => {
  let result = crews.value;
  if (activeTab.value === 'sequential') {
    result = result.filter(crew => crew.process === 'sequential');
  } else if (activeTab.value === 'hierarchical') {
    result = result.filter(crew => crew.process === 'hierarchical');
  }
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(crew =>
      crew.name.toLowerCase().includes(query) ||
      (crew.description && crew.description.toLowerCase().includes(query))
    );
  }
  return result;
});

async function loadCrews() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/crews');
    if (response.data.status === 'ok') {
      crews.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load crews:', error);
  } finally {
    loading.value = false;
  }
}

function openAddEditor() {
  editingCrew.value = null;
  isEditing.value = false;
  showEditor.value = true;
}

function openEditor(crew: any) {
  editingCrew.value = { ...crew };
  isEditing.value = true;
  showEditor.value = true;
}

async function copyCrew(crew: any) {
  const newCrew = { ...crew, name: `${crew.name}_copy` };
  delete (newCrew as any).id;
  try {
    await axios.post('/api/plug/agent/crews/add', newCrew);
    await loadCrews();
  } catch (error: any) {
    console.error('Failed to copy crew:', error);
    alert(error.response?.data?.message || t('agent.crews.messages.copyError'));
  }
}

function deleteCrew(crew: any) {
  deletingCrew.value = crew;
  showDeleteDialog.value = true;
}

async function confirmDelete() {
  if (!deletingCrew.value) return;
  deleting.value = true;
  try {
    await axios.post('/api/plug/agent/crews/delete', { name: deletingCrew.value.name });
    crews.value = crews.value.filter(c => c.name !== deletingCrew.value.name);
    showDeleteDialog.value = false;
    deletingCrew.value = null;
  } catch (error: any) {
    console.error('Failed to delete crew:', error);
    alert(error.response?.data?.message || t('agent.crews.messages.deleteError'));
  } finally {
    deleting.value = false;
  }
}

async function handleSaveCrew(crewData: any) {
  try {
    if (isEditing.value) {
      await axios.post('/api/plug/agent/crews/update', crewData);
    } else {
      await axios.post('/api/plug/agent/crews/add', crewData);
    }
    showEditor.value = false;
    await loadCrews();
  } catch (error: any) {
    console.error('Failed to save crew:', error);
    throw error;
  }
}

function importCrews() {
  importFile.value = null;
  showImportDialog.value = true;
}

async function executeImport() {
  if (!importFile.value) return;
  importing.value = true;
  try {
    const text = await importFile.value.text();
    const data = JSON.parse(text);
    await axios.post('/api/plug/agent/crews/import', { crews: data });
    showImportDialog.value = false;
    await loadCrews();
  } catch (error: any) {
    console.error('Failed to import crews:', error);
    alert(error.response?.data?.message || t('agent.crews.messages.importError'));
  } finally {
    importing.value = false;
  }
}

function exportCrews() {
  const data = JSON.stringify(crews.value, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `crews_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(() => {
  loadCrews();
});
</script>

<style scoped>
.v-card {
  border-radius: 12px;
}
</style>
