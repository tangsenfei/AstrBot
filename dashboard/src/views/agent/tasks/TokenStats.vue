<template>


  <div class="token-stats">


    <!-- Token 消耗卡-->


    <v-row class="mb-4">


      <v-col cols="12" md="4">


        <v-card variant="outlined">


          <v-card-text class="text-center">


            <v-icon icon="mdi-token" size="40" color="primary" class="mb-2" />


            <div class="text-h4 font-weight-bold text-primary">{{ formatTokenCount(tokenUsage?.total || 0) }}</div>


            <div class="text-body-2 text-grey">{{ $t('agent.tasks.tokens.totalTokens') }}</div>


          </v-card-text>


        </v-card>


      </v-col>


      <v-col cols="12" md="4">


        <v-card variant="outlined">


          <v-card-text class="text-center">


            <v-icon icon="mdi-text-box" size="40" color="info" class="mb-2" />


            <div class="text-h4 font-weight-bold text-info">{{ formatTokenCount(tokenUsage?.prompt || 0) }}</div>


            <div class="text-body-2 text-grey">{{ $t('agent.tasks.tokens.promptTokens') }}</div>


          </v-card-text>


        </v-card>


      </v-col>


      <v-col cols="12" md="4">


        <v-card variant="outlined">


          <v-card-text class="text-center">


            <v-icon icon="mdi-message-text" size="40" color="success" class="mb-2" />


            <div class="text-h4 font-weight-bold text-success">{{ formatTokenCount(tokenUsage?.completion || 0) }}</div>


            <div class="text-body-2 text-grey">{{ $t('agent.tasks.tokens.completionTokens') }}</div>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <v-row>


      <!-- Agent 分布 -->


      <v-col cols="12" md="6">


        <v-card variant="outlined">


          <v-card-title>


            <v-icon icon="mdi-chart-pie" class="mr-2" />


            {{ $t('agent.tasks.tokens.byAgent') }}


          </v-card-title>


          <v-card-text>


            <div v-if="agentStats && agentStats.length > 0" class="chart-container">


              <!-- 简化的饼图展示 -->


              <div class="pie-chart">


                <svg viewBox="0 0 100 100" class="pie-svg">


                  <circle


                    v-for="(segment, index) in pieSegments"


                    :key="index"


                    cx="50"


                    cy="50"


                    r="40"


                    fill="transparent"


                    :stroke="segment.color"


                    stroke-width="20"


                    :stroke-dasharray="`${segment.percentage * 2.51} ${251 - segment.percentage * 2.51}`"


                    :stroke-dashoffset="segment.offset"


                    class="pie-segment"


                  />


                </svg>


              </div>


              <v-list density="compact" class="mt-4">


                <v-list-item v-for="(stat, index) in agentStats" :key="index">


                  <template v-slot:prepend>


                    <v-avatar :color="getAgentColor(index)" size="12" class="mr-3" />


                  </template>


                  <v-list-item-title>{{ stat.agentName }}</v-list-item-title>


                  <v-list-item-subtitle>


                    {{ formatTokenCount(stat.tokens) }} ({{ getPercentage(stat.tokens) }}%)


                  </v-list-item-subtitle>


                </v-list-item>


              </v-list>


            </div>


            <div v-else class="text-center py-8 text-grey">


              {{ $t('agent.tasks.tokens.noData') }}


            </div>


          </v-card-text>


        </v-card>


      </v-col>





      <!-- 按时间分布-->


      <v-col cols="12" md="6">


        <v-card variant="outlined">


          <v-card-title>


            <v-icon icon="mdi-chart-line" class="mr-2" />


            {{ $t('agent.tasks.tokens.byTime') }}


          </v-card-title>


          <v-card-text>


            <div v-if="timeSeriesData && timeSeriesData.length > 0" class="chart-container">


              <!-- 简化的折线图展示-->


              <div class="line-chart">


                <svg viewBox="0 0 400 200" class="line-svg">


                  <!-- 网格线-->


                  <line x1="40" y1="20" x2="40" y2="180" stroke="#e0e0e0" stroke-width="1" />


                  <line x1="40" y1="180" x2="390" y2="180" stroke="#e0e0e0" stroke-width="1" />


                  


                  <!-- Y 轴标签-->


                  <text x="35" y="25" text-anchor="end" class="axis-label">{{ formatTokenCount(maxTokens) }}</text>


                  <text x="35" y="100" text-anchor="end" class="axis-label">{{ formatTokenCount(maxTokens / 2) }}</text>


                  <text x="35" y="180" text-anchor="end" class="axis-label">0</text>





                  <!-- 数据点-->


                  <polyline


                    :points="linePoints"


                    fill="none"


                    stroke="primary"


                    stroke-width="2"


                  />


                  


                  <!-- 数据点-->


                  <circle


                    v-for="(point, index) in dataPoints"


                    :key="index"


                    :cx="point.x"


                    :cy="point.y"


                    r="4"


                    fill="primary"


                  />


                </svg>


              </div>


              <v-list density="compact" class="mt-4">


                <v-list-item v-for="(data, index) in timeSeriesData.slice(-5)" :key="index">


                  <v-list-item-title>{{ formatTimeLabel(data.time) }}</v-list-item-title>


                  <v-list-item-subtitle>


                    {{ formatTokenCount(data.tokens) }}


                  </v-list-item-subtitle>


                </v-list-item>


              </v-list>


            </div>


            <div v-else class="text-center py-8 text-grey">


              {{ $t('agent.tasks.tokens.noData') }}


            </div>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>


  </div>


</template>





<script setup lang="ts">


import { ref, computed, onMounted } from 'vue';


import axios from 'axios';


import { useI18n } from 'vue-i18n';





const props = defineProps<{


  taskId: string;


  tokenUsage: {


    total: number;


    prompt: number;


    completion: number;


  };


  agentStats: Array<{


    agentName: string;


    tokens: number;


  }>;


}>();





const { t } = useI18n();





// 时间序列数据


const timeSeriesData = ref<Array<{ time: string; tokens: number }>>([]);





// 最大 Token 


const maxTokens = computed(() => {


  if (!timeSeriesData.value.length) return 0;


  return Math.max(...timeSeriesData.value.map(d => d.tokens));


});





// 饼图数据


const pieSegments = computed(() => {


  if (!props.agentStats || props.agentStats.length === 0) return [];


  


  const total = props.agentStats.reduce((sum, stat) => sum + stat.tokens, 0);


  let offset = 0;


  


  return props.agentStats.map((stat, index) => {


    const percentage = (stat.tokens / total) * 100;


    const segment = {


      percentage,


      offset: -offset * 2.51,


      color: getAgentColor(index)


    };


    offset += percentage;


    return segment;


  });


});





// 折线图数据点


const dataPoints = computed(() => {


  if (!timeSeriesData.value.length) return [];


  


  const max = maxTokens.value || 1;


  const width = 350;


  const height = 160;


  const padding = 40;


  


  return timeSeriesData.value.map((data, index) => ({


    x: padding + (index / (timeSeriesData.value.length - 1)) * width,


    y: padding + height - (data.tokens / max) * height


  }));


});





// 折线图路径


const linePoints = computed(() => {


  return dataPoints.value.map(p => `${p.x},${p.y}`).join(' ');


});





// 加载时间序列数据


async function loadTimeSeriesData() {


  try {


    const response = await axios.get(`/api/plug/agent/tasks/${props.taskId}/tokens/timeseries`);


    if (response.data.status === 'ok') {


      timeSeriesData.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load time series data:', error);


  }


}





// 获取 Agent 颜色


function getAgentColor(index: number): string {


  const colors = ['primary', 'info', 'success', 'warning', 'error', 'purple', 'teal', 'indigo'];


  return colors[index % colors.length];


}





// 获取百分比


function getPercentage(tokens: number): number {


  if (!props.tokenUsage?.total) return 0;


  return Math.round((tokens / props.tokenUsage.total) * 100);


}





// 格式?Token 数量


function formatTokenCount(count: number): string {


  if (count >= 1000000) {


    return `${(count / 1000000).toFixed(1)}M`;


  }


  if (count >= 1000) {


    return `${(count / 1000).toFixed(1)}K`;


  }


  return count.toString();


}





// 格式化时间标签


function formatTimeLabel(time: string): string {


  if (!time) return '-';


  const date = new Date(time);


  return date.toLocaleTimeString();


}





onMounted(() => {


  loadTimeSeriesData();


});


</script>





<style scoped>


.token-stats {


  min-height: 300px;


}





.chart-container {


  min-height: 200px;


}





.pie-chart {


  display: flex;


  justify-content: center;


  margin-bottom: 16px;


}





.pie-svg {


  width: 150px;


  height: 150px;


}





.pie-segment {


  transform-origin: center;


}





.line-chart {


  display: flex;


  justify-content: center;


  margin-bottom: 16px;


}





.line-svg {


  width: 100%;


  max-width: 400px;


  height: auto;


}





.axis-label {


  font-size: 10px;


  fill: #666;


}


</style>


