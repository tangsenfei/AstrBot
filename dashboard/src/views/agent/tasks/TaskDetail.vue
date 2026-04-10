<template>


  <v-container fluid class="pa-6">


    <!-- 加载状-->


    <v-row v-if="loading">


      <v-col cols="12" class="text-center py-8">


        <v-progress-circular indeterminate color="primary" />


        <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


      </v-col>


    </v-row>





    <!-- 任务不存-->


    <v-row v-else-if="!task">


      <v-col cols="12">


        <v-card>


          <v-card-text class="text-center py-8">


            <v-icon icon="mdi-alert-circle" size="60" color="error" class="mb-4" />


            <p class="text-grey">{{ $t('agent.tasks.notFound') }}</p>


            <v-btn color="primary" class="mt-4" @click="goBack">


              {{ $t('agent.tasks.actions.back') }}


            </v-btn>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <!-- 任务详情 -->


    <template v-else>


      <!-- 页面标题 -->


      <v-row>


        <v-col cols="12">


          <v-card class="mb-6">


            <v-card-title class="d-flex align-center">


              <v-btn icon variant="text" @click="goBack" class="mr-2">


                <v-icon icon="mdi-arrow-left" />


              </v-btn>


              <v-icon :icon="getTypeIcon(task.type)" class="mr-2" :color="getTypeColor(task.type)" />


              {{ task.name }}


              <v-chip :color="getStatusColor(task.status)" size="small" class="ml-4">


                <v-icon start :icon="getStatusIcon(task.status)" size="small" />


                {{ $t(`agent.tasks.status.${task.status}`) }}


              </v-chip>


              <v-spacer />


              <v-btn variant="outlined" @click="loadTask" :loading="refreshing" class="mr-2">


                <v-icon start icon="mdi-refresh" />


                {{ $t('agent.tasks.buttons.refresh') }}


              </v-btn>


            </v-card-title>


            <v-card-subtitle>


              {{ $t('agent.tasks.detail.subtitle', { id: task.id }) }}


            </v-card-subtitle>


          </v-card>


        </v-col>


      </v-row>





      <!-- 基本信息 -->


      <v-row>


        <v-col cols="12" md="8">


          <v-card class="mb-4">


            <v-card-title>


              <v-icon icon="mdi-information" class="mr-2" />


              {{ $t('agent.tasks.detail.basicInfo') }}


            </v-card-title>


            <v-card-text>


              <v-row>


                <v-col cols="12" sm="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.type') }}</div>


                  <div class="text-body-1 font-weight-medium">


                    <v-chip :color="getTypeColor(task.type)" size="small" variant="tonal">


                      {{ $t(`agent.tasks.types.${task.type}`) }}


                    </v-chip>


                  </div>


                </v-col>


                <v-col cols="12" sm="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.crew') }}</div>


                  <div class="text-body-1 font-weight-medium">{{ task.crewName || '-' }}</div>


                </v-col>


                <v-col cols="12" sm="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.createdAt') }}</div>


                  <div class="text-body-1 font-weight-medium">{{ formatDate(task.createdAt) }}</div>


                </v-col>


                <v-col cols="12" sm="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.updatedAt') }}</div>


                  <div class="text-body-1 font-weight-medium">{{ formatDate(task.updatedAt) }}</div>


                </v-col>


                <v-col cols="12">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.input') }}</div>


                  <div class="text-body-1 mt-2">


                    <v-card variant="outlined" class="pa-3">


                      <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word">{{ task.input || '-' }}</pre>


                    </v-card>


                  </div>


                </v-col>


              </v-row>


            </v-card-text>


          </v-card>


        </v-col>





        <v-col cols="12" md="4">


          <!-- 进度卡片 -->


          <v-card class="mb-4">


            <v-card-title>


              <v-icon icon="mdi-chart-line" class="mr-2" />


              {{ $t('agent.tasks.detail.progress') }}


            </v-card-title>


            <v-card-text>


              <div class="d-flex align-center mb-4">


                <v-progress-circular


                  :model-value="task.progress || 0"


                  :color="getProgressColor(task.status)"


                  size="80"


                  width="8"


                >


                  <span class="text-h5 font-weight-bold">{{ task.progress || 0 }}%</span>


                </v-progress-circular>


              </div>


              <v-row dense>


                <v-col cols="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.totalSteps') }}</div>


                  <div class="text-h6">{{ task.totalSteps || 0 }}</div>


                </v-col>


                <v-col cols="6">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.completedSteps') }}</div>


                  <div class="text-h6">{{ task.completedSteps || 0 }}</div>


                </v-col>


              </v-row>


            </v-card-text>


          </v-card>





          <!-- Token 统计卡片 -->


          <v-card class="mb-4">


            <v-card-title>


              <v-icon icon="mdi-token" class="mr-2" />


              {{ $t('agent.tasks.detail.tokenUsage') }}


            </v-card-title>


            <v-card-text>


              <v-row dense>


                <v-col cols="12">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.totalTokens') }}</div>


                  <div class="text-h5 font-weight-bold text-primary">


                    {{ formatTokenCount(task.tokenUsage?.total || 0) }}


                  </div>


                </v-col>


                <v-col cols="6" class="mt-2">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.promptTokens') }}</div>


                  <div class="text-body-1">{{ formatTokenCount(task.tokenUsage?.prompt || 0) }}</div>


                </v-col>


                <v-col cols="6" class="mt-2">


                  <div class="text-caption text-grey">{{ $t('agent.tasks.detail.completionTokens') }}</div>


                  <div class="text-body-1">{{ formatTokenCount(task.tokenUsage?.completion || 0) }}</div>


                </v-col>


              </v-row>


            </v-card-text>


          </v-card>





          <!-- 任务控制 -->


          <TaskControl


            :task="task"


            @pause="handlePause"


            @resume="handleResume"


            @cancel="handleCancel"


            @retry="handleRetry"


            @feedback="handleFeedback"


          />


        </v-col>


      </v-row>





      <!-- 标签-->


      <v-row>


        <v-col cols="12">


          <v-card>


            <v-tabs v-model="activeTab" color="primary">


              <v-tab value="execution">


                <v-icon start icon="mdi-timeline" />


                {{ $t('agent.tasks.tabs.execution') }}


              </v-tab>


              <v-tab value="planning">


                <v-icon start icon="mdi-clipboard-text-outline" />


                {{ $t('agent.tasks.tabs.planning') }}


              </v-tab>


              <v-tab value="tokens">


                <v-icon start icon="mdi-chart-pie" />


                {{ $t('agent.tasks.tabs.tokens') }}


              </v-tab>


              <v-tab value="output">


                <v-icon start icon="mdi-file-document-outline" />


                {{ $t('agent.tasks.tabs.output') }}


              </v-tab>


            </v-tabs>





            <v-card-text>


              <v-window v-model="activeTab">


                <v-window-item value="execution">


                  <ExecutionTracker :task-id="task.id" :steps="task.steps || []" />


                </v-window-item>





                <v-window-item value="planning">


                  <v-card variant="outlined" class="pa-4">


                    <div v-if="task.planning">


                      <div class="text-h6 mb-4">{{ $t('agent.tasks.planning.title') }}</div>


                      <v-timeline side="end" align="start">


                        <v-timeline-item


                          v-for="(step, index) in task.planning.steps"


                          :key="index"


                          :dot-color="getPlanningStepColor(step.status)"


                          size="small"


                        >


                          <div class="mb-2">


                            <div class="text-body-1 font-weight-medium">{{ step.description }}</div>


                            <div class="text-caption text-grey">


                              {{ $t('agent.tasks.planning.step', { index: index + 1 }) }}


                            </div>


                          </div>


                        </v-timeline-item>


                      </v-timeline>


                    </div>


                    <div v-else class="text-center py-8 text-grey">


                      {{ $t('agent.tasks.planning.empty') }}


                    </div>


                  </v-card>


                </v-window-item>





                <v-window-item value="tokens">


                  <TokenStats :task-id="task.id" :token-usage="task.tokenUsage" :agent-stats="task.agentTokenStats" />


                </v-window-item>





                <v-window-item value="output">


                  <v-card variant="outlined" class="pa-4">


                    <div v-if="task.output">


                      <div class="d-flex justify-end mb-2">


                        <v-btn size="small" variant="text" @click="copyOutput">


                          <v-icon start icon="mdi-content-copy" />


                          {{ $t('agent.tasks.output.copy') }}


                        </v-btn>


                      </div>


                      <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word">{{ task.output }}</pre>


                    </div>


                    <div v-else class="text-center py-8 text-grey">


                      {{ $t('agent.tasks.output.empty') }}


                    </div>


                  </v-card>


                </v-window-item>


              </v-window>


            </v-card-text>


          </v-card>


        </v-col>


      </v-row>





      <!-- 反馈对话-->


      <v-dialog v-model="showFeedbackDialog" max-width="600">


        <v-card>


          <v-card-title>{{ $t('agent.tasks.feedback.title') }}</v-card-title>


          <v-card-text>


            <v-textarea


              v-model="feedbackContent"


              :label="$t('agent.tasks.feedback.label')"


              rows="4"


              auto-grow


              :placeholder="$t('agent.tasks.feedback.placeholder')"


            />


          </v-card-text>


          <v-card-actions>


            <v-spacer />


            <v-btn @click="showFeedbackDialog = false">{{ $t('common.cancel') }}</v-btn>


            <v-btn color="primary" @click="submitFeedback" :loading="submittingFeedback" :disabled="!feedbackContent">


              {{ $t('agent.tasks.feedback.submit') }}


            </v-btn>


          </v-card-actions>


        </v-card>


      </v-dialog>


    </template>


  </v-container>


</template>





<script setup lang="ts">


import { ref, onMounted } from 'vue';


import { useRoute, useRouter } from 'vue-router';


import axios from 'axios';


import { useI18n } from 'vue-i18n';


import ExecutionTracker from './ExecutionTracker.vue';


import TokenStats from './TokenStats.vue';


import TaskControl from './TaskControl.vue';





const { t } = useI18n();


const route = useRoute();


const router = useRouter();





// 状


const loading = ref(true);


const refreshing = ref(false);


const task = ref<any>(null);


const activeTab = ref('execution');





// 反馈


const showFeedbackDialog = ref(false);


const feedbackContent = ref('');


const submittingFeedback = ref(false);





// 加载任务详情


async function loadTask() {


  const taskId = route.params.id as string;


  if (!taskId) return;





  refreshing.value = true;


  try {


    const response = await axios.get(`/api/plug/agent/tasks/${taskId}`);


    if (response.data.status === 'ok') {


      task.value = response.data.data;


    }


  } catch (error) {


    console.error('Failed to load task:', error);


  } finally {


    loading.value = false;


    refreshing.value = false;


  }


}





// 返回列表


function goBack() {


  router.push('/agent/tasks');


}





// 暂停任务


async function handlePause() {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.value.id}/pause`);


    await loadTask();


  } catch (error: any) {


    console.error('Failed to pause task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.pauseError'));


  }


}





// 恢复任务


async function handleResume() {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.value.id}/resume`);


    await loadTask();


  } catch (error: any) {


    console.error('Failed to resume task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.resumeError'));


  }


}





// 取消任务


async function handleCancel() {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.value.id}/cancel`);


    await loadTask();


  } catch (error: any) {


    console.error('Failed to cancel task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.cancelError'));


  }


}





// 重试任务


async function handleRetry() {


  try {


    await axios.post(`/api/plug/agent/tasks/${task.value.id}/retry`);


    await loadTask();


  } catch (error: any) {


    console.error('Failed to retry task:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.retryError'));


  }


}





// 提供反馈


function handleFeedback() {


  feedbackContent.value = '';


  showFeedbackDialog.value = true;


}





// 提交反馈


async function submitFeedback() {


  if (!feedbackContent.value) return;





  submittingFeedback.value = true;


  try {


    await axios.post(`/api/plug/agent/tasks/${task.value.id}/feedback`, {


      feedback: feedbackContent.value


    });


    showFeedbackDialog.value = false;


    await loadTask();


  } catch (error: any) {


    console.error('Failed to submit feedback:', error);


    alert(error.response?.data?.message || t('agent.tasks.messages.feedbackError'));


  } finally {


    submittingFeedback.value = false;


  }


}





// 复制输出


function copyOutput() {


  if (task.value?.output) {


    navigator.clipboard.writeText(task.value.output);


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





// 获取规划步骤颜色


function getPlanningStepColor(status: string): string {


  const colors: Record<string, string> = {


    pending: 'grey',


    running: 'info',


    completed: 'success',


    failed: 'error'


  };


  return colors[status] || 'grey';


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





onMounted(() => {


  loadTask();


});


</script>





<style scoped>


.v-card {


  border-radius: 12px;


}


</style>


