<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-clipboard-list-outline" class="mr-2" />


            {{ $t('agent.tasks.title') }}


            <v-spacer />


            <v-btn variant="outlined" @click="loadTasks" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.tasks.buttons.refresh') }}


            </v-btn>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.tasks.subtitle') }}


          </v-card-subtitle>


        </v-card>


      </v-col>


    </v-row>





    <!-- 统计卡片 -->


    <v-row>


      <v-col cols="12" sm="6" md="3">


        <v-card class="mb-4">


          <v-card-text class="d-flex align-center">


            <v-avatar color="primary" size="48" class="mr-4">


              <v-icon icon="mdi-clipboard-text" color="white" />


            </v-avatar>


            <div>


              <div class="text-h4 font-weight-bold">{{ stats.total }}</div>


              <div class="text-body-2 text-grey">{{ $t('agent.tasks.stats.total') }}</div>


            </div>


          </v-card-text>


        </v-card>


      </v-col>


      <v-col cols="12" sm="6" md="3">


        <v-card class="mb-4">


          <v-card-text class="d-flex align-center">


            <v-avatar color="info" size="48" class="mr-4">


              <v-icon icon="mdi-progress-clock" color="white" />


            </v-avatar>


            <div>


              <div class="text-h4 font-weight-bold">{{ stats.running }}</div>


              <div class="text-body-2 text-grey">{{ $t('agent.tasks.stats.running') }}</div>


            </div>


          </v-card-text>


        </v-card>


      </v-col>


      <v-col cols="12" sm="6" md="3">


        <v-card class="mb-4">


          <v-card-text class="d-flex align-center">


            <v-avatar color="success" size="48" class="mr-4">


              <v-icon icon="mdi-check-circle" color="white" />


            </v-avatar>


            <div>


              <div class="text-h4 font-weight-bold">{{ stats.completed }}</div>


              <div class="text-body-2 text-grey">{{ $t('agent.tasks.stats.completed') }}</div>


            </div>


          </v-card-text>


        </v-card>


      </v-col>


      <v-col cols="12" sm="6" md="3">


        <v-card class="mb-4">


          <v-card-text class="d-flex align-center">


            <v-avatar color="warning" size="48" class="mr-4">


              <v-icon icon="mdi-token" color="white" />


            </v-avatar>


            <div>


              <div class="text-h4 font-weight-bold">{{ formatTokenCount(stats.todayTokens) }}</div>


              <div class="text-body-2 text-grey">{{ $t('agent.tasks.stats.todayTokens') }}</div>


            </div>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <!-- 筛选区域-->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-4">


          <v-card-text class="pb-2">


            <v-row align="center">


              <v-col cols="12" md="6">


                <v-tabs v-model="activeTab" color="primary">


                  <v-tab value="all">{{ $t('agent.tasks.tabs.all') }}</v-tab>


                  <v-tab value="pending">{{ $t('agent.tasks.tabs.pending') }}</v-tab>


                  <v-tab value="running">{{ $t('agent.tasks.tabs.running') }}</v-tab>


                  <v-tab value="paused">{{ $t('agent.tasks.tabs.paused') }}</v-tab>


                  <v-tab value="waiting_feedback">{{ $t('agent.tasks.tabs.waiting_feedback') }}</v-tab>


                  <v-tab value="completed">{{ $t('agent.tasks.tabs.completed') }}</v-tab>


                  <v-tab value="failed">{{ $t('agent.tasks.tabs.failed') }}</v-tab>


                  <v-tab value="cancelled">{{ $t('agent.tasks.tabs.cancelled') }}</v-tab>


                </v-tabs>


              </v-col>


              <v-col cols="12" md="3">


                <v-select


                  v-model="filterCrew"


                  :items="crewOptions"


                  :label="$t('agent.tasks.filter.crew')"


                  prepend-inner-icon="mdi-account-group"


                  variant="outlined"


                  density="compact"


                  hide-details


                  clearable


                />


              </v-col>


              <v-col cols="12" md="3">


                <v-select


                  v-model="filterTimeRange"


                  :items="timeRangeOptions"


                  :label="$t('agent.tasks.filter.timeRange')"


                  prepend-inner-icon="mdi-calendar"


                  variant="outlined"


                  density="compact"


                  hide-details


                />


              </v-col>


            </v-row>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <!-- 任务列表 -->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-data-table-server


            :headers="headers"


            :items="tasks"


            :items-length="totalItems"


            :loading="loading"


            :items-per-page="itemsPerPage"


            :page="currentPage"


            item-value="id"


            class="elevation-1"


            @update:page="handlePageChange"


            @update:items-per-page="handleItemsPerPageChange"


          >


            <template v-slot:item.name="{ item }">


              <div class="d-flex align-center py-2">


                <v-icon :icon="getTypeIcon(item.type)" class="mr-2" :color="getTypeColor(item.type)" />


                <div>


                  <div class="font-weight-medium">{{ item.name }}</div>


                  <div class="text-caption text-grey">{{ item.id }}</div>


                </div>


              </div>


            </template>





            <template v-slot:item.type="{ item }">


              <v-chip :color="getTypeColor(item.type)" size="small" variant="tonal">


                {{ $t(`agent.tasks.types.${item.type}`) }}


              </v-chip>


            </template>





            <template v-slot:item.status="{ item }">


              <v-chip :color="getStatusColor(item.status)" size="small" variant="tonal">


                <v-icon start :icon="getStatusIcon(item.status)" size="small" />


                {{ $t(`agent.tasks.status.${item.status}`) }}


              </v-chip>


            </template>





            <template v-slot:item.progress="{ item }">


              <div class="d-flex align-center" style="min-width: 120px">


                <v-progress-linear


                  :model-value="item.progress || 0"


                  :color="getProgressColor(item.status)"


                  height="6"


                  rounded


                  class="mr-2"


                />


                <span class="text-caption">{{ item.progress || 0 }}%</span>


              </div>


            </template>





            <template v-slot:item.tokenUsage="{ item }">


              <div class="text-body-2">


                <span class="font-weight-medium">{{ formatTokenCount(item.tokenUsage?.total || 0) }}</span>


                <span class="text-grey ml-1">


                  ({{ formatTokenCount(item.tokenUsage?.prompt || 0) }}/{{ formatTokenCount(item.tokenUsage?.completion || 0) }})


                </span>


              </div>


            </template>





            <template v-slot:item.createdAt="{ item }">


              <div class="text-body-2">


                {{ formatDate(item.createdAt) }}


              </div>


            </template>





            <template v-slot:item.actions="{ item }">


              <v-btn


                icon


                variant="text"


                size="small"


                @click="viewDetail(item)"


                class="mr-1"


              >


                <v-icon icon="mdi-eye" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.view') }}</v-tooltip>


              </v-btn>


              <v-btn


                v-if="item.status === 'running'"


                icon


                variant="text"


                size="small"


                color="warning"


                @click="pauseTask(item)"


                class="mr-1"


              >


                <v-icon icon="mdi-pause" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.pause') }}</v-tooltip>


              </v-btn>


              <v-btn


                v-if="item.status === 'paused'"


                icon


                variant="text"


                size="small"


                color="success"


                @click="resumeTask(item)"


                class="mr-1"


              >


                <v-icon icon="mdi-play" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.resume') }}</v-tooltip>


              </v-btn>


              <v-btn


                v-if="['running', 'paused', 'waiting_feedback'].includes(item.status)"


                icon


                variant="text"


                size="small"


                color="error"


                @click="cancelTask(item)"


                class="mr-1"


              >


                <v-icon icon="mdi-stop" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.cancel') }}</v-tooltip>


              </v-btn>


              <v-btn


                v-if="['failed', 'cancelled'].includes(item.status)"


                icon


                variant="text"


                size="small"


                color="info"


                @click="retryTask(item)"


                class="mr-1"


              >


                <v-icon icon="mdi-refresh" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.retry') }}</v-tooltip>


              </v-btn>


              <v-btn


                icon


                variant="text"


                size="small"


                color="error"


                @click="deleteTask(item)"


              >


                <v-icon icon="mdi-delete" />


                <v-tooltip activator="parent">{{ $t('agent.tasks.actions.delete') }}</v-tooltip>


              </v-btn>


            </template>





            <template v-slot:no-data>


              <div class="text-center py-8">


                <v-icon icon="mdi-clipboard-list-outline" size="60" color="grey-lighten-1" class="mb-4" />


                <p class="text-grey">{{ $t('agent.tasks.empty') }}</p>


              </div>


            </template>


          </v-data-table-server>


        </v-card>


      </v-col>


    </v-row>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.tasks.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.tasks.delete.confirm', { name: deletingTask?.name }) }}


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


import { ref, computed, onMounted, watch } from 'vue';


import { useRouter } from 'vue-router';


import axios from 'axios';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();


const router = useRouter();





// 状


const loading = ref(false);


const tasks = ref<any[]>([]);


const totalItems = ref(0);


const currentPage = ref(1);


const itemsPerPage = ref(10);


const activeTab = ref('all');


const filterCrew = ref<string | null>(null);


const filterTimeRange = ref('all');





// 统计数据


const stats = ref({


  total: 0,


  running: 0,


  completed: 0,


  todayTokens: 0


});





// Crew 选项


const crewOptions = ref<{ title: string; value: string }[]>([]);





// 时间范围选项


const timeRangeOptions = computed(() => [


  { title: t('agent.tasks.filter.timeRanges.all'), value: 'all' },


  { title: t('agent.tasks.filter.timeRanges.today'), value: 'today' },


  { title: t('agent.tasks.filter.timeRanges.week'), value: 'week' },


  { title: t('agent.tasks.filter.timeRanges.month'), value: 'month' }


]);





// 删除


const showDeleteDialog = ref(false);


const deletingTask = ref<any>(null);


const deleting = ref(false);





// 表头


const headers = computed(() => [


  { title: t('agent.tasks.table.name'), key: 'name', sortable: false },


  { title: t('agent.tasks.table.type'), key: 'type', sortable: false, width: 100 },


  { title: t('agent.tasks.table.status'), key: 'status', sortable: false, width: 120 },


  { title: t('agent.tasks.table.progress'), key: 'progress', sortable: false, width: 150 },


  { title: t('agent.tasks.table.tokenUsage'), key: 'tokenUsage', sortable: false, width: 180 },


  { title: t('agent.tasks.table.createdAt'), key: 'createdAt', sortable: false, width: 180 },


  { title: t('agent.tasks.table.actions'), key: 'actions', sortable: false, width: 200, align: 'end' as const }


]);





// 加载任务列表


async function loadTasks() {


  loading.value = true;


  try {


    const params: any = {


      page: currentPage.value,


      pageSize: itemsPerPage.value,


      status: activeTab.value === 'all'  ? undefined : activeTab.value,


      crew: filterCrew.value,


      timeRange: filterTimeRange.value


    };





    const response = await axios.get('/api/plug/agent/tasks', { params });


    if (response.data.status === 'ok') {


      tasks.value = response.data.data.items || [];


      totalItems.value = response.data.data.total || 0;


    }


  } catch (error) {


    console.error('Failed to load tasks:', error);


  } finally {


    loading.value = false;


  }


}





// 加载统计数据


async function loadStats() {


  try {


    const response = await axios.get('/api/plug/agent/tasks/stats');


    if (response.data.status === 'ok') {


      stats.value = response.data.data;


    }


  } catch (error) {


    console.error('Failed to load stats:', error);


  }


}





// 加载 Crew 列表


async function loadCrews() {


  try {


    const response = await axios.get('/api/plug/agent/crews');


    if (response.data.status === 'ok') {


      crewOptions.value = (response.data.data || []).map((crew: any) => ({


        title: crew.name,


        value: crew.name


      }));


    }


  } catch (error) {


    console.error('Failed to load crews:', error);


  }


}





// 分页处理


function handlePageChange(page: number) {


  currentPage.value = page;


  loadTasks();


}





function handleItemsPerPageChange(size: number) {


  itemsPerPage.value = size;


  currentPage.value = 1;


  loadTasks();


}





// 查看详情


function viewDetail(task: any) {


  router.push(`/agent/tasks/${task.id}`);


}





// 暂停任务


async function pauseTask(task: any) {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.id}/pause`);


    await loadTasks();


  } catch (error: any) {


    console.error('Failed to pause task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.pauseError'));


  }


}





// 恢复任务


async function resumeTask(task: any) {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.id}/resume`);


    await loadTasks();


  } catch (error: any) {


    console.error('Failed to resume task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.resumeError'));


  }


}





// 取消任务


async function cancelTask(task: any) {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.id}/cancel`);


    await loadTasks();


  } catch (error: any) {


    console.error('Failed to cancel task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.cancelError'));


  }


}





// 重试任务


async function retryTask(task: any) {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.id}/retry`);


    await loadTasks();


  } catch (error: any) {


    console.error('Failed to retry task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.retryError'));


  }


}





// 删除任务


function deleteTask(task: any) {


  deletingTask.value = task;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingTask.value) return;





  deleting.value = true;


  try {


    await axios.delete(`/api/plug/agent/tasks/${deletingTask.value.id}`);


    showDeleteDialog.value = false;


    await loadTasks();


    await loadStats();


  } catch (error: any) {


    console.error('Failed to delete task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 获取状态颜


function getStatusColor(status: string): string {


  const colors: Record<string, string> = {


    pending: 'grey',


    running: 'info',


    paused: 'warning',


    waiting_feedback: 'purple',


    completed: 'success',


    failed: 'error',


    cancelled: 'grey'


  };


  return colors[status] || 'grey';


}





// 获取状态图标


function getStatusIcon(status: string): string {


  const icons: Record<string, string> = {


    pending: 'mdi-clock-outline',


    running: 'mdi-progress-clock',


    paused: 'mdi-pause-circle',


    waiting_feedback: 'mdi-message-question',


    completed: 'mdi-check-circle',


    failed: 'mdi-alert-circle',


    cancelled: 'mdi-cancel'


  };


  return icons[status] || 'mdi-help-circle';


}





// 获取类型颜色


function getTypeColor(type: string): string {


  const colors: Record<string, string> = {


    crew: 'primary',


    flow: 'secondary'


  };


  return colors[type] || 'grey';


}





// 获取类型图标


function getTypeIcon(type: string): string {


  const icons: Record<string, string> = {


    crew: 'mdi-account-group',


    flow: 'mdi-sitemap'


  };


  return icons[type] || 'mdi-file-document';


}





// 获取进度颜色


function getProgressColor(status: string): string {


  if (status === 'completed') return 'success';


  if (status === 'failed') return 'error';


  return 'primary';


}





// 格式化 Token 数量


function formatTokenCount(count: number): string {


  if (count >= 1000000) {


    return `${(count / 1000000).toFixed(1)}M`;


  }


  if (count >= 1000) {


    return `${(count / 1000).toFixed(1)}K`;


  }


  return count.toString();


}





// 格式化日期


function formatDate(dateStr: string): string {


  if (!dateStr) return '-';


  const date = new Date(dateStr);


  return date.toLocaleString();


}





// 监听筛选条件变化


watch([activeTab, filterCrew, filterTimeRange], () => {


  currentPage.value = 1;


  loadTasks();


});





onMounted(() => {


  loadTasks();


  loadStats();


  loadCrews();


});


</script>





<style scoped>


.v-card {


  border-radius: 12px;


}


</style>


