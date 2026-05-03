<template>
  <v-card-text class="pa-4">
    <v-row class="mb-4" align="center">
      <v-col cols="12" md="8">
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="all">{{ $t('agent.skills.tabs.all') }}</v-tab>
          <v-tab value="builtin">{{ $t('agent.skills.tabs.builtin') }}</v-tab>
          <v-tab value="astrbot">{{ $t('agent.skills.tabs.astrbot') }}</v-tab>
          <v-tab value="claudcode">{{ $t('agent.skills.tabs.claudcode') }}</v-tab>
          <v-tab value="crewai">{{ $t('agent.skills.tabs.crewai') }}</v-tab>
          <v-tab value="custom">{{ $t('agent.skills.tabs.custom') }}</v-tab>
        </v-tabs>
      </v-col>
      <v-col cols="12" md="4" class="d-flex align-center" style="gap: 8px;">
        <v-text-field
          v-model="searchQuery"
          :placeholder="$t('agent.skills.search.placeholder')"
          prepend-inner-icon="mdi-magnify"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          class="flex-grow-1"
        />
        <v-btn color="primary" @click="openAddEditor">
          <v-icon start icon="mdi-plus" />
          {{ $t('agent.skills.buttons.add') }}
        </v-btn>
        <v-btn variant="outlined" @click="refreshAll" :loading="loading">
          <v-icon start icon="mdi-refresh" />
        </v-btn>
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn variant="outlined" v-bind="props" icon>
              <v-icon icon="mdi-dots-vertical" />
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="importSkills">
              <template v-slot:prepend>
                <v-icon icon="mdi-import" />
              </template>
              <v-list-item-title>{{ $t('agent.skills.buttons.import') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="exportSkills">
              <template v-slot:prepend>
                <v-icon icon="mdi-export" />
              </template>
              <v-list-item-title>{{ $t('agent.skills.buttons.export') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </v-col>
    </v-row>

    <v-card-text v-if="loading" class="text-center py-8">
      <v-progress-circular indeterminate color="primary" />
      <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
    </v-card-text>

    <v-card-text v-else-if="filteredSkills.length === 0" class="text-center py-8">
      <v-icon icon="mdi-lightning-bolt" size="60" color="grey-lighten-1" class="mb-4" />
      <p class="text-grey">{{ $t('agent.skills.empty') }}</p>
    </v-card-text>

    <v-container fluid v-else class="pa-0">
      <v-row>
        <v-col
          v-for="skill in filteredSkills"
          :key="skill.name"
          cols="12"
          sm="6"
          md="4"
          lg="3"
        >
          <SkillCard
            :skill="skill"
            @edit="openEditor"
            @test="openTester"
            @delete="deleteSkill"
            @viewDetail="openSkillDetail"
          />
        </v-col>
      </v-row>
    </v-container>

    <SkillEditor
      v-model="showEditor"
      :skill="editingSkill"
      :is-editing="isEditing"
      :tools="availableTools"
      @save="handleSaveSkill"
    />

    <v-dialog v-model="showTester" max-width="800">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-bug-play" class="mr-2" />
          {{ $t('agent.skills.card.test') }}: {{ testingSkill?.name }}
          <v-spacer />
          <v-btn icon variant="text" @click="showTester = false">
            <v-icon icon="mdi-close" />
          </v-btn>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-alert type="info" variant="tonal" class="mb-4">
            {{ $t('agent.skills.card.test') }}功能开发中...
          </v-alert>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ $t('agent.skills.import.title') }}</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="importFile"
            :label="$t('agent.skills.import.selectFile')"
            accept=".json"
            prepend-icon="mdi-file-json"
            show-size
          />
          <v-alert type="info" variant="tonal" class="mt-4">
            {{ $t('agent.skills.import.hint') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">
            {{ $t('agent.skills.import.button') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ $t('agent.skills.delete.title') }}</v-card-title>
        <v-card-text>
          {{ $t('agent.skills.delete.confirm', { name: deletingSkill?.name }) }}
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

    <v-dialog v-model="showDetailDialog" max-width="700">
      <v-card v-if="detailSkill">
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-lightning-bolt" class="mr-2" color="primary" />
          {{ detailSkill.name }}
          <v-chip size="small" :color="detailSourceColor" variant="flat" class="ml-3">
            {{ detailSourceLabel }}
          </v-chip>
          <v-chip v-if="detailSkill.version" size="small" variant="outlined" class="ml-2">
            v{{ detailSkill.version }}
          </v-chip>
          <v-spacer />
          <v-btn icon variant="text" @click="showDetailDialog = false">
            <v-icon icon="mdi-close" />
          </v-btn>
        </v-card-title>
        <v-divider />

        <v-card-text class="pa-4">
          <div class="mb-4">
            <div class="text-subtitle-2 mb-1">描述</div>
            <p class="text-body-2">{{ detailSkill.description || '暂无描述' }}</p>
          </div>

          <div v-if="detailSkill.disclosure_level" class="mb-4">
            <div class="text-subtitle-2 mb-1">{{ $t('agent.skills.card.disclosureLevel') }}</div>
            <v-chip size="small" :color="detailDisclosureColor">
              {{ $t(`agent.skills.disclosureLevels.${detailSkill.disclosure_level}`) || detailSkill.disclosure_level }}
            </v-chip>
          </div>

          <div v-if="detailSkill.preapproved_tools && detailSkill.preapproved_tools.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.editor.preapprovedTools') }}</div>
            <v-chip
              v-for="tool in detailSkill.preapproved_tools"
              :key="tool"
              size="small"
              color="success"
              variant="tonal"
              class="mr-1 mb-1"
            >
              <v-icon icon="mdi-check" start size="x-small" />
              {{ tool }}
            </v-chip>
          </div>

          <div v-if="detailSkill.workflow && detailSkill.workflow.steps && detailSkill.workflow.steps.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.card.workflow') }}</div>
            <v-timeline density="compact" side="end">
              <v-timeline-item
                v-for="(step, index) in detailSkill.workflow.steps"
                :key="index"
                size="small"
              >
                <template v-slot:opposite>
                  <span class="text-caption text-grey">{{ index + 1 }}</span>
                </template>
                <div class="text-body-2 font-weight-medium">{{ step.name }}</div>
                <div v-if="step.description" class="text-caption text-grey">{{ step.description }}</div>
              </v-timeline-item>
            </v-timeline>
          </div>

          <div v-if="detailSkill.tags && detailSkill.tags.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">标签</div>
            <v-chip
              v-for="tag in detailSkill.tags"
              :key="tag"
              size="small"
              variant="outlined"
              class="mr-1 mb-1"
            >
              {{ tag }}
            </v-chip>
          </div>

          <div v-if="detailSkill.metadata && Object.keys(detailSkill.metadata).length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.editor.metadata') }}</div>
            <v-table density="compact" class="bg-grey-lighten-4">
              <tbody>
                <tr v-for="(value, key) in detailSkill.metadata" :key="key">
                  <td class="text-caption font-weight-medium">{{ key }}</td>
                  <td class="text-caption">{{ value }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>
        </v-card-text>

        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="outlined" @click="showDetailDialog = false">
            {{ $t('common.close') }}
          </v-btn>
          <v-btn
            v-if="detailSkill.source !== 'builtin'"
            color="primary"
            @click="showDetailDialog = false; openEditor(detailSkill)"
          >
            <v-icon start icon="mdi-pencil" />
            {{ $t('agent.skills.card.edit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card-text>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';
import SkillCard from '../agent/skills/SkillCard.vue';
import SkillEditor from '../agent/skills/SkillEditor.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const loading = ref(false);
const skills = ref<any[]>([]);
const builtinSkills = ref<any[]>([]);
const availableTools = ref<any[]>([]);
const activeTab = ref('all');
const searchQuery = ref('');

const showEditor = ref(false);
const editingSkill = ref<any>(null);
const isEditing = ref(false);

const showTester = ref(false);
const testingSkill = ref<any>(null);

const showDeleteDialog = ref(false);
const deletingSkill = ref<any>(null);
const deleting = ref(false);

const showImportDialog = ref(false);
const importFile = ref<File | null>(null);
const importing = ref(false);

const showDetailDialog = ref(false);
const detailSkill = ref<any>(null);

const filteredSkills = computed(() => {
  const builtinIds = new Set(builtinSkills.value.map(s => s.id));
  let result = [
    ...skills.value,
    ...builtinSkills.value.filter(bs => !skills.value.some(s => s.id === bs.id)),
  ];
  if (activeTab.value !== 'all') {
    result = result.filter(skill => skill.source === activeTab.value);
  }
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(skill =>
      skill.name.toLowerCase().includes(query) ||
      (skill.description && skill.description.toLowerCase().includes(query))
    );
  }
  return result;
});

const detailSourceColor = computed(() => {
  if (!detailSkill.value) return 'grey';
  switch (detailSkill.value.source) {
    case 'builtin': return 'secondary';
    case 'astrbot': return 'primary';
    case 'claudcode': return 'success';
    case 'crewai': return 'warning';
    default: return 'grey';
  }
});

const detailSourceLabel = computed(() => {
  if (!detailSkill.value) return '';
  return t(`agent.skills.sources.${detailSkill.value.source}`) || detailSkill.value.source;
});

const detailDisclosureColor = computed(() => {
  if (!detailSkill.value) return 'grey';
  switch (detailSkill.value.disclosure_level) {
    case 'metadata': return 'grey';
    case 'instructions': return 'warning';
    case 'resources': return 'success';
    default: return 'grey';
  }
});

async function loadSkills() {
  try {
    const response = await axios.get('/api/plug/agent/skills');
    if (response.data.status === 'ok') {
      skills.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load skills:', error);
  }
}

async function loadBuiltinSkills() {
  try {
    const response = await axios.get('/api/plug/agent/skills/builtin');
    if (response.data.status === 'ok') {
      builtinSkills.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load builtin skills:', error);
  }
}

async function refreshAll() {
  loading.value = true;
  try {
    await Promise.all([loadSkills(), loadBuiltinSkills()]);
  } finally {
    loading.value = false;
  }
}

async function loadAvailableTools() {
  try {
    const response = await axios.get('/api/plug/agent/tools');
    if (response.data.status === 'ok') {
      availableTools.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load tools:', error);
  }
}

function openAddEditor() {
  editingSkill.value = null;
  isEditing.value = false;
  showEditor.value = true;
}

function openEditor(skill: any) {
  editingSkill.value = { ...skill };
  isEditing.value = true;
  showEditor.value = true;
}

function openTester(skill: any) {
  testingSkill.value = skill;
  showTester.value = true;
}

async function openSkillDetail(skill: any) {
  detailSkill.value = skill;
  showDetailDialog.value = true;

  try {
    const skillId = skill.id || skill.name;
    const response = await axios.get(`/api/plug/agent/skills/${encodeURIComponent(skillId)}`);
    if (response.data.status === 'ok' && response.data.data) {
      detailSkill.value = { ...skill, ...response.data.data };
    }
  } catch (error) {
    console.error('Failed to load skill detail:', error);
  }
}

function deleteSkill(skill: any) {
  deletingSkill.value = skill;
  showDeleteDialog.value = true;
}

async function confirmDelete() {
  if (!deletingSkill.value) return;
  deleting.value = true;
  try {
    await axios.post('/api/plug/agent/skills/delete', {
      name: deletingSkill.value.name,
    });
    skills.value = skills.value.filter(s => s.name !== deletingSkill.value.name);
    showDeleteDialog.value = false;
    deletingSkill.value = null;
  } catch (error: any) {
    console.error('Failed to delete skill:', error);
    alert(error.response?.data?.message || t('agent.skills.messages.deleteError'));
  } finally {
    deleting.value = false;
  }
}

async function handleSaveSkill(skillData: any) {
  try {
    if (isEditing.value) {
      await axios.post('/api/plug/agent/skills/update', skillData);
    } else {
      await axios.post('/api/plug/agent/skills/add', skillData);
    }
    showEditor.value = false;
    await loadSkills();
  } catch (error: any) {
    console.error('Failed to save skill:', error);
    throw error;
  }
}

function importSkills() {
  importFile.value = null;
  showImportDialog.value = true;
}

async function executeImport() {
  if (!importFile.value) return;
  importing.value = true;
  try {
    const text = await importFile.value.text();
    const data = JSON.parse(text);
    await axios.post('/api/plug/agent/skills/import', { skills: data });
    showImportDialog.value = false;
    await loadSkills();
  } catch (error: any) {
    console.error('Failed to import skills:', error);
    alert(error.response?.data?.message || t('agent.skills.messages.importError'));
  } finally {
    importing.value = false;
  }
}

function exportSkills() {
  const data = JSON.stringify(skills.value, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `skills_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(() => {
  refreshAll();
  loadAvailableTools();
});
</script>
