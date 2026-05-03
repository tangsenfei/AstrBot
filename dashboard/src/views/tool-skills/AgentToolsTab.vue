<template>
  <v-card-text class="pa-4">
    <v-row class="mb-4" align="center">
      <v-col cols="12" md="8">
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="all">{{ $t('agent.tools.tabs.all') }}</v-tab>
          <v-tab value="builtin">{{ $t('agent.tools.tabs.builtin') }}</v-tab>
          <v-tab value="mcp">{{ $t('agent.tools.tabs.mcp') }}</v-tab>
          <v-tab value="custom">{{ $t('agent.tools.tabs.custom') }}</v-tab>
          <v-tab value="api_wrapper">{{ $t('agent.tools.tabs.apiWrapper') }}</v-tab>
        </v-tabs>
      </v-col>
      <v-col cols="12" md="4" class="d-flex align-center" style="gap: 8px;">
        <v-text-field
          v-model="searchQuery"
          :placeholder="$t('agent.tools.search.placeholder')"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          class="flex-grow-1"
        />
        <v-btn color="primary" @click="openAddEditor">
          <v-icon start icon="mdi-plus" />
          {{ $t('agent.tools.buttons.add') }}
        </v-btn>
        <v-btn variant="outlined" @click="loadTools" :loading="loading">
          <v-icon start icon="mdi-refresh" />
        </v-btn>
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn variant="outlined" v-bind="props" icon>
              <v-icon icon="mdi-dots-vertical" />
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="importTools">
              <template v-slot:prepend>
                <v-icon icon="mdi-import" />
              </template>
              <v-list-item-title>{{ $t('agent.tools.buttons.import') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="exportTools">
              <template v-slot:prepend>
                <v-icon icon="mdi-export" />
              </template>
              <v-list-item-title>{{ $t('agent.tools.buttons.export') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </v-col>
    </v-row>

    <v-card-text v-if="loading" class="text-center py-8">
      <v-progress-circular indeterminate color="primary" />
      <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
    </v-card-text>

    <v-card-text v-else-if="filteredTools.length === 0" class="text-center py-8">
      <v-icon icon="mdi-tools" size="60" color="grey-lighten-1" class="mb-4" />
      <p class="text-grey">{{ $t('agent.tools.empty') }}</p>
    </v-card-text>

    <v-container fluid v-else class="pa-0">
      <v-row>
        <v-col
          v-for="tool in filteredTools"
          :key="tool.name"
          cols="12"
          sm="6"
          md="4"
          lg="3"
        >
          <ToolCard
            :tool="tool"
            @edit="openEditor"
            @test="openTester"
            @delete="deleteTool"
            @toggle="toggleTool"
          />
        </v-col>
      </v-row>
    </v-container>

    <ToolEditor
      v-model="showEditor"
      :tool="editingTool"
      :is-editing="isEditing"
      @save="handleSaveTool"
    />

    <ToolTester
      v-model="showTester"
      :tool="testingTool"
    />

    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ $t('agent.tools.import.title') }}</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="importFile"
            :label="$t('agent.tools.import.selectFile')"
            accept=".json"
            prepend-icon="mdi-file-json"
            show-size
          />
          <v-alert type="info" variant="tonal" class="mt-4">
            {{ $t('agent.tools.import.hint') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">
            {{ $t('agent.tools.import.button') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ $t('agent.tools.delete.title') }}</v-card-title>
        <v-card-text>
          {{ $t('agent.tools.delete.confirm', { name: deletingTool?.name }) }}
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
  </v-card-text>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import ToolCard from '../agent/tools/ToolCard.vue';
import ToolEditor from '../agent/tools/ToolEditor.vue';
import ToolTester from '../agent/tools/ToolTester.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const loading = ref(false);
const tools = ref<any[]>([]);
const activeTab = ref('all');
const searchQuery = ref('');

const showEditor = ref(false);
const editingTool = ref<any>(null);
const isEditing = ref(false);

const showTester = ref(false);
const testingTool = ref<any>(null);

const showDeleteDialog = ref(false);
const deletingTool = ref<any>(null);
const deleting = ref(false);

const showImportDialog = ref(false);
const importFile = ref<File | null>(null);
const importing = ref(false);

const filteredTools = computed(() => {
  let result = tools.value;
  if (activeTab.value !== 'all') {
    result = result.filter(tool => tool.source === activeTab.value);
  }
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(tool =>
      tool.name.toLowerCase().includes(query) ||
      (tool.description && tool.description.toLowerCase().includes(query))
    );
  }
  return result;
});

async function loadTools() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/tools');
    if (response.data.status === 'ok') {
      tools.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load tools:', error);
  } finally {
    loading.value = false;
  }
}

function openAddEditor() {
  editingTool.value = null;
  isEditing.value = false;
  showEditor.value = true;
}

function openEditor(tool: any) {
  editingTool.value = { ...tool };
  isEditing.value = true;
  showEditor.value = true;
}

function openTester(tool: any) {
  testingTool.value = tool;
  showTester.value = true;
}

function deleteTool(tool: any) {
  deletingTool.value = tool;
  showDeleteDialog.value = true;
}

async function confirmDelete() {
  if (!deletingTool.value) return;
  deleting.value = true;
  try {
    await axios.post('/api/plug/agent/tools/delete', {
      name: deletingTool.value.name,
    });
    tools.value = tools.value.filter(t => t.name !== deletingTool.value.name);
    showDeleteDialog.value = false;
    deletingTool.value = null;
  } catch (error: any) {
    console.error('Failed to delete tool:', error);
    alert(error.response?.data?.message || t('agent.tools.messages.deleteError'));
  } finally {
    deleting.value = false;
  }
}

async function toggleTool(tool: any) {
  try {
    await axios.post('/api/plug/agent/tools/toggle', {
      name: tool.name,
      enabled: tool.enabled,
    });
  } catch (error) {
    console.error('Failed to toggle tool:', error);
    tool.enabled = !tool.enabled;
  }
}

async function handleSaveTool(toolData: any) {
  try {
    if (isEditing.value) {
      await axios.post('/api/plug/agent/tools/update', toolData);
    } else {
      await axios.post('/api/plug/agent/tools/add', toolData);
    }
    showEditor.value = false;
    await loadTools();
  } catch (error: any) {
    console.error('Failed to save tool:', error);
    throw error;
  }
}

function importTools() {
  importFile.value = null;
  showImportDialog.value = true;
}

async function executeImport() {
  if (!importFile.value) return;
  importing.value = true;
  try {
    const text = await importFile.value.text();
    const data = JSON.parse(text);
    await axios.post('/api/plug/agent/tools/import', { tools: data });
    showImportDialog.value = false;
    await loadTools();
  } catch (error: any) {
    console.error('Failed to import tools:', error);
    alert(error.response?.data?.message || t('agent.tools.messages.importError'));
  } finally {
    importing.value = false;
  }
}

function exportTools() {
  const data = JSON.stringify(tools.value, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `tools_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(() => {
  loadTools();
});
</script>
