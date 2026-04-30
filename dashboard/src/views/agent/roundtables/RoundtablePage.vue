<template>
  <v-container fluid class="pa-6">
    <!-- 页面标题 -->
    <v-row>
      <v-col cols="12">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-table-chair" class="mr-2" />
            {{ $t('agent.roundtables.title') }}
            <v-spacer />
            <v-btn color="primary" @click="openAddEditor" class="mr-2">
              <v-icon start icon="mdi-plus" />
              {{ $t('agent.roundtables.buttons.add') }}
            </v-btn>
            <v-text-field
              v-model="searchQuery"
              :placeholder="$t('agent.roundtables.search.placeholder')"
              prepend-inner-icon="mdi-magnify"
              variant="outlined"
              density="compact"
              hide-details
              clearable
              class="mr-2"
              style="max-width: 240px;"
            />
            <v-btn variant="outlined" @click="loadRoundtables" :loading="loading">
              <v-icon start icon="mdi-refresh" />
              {{ $t('agent.roundtables.buttons.refresh') }}
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            {{ $t('agent.roundtables.subtitle') }}
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <!-- 筛选标签 -->
    <v-row>
      <v-col cols="12">
        <v-card class="mb-4">
          <v-card-text class="pb-2">
            <v-tabs v-model="activeTab" color="primary">
              <v-tab value="all">{{ $t('agent.roundtables.tabs.all') }}</v-tab>
              <v-tab value="pending">{{ $t('agent.roundtables.tabs.pending') }}</v-tab>
              <v-tab value="running">{{ $t('agent.roundtables.tabs.running') }}</v-tab>
              <v-tab value="completed">{{ $t('agent.roundtables.tabs.completed') }}</v-tab>
              <v-tab value="failed">{{ $t('agent.roundtables.tabs.failed') }}</v-tab>
            </v-tabs>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 会议类型筛选 -->
    <v-row>
      <v-col cols="12">
        <v-chip-group v-model="selectedMeetingType" class="mb-4">
          <v-chip filter value="">全部类型</v-chip>
          <v-chip filter value="standard">标准研讨</v-chip>
          <v-chip filter value="brainstorm">头脑风暴</v-chip>
          <v-chip filter value="parliament">议会投票</v-chip>
          <v-chip filter value="convergence">方案收敛</v-chip>
          <v-chip filter value="six_hat">六顶思考帽</v-chip>
          <v-chip filter value="fishbone">鱼骨图分析</v-chip>
          <v-chip filter value="swot">SWOT分析</v-chip>
          <v-chip filter value="okr">OKR拆解会</v-chip>
          <v-chip filter value="retrospective">项目复盘</v-chip>
          <v-chip filter value="interview">模拟面试</v-chip>
        </v-chip-group>
      </v-col>
    </v-row>

    <!-- 圆桌会议列表 -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-text v-if="loading" class="text-center py-8">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
          </v-card-text>

          <v-card-text v-else-if="filteredRoundtables.length === 0" class="text-center py-8">
            <v-icon icon="mdi-table-chair" size="60" color="grey-lighten-1" class="mb-4" />
            <p class="text-grey">{{ $t('agent.roundtables.empty') }}</p>
          </v-card-text>

          <v-data-table
            v-else
            :items="filteredRoundtables"
            :headers="headers"
            class="roundtable-table"
          >
            <template v-slot:item.name="{ item }">
              <div class="font-weight-medium">{{ item.name }}</div>
            </template>

            <template v-slot:item.topic="{ item }">
              <div class="text-truncate" style="max-width: 200px;" :title="item.topic">
                {{ item.topic }}
              </div>
            </template>

            <template v-slot:item.meeting_type="{ item }">
              <v-chip
                :color="getMeetingTypeColor(item.meeting_type)"
                size="small"
                variant="tonal"
              >
                <v-icon start :icon="getMeetingTypeIcon(item.meeting_type)" size="small" />
                {{ getMeetingTypeName(item.meeting_type) }}
              </v-chip>
            </template>

            <template v-slot:item.mode="{ item }">
              <v-chip
                :color="item.has_moderator ? 'warning' : 'primary'"
                size="small"
                variant="tonal"
              >
                <v-icon start :icon="item.has_moderator ? 'mdi-account-tie' : 'mdi-account-group'" size="small" />
                {{ item.has_moderator ? $t('agent.roundtables.mode.moderated') : $t('agent.roundtables.mode.free') }}
              </v-chip>
            </template>

            <template v-slot:item.rounds="{ item }">
              <v-chip size="small" color="info" variant="flat">
                <v-icon start icon="mdi-rotate-right" size="small" />
                {{ item.rounds }}
              </v-chip>
            </template>

            <template v-slot:item.status="{ item }">
              <v-chip
                :color="getStatusColor(item.status)"
                size="small"
                variant="tonal"
              >
                <v-icon start :icon="getStatusIcon(item.status)" size="small" />
                {{ $t(`agent.roundtables.status.${item.status}`) }}
              </v-chip>
            </template>

            <template v-slot:item.created_at="{ item }">
              {{ formatDate(item.created_at) }}
            </template>

            <template v-slot:item.actions="{ item }">
              <div class="d-flex align-center">
                <v-btn
                  v-if="item.status === 'pending'"
                  icon
                  size="small"
                  variant="text"
                  color="success"
                  @click="executeRoundtable(item)"
                  :title="$t('agent.roundtables.actions.execute')"
                >
                  <v-icon icon="mdi-play" />
                </v-btn>
                <v-btn
                  v-if="item.status === 'running'"
                  icon
                  size="small"
                  variant="text"
                  color="info"
                  @click="viewResult(item)"
                  :title="$t('agent.roundtables.actions.viewProgress')"
                >
                  <v-icon icon="mdi-progress-clock" />
                </v-btn>
                <v-btn
                  v-if="item.status === 'completed'"
                  icon
                  size="small"
                  variant="text"
                  color="primary"
                  @click="viewResult(item)"
                  :title="$t('agent.roundtables.actions.viewResult')"
                >
                  <v-icon icon="mdi-file-document" />
                </v-btn>
                <v-btn
                  v-if="item.status === 'failed'"
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  @click="viewResult(item)"
                  :title="$t('agent.roundtables.actions.viewError')"
                >
                  <v-icon icon="mdi-alert-circle" />
                </v-btn>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  color="primary"
                  @click="openEditor(item)"
                  :title="$t('common.edit')"
                >
                  <v-icon icon="mdi-pencil" />
                </v-btn>
                <v-btn
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  @click="deleteRoundtable(item)"
                  :title="$t('common.delete')"
                >
                  <v-icon icon="mdi-delete" />
                </v-btn>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- 编辑弹窗 -->
    <RoundtableEditor
      v-model="showEditor"
      :roundtable="editingRoundtable"
      :is-editing="isEditing"
      @save="handleSaveRoundtable"
    />

    <!-- 确认删除对话框 -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ $t('agent.roundtables.delete.title') }}</v-card-title>
        <v-card-text>
          {{ $t('agent.roundtables.delete.confirm', { name: deletingRoundtable?.name }) }}
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
import { useRouter } from 'vue-router';
import axios from 'axios';
import RoundtableEditor from './RoundtableEditor.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const router = useRouter();

// 状态
const loading = ref(false);
const roundtables = ref<any[]>([]);
const activeTab = ref('all');
const searchQuery = ref('');
const selectedMeetingType = ref('');

// 编辑
const showEditor = ref(false);
const editingRoundtable = ref<any>(null);
const isEditing = ref(false);

// 删除
const showDeleteDialog = ref(false);
const deletingRoundtable = ref<any>(null);
const deleting = ref(false);

// 表格列
const headers = [
  { title: t('agent.roundtables.table.name'), key: 'name', sortable: true },
  { title: t('agent.roundtables.table.topic'), key: 'topic', sortable: true },
  { title: '会议类型', key: 'meeting_type', sortable: true },
  { title: t('agent.roundtables.table.mode'), key: 'mode', sortable: true },
  { title: t('agent.roundtables.table.rounds'), key: 'rounds', sortable: true },
  { title: t('agent.roundtables.table.status'), key: 'status', sortable: true },
  { title: t('agent.roundtables.table.createdAt'), key: 'created_at', sortable: true },
  { title: t('agent.roundtables.table.actions'), key: 'actions', sortable: false, align: 'end' as const },
];

// 计算属性
const filteredRoundtables = computed(() => {
  let result = roundtables.value;

  // 状态筛选
  if (activeTab.value !== 'all') {
    result = result.filter(rt => rt.status === activeTab.value);
  }

  // 会议类型筛选
  if (selectedMeetingType.value) {
    result = result.filter(rt => rt.meeting_type === selectedMeetingType.value);
  }

  // 按搜索词筛选
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(rt =>
      rt.name?.toLowerCase().includes(query) ||
      rt.topic?.toLowerCase().includes(query)
    );
  }

  return result;
});

// 加载圆桌会议列表
async function loadRoundtables() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/agent/roundtables');
    if (response.data.status === 'ok') {
      roundtables.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load roundtables:', error);
  } finally {
    loading.value = false;
  }
}

// 打开添加编辑器
function openAddEditor() {
  editingRoundtable.value = null;
  isEditing.value = false;
  showEditor.value = true;
}

// 打开编辑器
function openEditor(roundtable: any) {
  editingRoundtable.value = { ...roundtable };
  isEditing.value = true;
  showEditor.value = true;
}

// 执行圆桌会议
async function executeRoundtable(roundtable: any) {
  try {
    const response = await axios.post(`/api/plug/agent/roundtables/${roundtable.id}/execute`, {});
    if (response.data.status === 'ok') {
      await loadRoundtables();
      // 执行已启动，跳转到执行页面
      router.push(`/roundtables/${roundtable.id}/execution`);
    } else {
      alert(response.data.message || t('agent.roundtables.messages.executionError'));
    }
  } catch (error: any) {
    console.error('Failed to execute roundtable:', error);
    alert(error.response?.data?.message || t('agent.roundtables.messages.executionError'));
  }
}

// 查看结果
function viewResult(roundtable: any) {
  router.push(`/roundtables/${roundtable.id}/execution`);
}

// 删除圆桌会议
function deleteRoundtable(roundtable: any) {
  deletingRoundtable.value = roundtable;
  showDeleteDialog.value = true;
}

// 确认删除
async function confirmDelete() {
  if (!deletingRoundtable.value) return;

  deleting.value = true;
  try {
    await axios.post('/api/plug/agent/roundtables/delete', {
      id: deletingRoundtable.value.id,
    });
    roundtables.value = roundtables.value.filter(rt => rt.id !== deletingRoundtable.value.id);
    showDeleteDialog.value = false;
    deletingRoundtable.value = null;
  } catch (error: any) {
    console.error('Failed to delete roundtable:', error);
    alert(error.response?.data?.message || t('agent.roundtables.messages.deleteError'));
  } finally {
    deleting.value = false;
  }
}

// 保存圆桌会议
async function handleSaveRoundtable(roundtableData: any) {
  try {
    if (isEditing.value) {
      await axios.post('/api/plug/agent/roundtables/update', roundtableData);
    } else {
      await axios.post('/api/plug/agent/roundtables/add', roundtableData);
    }
    showEditor.value = false;
    await loadRoundtables();
  } catch (error: any) {
    console.error('Failed to save roundtable:', error);
    throw error;
  }
}

// 获取状态颜色
function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'grey',
    running: 'info',
    completed: 'success',
    failed: 'error',
  };
  return colors[status] || 'grey';
}

// 获取状态图标
function getStatusIcon(status: string): string {
  const icons: Record<string, string> = {
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    completed: 'mdi-check-circle',
    failed: 'mdi-alert-circle',
  };
  return icons[status] || 'mdi-help-circle';
}

// 格式化日期
function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString();
}

// 会议类型名称
function getMeetingTypeName(type: string): string {
  const names: Record<string, string> = {
    standard: '标准研讨',
    brainstorm: '头脑风暴',
    parliament: '议会投票',
    convergence: '方案收敛',
    six_hat: '六顶思考帽',
    fishbone: '鱼骨图分析',
    swot: 'SWOT分析',
    okr: 'OKR拆解会',
    retrospective: '项目复盘',
    interview: '模拟面试',
  };
  return names[type] || type;
}

// 会议类型颜色
function getMeetingTypeColor(type: string): string {
  const colors: Record<string, string> = {
    standard: 'primary',
    brainstorm: 'success',
    parliament: 'warning',
    convergence: 'info',
    six_hat: 'purple',
    fishbone: 'teal',
    swot: 'orange',
    okr: 'deep-purple',
    retrospective: 'indigo',
    interview: 'pink',
  };
  return colors[type] || 'grey';
}

// 会议类型图标
function getMeetingTypeIcon(type: string): string {
  const icons: Record<string, string> = {
    standard: 'mdi-forum',
    brainstorm: 'mdi-lightbulb',
    parliament: 'mdi-vote',
    convergence: 'mdi-target',
    six_hat: 'mdi-hat-fedora',
    fishbone: 'mdi-fish',
    swot: 'mdi-chart-box',
    okr: 'mdi-bullseye-arrow',
    retrospective: 'mdi-history',
    interview: 'mdi-account-question',
  };
  return icons[type] || 'mdi-help-circle';
}

onMounted(() => {
  loadRoundtables();
});
</script>

<style scoped>
.v-card {
  border-radius: 12px;
}

.roundtable-table :deep(.v-data-table__tr) {
  cursor: default;
}
</style>
