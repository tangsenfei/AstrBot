<template>
  <v-container fluid class="pa-6">
    <v-card class="mb-6">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-rocket-launch" class="mr-2" />
        {{ t('nicebot.evolution_center.title') }}
      </v-card-title>
      <v-card-subtitle>
        {{ t('nicebot.evolution_center.description') }}
      </v-card-subtitle>
    </v-card>

    <v-row>
      <v-col cols="12" md="8">
        <v-card class="mb-4">
          <v-card-title>{{ t('nicebot.evolution_center.evolution_tasks.title') }}</v-card-title>
          <v-card-text>
            <v-btn color="primary" class="mb-4" prepend-icon="mdi-plus">
              {{ t('nicebot.evolution_center.actions.create_task') }}
            </v-btn>

            <v-timeline side="end" align="start">
              <v-timeline-item
                v-for="task in evolutionTasks"
                :key="task.id"
                :dot-color="getTaskColor(task.status)"
                size="small"
              >
                <v-card variant="outlined">
                  <v-card-title class="text-subtitle-1">
                    {{ task.title }}
                    <v-chip :color="getTaskColor(task.status)" size="x-small" class="ml-2">
                      {{ t(`nicebot.evolution_center.status.${task.status}`) }}
                    </v-chip>
                  </v-card-title>
                  <v-card-text>
                    <div class="text-body-2 mb-2">{{ task.description }}</div>
                    <div class="d-flex align-center ga-2">
                      <v-progress-linear
                        :model-value="task.progress"
                        color="primary"
                        height="6"
                        rounded
                        style="max-width: 200px"
                      />
                      <span class="text-caption">{{ task.progress }}%</span>
                    </div>
                  </v-card-text>
                  <v-card-actions>
                    <v-btn variant="text" size="small" :disabled="task.status === 'completed'">
                      {{ t('nicebot.evolution_center.actions.view_detail') }}
                    </v-btn>
                    <v-btn variant="text" size="small" color="error" :disabled="task.status === 'running'">
                      {{ t('nicebot.evolution_center.actions.cancel') }}
                    </v-btn>
                  </v-card-actions>
                </v-card>
              </v-timeline-item>
            </v-timeline>

            <v-alert v-if="evolutionTasks.length === 0" type="info" variant="tonal">
              {{ t('nicebot.evolution_center.evolution_tasks.empty') }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card class="mb-4">
          <v-card-title>{{ t('nicebot.evolution_center.capabilities.title') }}</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item
                v-for="cap in capabilities"
                :key="cap.id"
                :subtitle="cap.description"
              >
                <template v-slot:prepend>
                  <v-icon :icon="cap.icon" :color="cap.enabled ? 'success' : 'grey'" />
                </template>
                <v-list-item-title>{{ cap.name }}</v-list-item-title>
                <template v-slot:append>
                  <v-switch
                    v-model="cap.enabled"
                    color="primary"
                    hide-details
                    density="compact"
                  />
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>

        <v-card>
          <v-card-title>{{ t('nicebot.evolution_center.stats.title') }}</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon icon="mdi-counter" />
                </template>
                <v-list-item-title>{{ t('nicebot.evolution_center.stats.total_tasks') }}</v-list-item-title>
                <v-list-item-subtitle class="text-right">{{ stats.totalTasks }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon icon="mdi-check-circle" color="success" />
                </template>
                <v-list-item-title>{{ t('nicebot.evolution_center.stats.completed') }}</v-list-item-title>
                <v-list-item-subtitle class="text-right">{{ stats.completed }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon icon="mdi-trending-up" color="info" />
                </template>
                <v-list-item-title>{{ t('nicebot.evolution_center.stats.improvements') }}</v-list-item-title>
                <v-list-item-subtitle class="text-right">{{ stats.improvements }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const evolutionTasks = ref([
  { id: 1, title: '对话能力优化', description: '基于用户反馈优化对话响应质量', status: 'running', progress: 65 },
  { id: 2, title: '知识库扩展', description: '自动学习新领域知识', status: 'pending', progress: 0 },
  { id: 3, title: '工具调用优化', description: '提升工具选择的准确性', status: 'completed', progress: 100 }
]);

const capabilities = ref([
  { id: 1, name: '自动学习', description: '从对话中自动学习新知识', icon: 'mdi-school', enabled: true },
  { id: 2, name: '自我评估', description: '定期评估自身表现', icon: 'mdi-chart-line', enabled: true },
  { id: 3, name: '能力扩展', description: '自动发现并安装新能力', icon: 'mdi-puzzle', enabled: false },
  { id: 4, name: '性能优化', description: '自动优化响应速度', icon: 'mdi-speedometer', enabled: true }
]);

const stats = reactive({
  totalTasks: 15,
  completed: 12,
  improvements: 8
});

const getTaskColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'grey',
    running: 'primary',
    completed: 'success',
    failed: 'error'
  };
  return colors[status] || 'grey';
};
</script>
