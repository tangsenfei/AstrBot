<template>


  <div class="execution-tracker">


    <!-- 筛选区域-->


    <v-row class="mb-4">


      <v-col cols="12" md="4">


        <v-select


          v-model="filterAgent"


          :items="agentOptions"


          :label="$t('agent.tasks.execution.filter.agent')"


          prepend-inner-icon="mdi-robot"


          variant="outlined"


          density="compact"


          hide-details


          clearable


        />


      </v-col>


      <v-col cols="12" md="4">


        <v-select


          v-model="filterStatus"


          :items="statusOptions"


          :label="$t('agent.tasks.execution.filter.status')"


          prepend-inner-icon="mdi-filter"


          variant="outlined"


          density="compact"


          hide-details


          clearable


        />


      </v-col>


    </v-row>





    <!-- 时间-->


    <v-timeline side="end" align="start" v-if="filteredSteps.length > 0">


      <v-timeline-item


        v-for="(step, index) in filteredSteps"


        :key="index"


        :dot-color="getStepColor(step.status)"


        :icon="getStepIcon(step.status)"


        size="small"


      >


        <v-card variant="outlined" class="mb-2">


          <v-card-text>


            <div class="d-flex justify-space-between align-start mb-2">


              <div>


                <div class="text-body-1 font-weight-medium">{{ step.name }}</div>


                <div class="text-caption text-grey">{{ step.agentName }}</div>


              </div>


              <v-chip :color="getStepColor(step.status)" size="x-small" variant="tonal">


                {{ $t(`agent.tasks.execution.status.${step.status}`) }}


              </v-chip>


            </div>





            <div class="d-flex align-center text-caption text-grey mb-2">


              <v-icon icon="mdi-clock-outline" size="small" class="mr-1" />


              <span>{{ formatDuration(step.duration) }}</span>


              <span class="mx-2">|</span>


              <v-icon icon="mdi-calendar" size="small" class="mr-1" />


              <span>{{ formatDate(step.startedAt) }}</span>


            </div>





            <!-- 展开详情 -->


            <v-expansion-panels flat>


              <v-expansion-panel>


                <v-expansion-panel-title class="px-0">


                  {{ $t('agent.tasks.execution.viewDetails') }}


                </v-expansion-panel-title>


                <v-expansion-panel-text class="px-0">


                  <v-row>


                    <v-col cols="12">


                      <div class="text-caption text-grey mb-1">{{ $t('agent.tasks.execution.input') }}</div>


                      <v-card variant="outlined" class="pa-2 mb-2">


                        <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word">{{ step.input || '-' }}</pre>


                      </v-card>


                    </v-col>


                    <v-col cols="12">


                      <div class="text-caption text-grey mb-1">{{ $t('agent.tasks.execution.output') }}</div>


                      <v-card variant="outlined" class="pa-2">


                        <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word">{{ step.output || '-' }}</pre>


                      </v-card>


                    </v-col>


                  </v-row>


                </v-expansion-panel-text>


              </v-expansion-panel>


            </v-expansion-panels>


          </v-card-text>


        </v-card>


      </v-timeline-item>


    </v-timeline>





    <!-- 空状-->


    <v-card v-else variant="outlined" class="pa-8 text-center">


      <v-icon icon="mdi-timeline-clock" size="60" color="grey-lighten-1" class="mb-4" />


      <p class="text-grey">{{ $t('agent.tasks.execution.empty') }}</p>


    </v-card>


  </div>


</template>





<script setup lang="ts">


import { ref, computed, watch } from 'vue';


import { useI18n } from 'vue-i18n';





const props = defineProps<{


  taskId: string;


  steps: any[];


}>();





const { t } = useI18n();





// 筛


const filterAgent = ref<string | null>(null);


const filterStatus = ref<string | null>(null);





// Agent 选项


const agentOptions = computed(() => {


  const agents = new Set<string>();


  props.steps.forEach(step => {


    if (step.agentName) {


      agents.add(step.agentName);


    }


  });


  return Array.from(agents).map(name => ({ title: name, value: name }));


});





// 状态选项


const statusOptions = computed(() => [


  { title: t('agent.tasks.execution.status.pending'), value: 'pending' },


  { title: t('agent.tasks.execution.status.running'), value: 'running' },


  { title: t('agent.tasks.execution.status.completed'), value: 'completed' },


  { title: t('agent.tasks.execution.status.failed'), value: 'failed' },


  { title: t('agent.tasks.execution.status.skipped'), value: 'skipped' }


]);





// 过滤后的步骤


const filteredSteps = computed(() => {


  let result = props.steps;





  if (filterAgent.value) {


    result = result.filter(step => step.agentName === filterAgent.value);


  }





  if (filterStatus.value) {


    result = result.filter(step => step.status === filterStatus.value);


  }





  return result;


});





// 获取步骤颜色


function getStepColor(status: string): string {


  const colors: Record<string, string> = {


    pending: 'grey',


    running: 'info',


    completed: 'success',


    failed: 'error',


    skipped: 'warning'


  };


  return colors[status] || 'grey';


}





// 获取步骤图标


function getStepIcon(status: string): string {


  const icons: Record<string, string> = {


    pending: 'mdi-clock-outline',


    running: 'mdi-progress-clock',


    completed: 'mdi-check',


    failed: 'mdi-alert',


    skipped: 'mdi-skip-next'


  };


  return icons[status] || 'mdi-help-circle';


}





// 格式化持续时


function formatDuration(duration: number): string {


  if (!duration) return '-';


  if (duration < 1000) {


    return `${duration}ms`;


  }


  if (duration < 60000) {


    return `${(duration / 1000).toFixed(1)}s`;


  }


  return `${(duration / 60000).toFixed(1)}m`;


}





// 格式化日期


function formatDate(dateStr: string): string {


  if (!dateStr) return '-';


  const date = new Date(dateStr);


  return date.toLocaleString();


}


</script>





<style scoped>


.execution-tracker {


  min-height: 200px;


}





.v-timeline-item {


  padding-bottom: 0;


}





.v-expansion-panel-title {


  min-height: 32px;


  padding: 0;


}


</style>


