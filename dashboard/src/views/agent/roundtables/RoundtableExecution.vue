<template>
  <v-container fluid class="pa-6">
    <v-row v-if="loading">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" />
        <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
      </v-col>
    </v-row>

    <v-row v-else-if="!roundtable">
      <v-col cols="12">
        <v-card>
          <v-card-text class="text-center py-8">
            <v-icon icon="mdi-alert-circle" size="60" color="error" class="mb-4" />
            <p class="text-grey">{{ $t('agent.roundtables.notFound') }}</p>
            <v-btn color="primary" class="mt-4" @click="goBack">
              {{ $t('agent.roundtables.actions.back') }}
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <template v-else>
      <v-row>
        <v-col cols="12">
          <v-card class="mb-6">
            <v-card-title class="d-flex align-center">
              <v-btn icon variant="text" @click="goBack" class="mr-2">
                <v-icon icon="mdi-arrow-left" />
              </v-btn>
              <v-icon icon="mdi-table-chair" class="mr-2" />
              {{ roundtable.name }}
              <v-chip :color="getStatusColor(roundtable.status)" size="small" class="ml-4">
                <v-icon start :icon="getStatusIcon(roundtable.status)" size="small" />
                {{ $t(`agent.roundtables.status.${roundtable.status}`) }}
              </v-chip>
              <v-chip :color="getMeetingTypeColor(roundtable.meeting_type)" size="small" class="ml-2" variant="tonal">
                <v-icon start :icon="getMeetingTypeIcon(roundtable.meeting_type)" size="small" />
                {{ getMeetingTypeName(roundtable.meeting_type) }}
              </v-chip>
              <v-spacer />
              <v-btn
                v-if="roundtable.status === 'running'"
                variant="outlined"
                size="small"
                @click="togglePolling"
                class="mr-2"
              >
                <v-icon start :icon="isPolling ? 'mdi-pause' : 'mdi-play'" />
                {{ isPolling ? $t('agent.roundtables.actions.pausePolling') : $t('agent.roundtables.actions.resumePolling') }}
              </v-btn>
              <v-btn
                v-if="roundtable.status === 'completed'"
                variant="outlined"
                @click="exportResult"
                class="mr-2"
              >
                <v-icon start icon="mdi-export" />
                {{ $t('agent.roundtables.actions.export') }}
              </v-btn>
              <v-btn variant="outlined" @click="loadRoundtable" :loading="refreshing">
                <v-icon start icon="mdi-refresh" />
                {{ $t('common.refresh') }}
              </v-btn>
            </v-card-title>
            <v-card-subtitle>
              {{ roundtable.topic }}
            </v-card-subtitle>
          </v-card>
        </v-col>
      </v-row>

      <v-row>
        <v-col cols="12">
          <v-card class="mb-4">
            <v-tabs v-model="activeStageTab" color="primary" grow>
              <v-tab value="preparation">
                <v-icon icon="mdi-book-open-variant" class="mr-1" />
                准备阶段
              </v-tab>
              <v-tab value="running">
                <v-icon icon="mdi-run" class="mr-1" />
                进行阶段
              </v-tab>
              <v-tab value="completed" :disabled="roundtable.status !== 'completed' && roundtable.status !== 'failed'">
                <v-icon icon="mdi-check-circle" class="mr-1" />
                完成阶段
              </v-tab>
            </v-tabs>
          </v-card>
        </v-col>
      </v-row>

      <!-- 准备阶段 -->
      <v-row v-if="activeStageTab === 'preparation'">
        <v-col cols="12">
          <v-card class="mb-4">
            <v-card-title>
              <v-icon icon="mdi-cog" class="mr-2" />
              会议配置
            </v-card-title>
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-shape-outline" />
                      </template>
                      <v-list-item-title>会议类型</v-list-item-title>
                      <v-list-item-subtitle>{{ getMeetingTypeName(roundtable.meeting_type) }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-text" />
                      </template>
                      <v-list-item-title>讨论主题</v-list-item-title>
                      <v-list-item-subtitle>{{ roundtable.topic }}</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-package-variant" />
                      </template>
                      <v-list-item-title>预期产出</v-list-item-title>
                      <v-list-item-subtitle>{{ roundtable.deliverable || '-' }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
                <v-col cols="12" md="6">
                  <v-list density="compact">
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-account-group" />
                      </template>
                      <v-list-item-title>参会人数</v-list-item-title>
                      <v-list-item-subtitle>{{ roundtable.participants?.length || 0 }} 人</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-rotate-right" />
                      </template>
                      <v-list-item-title>讨论轮数</v-list-item-title>
                      <v-list-item-subtitle>{{ roundtable.rounds }} 轮</v-list-item-subtitle>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon icon="mdi-file-export" />
                      </template>
                      <v-list-item-title>导出格式</v-list-item-title>
                      <v-list-item-subtitle>{{ roundtable.export_format === 'word' ? 'Word' : 'Markdown' }}</v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card v-if="roundtable.preparation_records?.length > 0 || roundtable.materials?.type">
            <v-card-title>
              <v-icon icon="mdi-book-open-variant" class="mr-2" />
              材料准备
            </v-card-title>
            <v-card-text>
              <v-alert v-if="roundtable.materials?.type" type="info" variant="tonal" density="compact" class="mb-3">
                材料类型: {{ materialsTypeLabel }}
              </v-alert>
              <v-timeline density="compact" v-if="roundtable.preparation_records?.length > 0">
                <v-timeline-item
                  v-for="(record, idx) in roundtable.preparation_records"
                  :key="idx"
                  dot-color="primary"
                  size="small"
                >
                  <div class="text-subtitle-2">{{ record.question }}</div>
                  <div class="text-body-2 text-grey">{{ record.answer }}</div>
                </v-timeline-item>
              </v-timeline>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- 进行阶段 -->
      <v-row v-if="activeStageTab === 'running'">
        <v-col cols="12">
          <template v-if="roundtable.status === 'pending'">
            <v-card class="mb-4">
              <v-card-text class="text-center py-8">
                <v-icon icon="mdi-table-chair" size="60" color="primary" class="mb-4" />
                <div class="text-h6 mb-2">
                  {{ $t('agent.roundtables.execution.readyTitle') }}
                </div>
                <div class="text-body-1 text-grey mb-4">
                  {{ $t('agent.roundtables.execution.readyDesc') }}
                </div>
                <v-btn
                  color="primary"
                  size="large"
                  :loading="executing"
                  @click="startExecution"
                >
                  <v-icon start icon="mdi-play" />
                  {{ $t('agent.roundtables.actions.startExecution') }}
                </v-btn>
              </v-card-text>
            </v-card>
          </template>

          <template v-if="roundtable.status === 'running' || chatMessages.length > 0">
            <v-card class="mb-4">
              <v-card-text>
                <div class="d-flex align-center justify-space-between mb-4">
                  <div>
                    <div class="text-h6">{{ $t('agent.roundtables.execution.progressTitle') }}</div>
                    <div class="text-body-2 text-grey mt-1">
                      {{ $t('agent.roundtables.execution.currentRound', { current: roundtable.current_round || 0, total: roundtable.rounds }) }}
                    </div>
                  </div>
                  <div class="text-right">
                    <v-chip color="info" size="large" variant="tonal" class="mb-1">
                      <v-icon start icon="mdi-account-voice" />
                      {{ roundtable.current_speaker || '-' }}
                    </v-chip>
                    <div class="text-caption text-grey mt-1">
                      <v-icon size="x-small" icon="mdi-clock-outline" class="mr-1" />
                      已运行 {{ elapsedDisplay }}
                    </div>
                  </div>
                </div>
                <v-progress-linear
                  :model-value="executionProgress"
                  color="primary"
                  height="24"
                  rounded
                  striped
                  :indeterminate="executionProgress === 0"
                >
                  <template v-slot:default>
                    <span class="text-white font-weight-medium">{{ executionProgress }}%</span>
                  </template>
                </v-progress-linear>
              </v-card-text>
            </v-card>

            <v-card>
              <v-card-title class="d-flex align-center">
                <v-icon icon="mdi-forum" class="mr-2" />
                {{ $t('agent.roundtables.execution.liveDiscussion') }}
                <v-spacer />
                <v-chip size="small" color="success" variant="tonal" v-if="isPolling">
                  <v-icon start icon="mdi-rss" size="small" />
                  {{ $t('agent.roundtables.execution.live') }}
                </v-chip>
              </v-card-title>
              <v-card-text class="pa-0">
                <div style="height: 60vh;">
                  <AgentChatPanel
                    ref="chatPanel"
                    :messages="chatMessages"
                    :sending="false"
                    :show-input="false"
                    :show-round-divider="true"
                    empty-text="等待讨论开始..."
                  />
                </div>
              </v-card-text>
            </v-card>
          </template>

          <template v-if="roundtable.status === 'failed'">
            <v-card class="mb-4">
              <v-card-text class="text-center py-8">
                <v-icon icon="mdi-alert-circle" size="60" color="error" class="mb-4" />
                <div class="text-h6 mb-2 text-error">
                  {{ $t('agent.roundtables.status.failed') }}
                </div>
                <div class="text-body-1 text-grey mb-4">
                  {{ roundtable.result?.error || t('agent.roundtables.execution.noError') }}
                </div>
                <v-btn
                  color="primary"
                  size="large"
                  @click="retryExecution"
                  class="mr-2"
                >
                  <v-icon start icon="mdi-replay" />
                  {{ $t('agent.roundtables.actions.retry') }}
                </v-btn>
              </v-card-text>
            </v-card>
          </template>
        </v-col>
      </v-row>

      <!-- 完成阶段 -->
      <v-row v-if="activeStageTab === 'completed'">
        <v-col cols="12">
          <v-card class="mb-4">
            <v-card-title class="d-flex align-center">
              <v-icon icon="mdi-file-document" class="mr-2" />
              会议纪要
              <v-spacer />
              <v-btn
                size="small"
                variant="outlined"
                @click="exportDocument('summary')"
                class="mr-2"
              >
                <v-icon start icon="mdi-download" />
                导出纪要
              </v-btn>
            </v-card-title>
            <v-card-text>
              <v-card variant="outlined" class="pa-4 mb-4" color="success-lighten-5">
                <pre class="text-body-1" style="white-space: pre-wrap; word-break: break-word; margin: 0; font-family: inherit;">{{ finalSummary }}</pre>
              </v-card>
            </v-card-text>
          </v-card>

          <v-card v-if="deliverableContent" class="mb-4">
            <v-card-title class="d-flex align-center">
              <v-icon icon="mdi-package-variant" class="mr-2" />
              会议交付物
              <v-spacer />
              <v-btn
                size="small"
                variant="outlined"
                @click="exportDocument('deliverable')"
                class="mr-2"
              >
                <v-icon start icon="mdi-download" />
                导出交付物
              </v-btn>
            </v-card-title>
            <v-card-text>
              <v-card variant="outlined" class="pa-4" color="primary-lighten-5">
                <pre class="text-body-1" style="white-space: pre-wrap; word-break: break-word; margin: 0; font-family: inherit;">{{ deliverableContent }}</pre>
              </v-card>
            </v-card-text>
          </v-card>

          <v-card v-if="roundtable?.status === 'completed'" class="mb-4">
            <v-card-title class="d-flex align-center">
              <v-icon icon="mdi-restart" class="mr-2" />
              续会操作
            </v-card-title>
            <v-card-text>
              <v-alert type="info" variant="tonal" density="compact" class="mb-3">
                如果对会议结果不满意，可以提交验收意见后继续开会。续会后会议将回到待执行状态，历史讨论记录会保留。
              </v-alert>
              <v-textarea
                v-model="continueFormData.review_comment"
                label="验收意见"
                placeholder="请输入对本次会议结果的验收意见，例如：方案不够具体，需要进一步细化行动项..."
                rows="3"
                auto-grow
                class="mb-3"
              />
              <v-text-field
                v-model="continueFormData.additional_topic"
                label="追加议题（可选）"
                placeholder="如有需要追加讨论的议题，请在此输入"
                class="mb-3"
              />
              <div class="d-flex align-center mb-3">
                <span class="text-body-2 mr-4">额外增加轮数：</span>
                <v-slider
                  v-model="continueFormData.additional_rounds"
                  :min="1"
                  :max="5"
                  :step="1"
                  thumb-label
                  style="max-width: 200px;"
                  class="mr-4"
                />
                <v-chip size="small">{{ continueFormData.additional_rounds }} 轮</v-chip>
              </div>
              <v-btn
                color="primary"
                variant="outlined"
                @click="continueMeeting"
                :loading="continuing"
                :disabled="!continueFormData.review_comment"
              >
                <v-icon start icon="mdi-restart" />
                提交验收意见并续会
              </v-btn>
            </v-card-text>
          </v-card>

          <v-card>
            <v-card-title>
              <v-icon icon="mdi-forum" class="mr-2" />
              {{ $t('agent.roundtables.execution.discussionRecords') }}
            </v-card-title>
            <v-card-text class="pa-0">
              <div style="height: 60vh;">
                <AgentChatPanel
                  :messages="chatMessages"
                  :sending="false"
                  :show-input="false"
                  :show-round-divider="true"
                  empty-text="暂无讨论记录"
                />
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { useI18n } from 'vue-i18n';
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue';
import type { ChatMessage } from '@/components/agent/AgentChatPanel.vue';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const loading = ref(true);
const refreshing = ref(false);
const executing = ref(false);
const roundtable = ref<any>(null);
const chatMessages = ref<ChatMessage[]>([]);
const chatPanel = ref<InstanceType<typeof AgentChatPanel> | null>(null);
const activeStageTab = ref('preparation');
const continuing = ref(false);
const continueFormData = ref({
  review_comment: '',
  additional_rounds: 2,
  additional_topic: '',
});

let abortController: AbortController | null = null;
const isPolling = ref(false);
const executionStartedAt = ref<number>(0);
const elapsedSeconds = ref(0);
let elapsedTimer: ReturnType<typeof setInterval> | null = null;

const elapsedDisplay = computed(() => {
  const s = elapsedSeconds.value;
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}m ${sec}s`;
});

function startElapsedTimer() {
  executionStartedAt.value = Date.now();
  elapsedSeconds.value = 0;
  if (elapsedTimer) clearInterval(elapsedTimer);
  elapsedTimer = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - executionStartedAt.value) / 1000);
  }, 1000);
}

function stopElapsedTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; }
}

const executionProgress = computed(() => {
  if (!roundtable.value) return 0;
  if (roundtable.value.status === 'completed') return 100;
  if (roundtable.value.status === 'pending') return 0;
  const total = roundtable.value.rounds * (roundtable.value.participants?.length || 1) * 2 + roundtable.value.rounds;
  const completed = chatMessages.value.length;
  return Math.min(Math.round((completed / total) * 100), 99);
});

const finalSummary = computed(() => {
  if (!roundtable.value?.result?.summary) return '';
  const summary = roundtable.value.result.summary;
  if (typeof summary === 'string') return summary;
  if (summary.conclusions) {
    const parts = [];
    parts.push(`# ${t('agent.roundtables.execution.conclusions')}\n${summary.conclusions}`);
    if (summary.actionItems?.length) {
      parts.push(`\n# ${t('agent.roundtables.execution.actionItems')}\n${summary.actionItems.map((item: string) => `- ${item}`).join('\n')}`);
    }
    if (summary.decisions?.length) {
      parts.push(`\n# ${t('agent.roundtables.execution.decisions')}\n${summary.decisions.map((item: string) => `- ${item}`).join('\n')}`);
    }
    return parts.join('\n\n');
  }
  return JSON.stringify(summary, null, 2);
});

const deliverableContent = computed(() => {
  return roundtable.value?.result?.deliverable || '';
});

const materialsTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    url: '链接资料',
    file: '文件资料',
    manual: '人工补充',
  };
  return labels[roundtable.value?.materials?.type] || '';
});

function convertRecordsToMessages(records: any[]): ChatMessage[] {
  const messageMap = new Map<string, ChatMessage>();
  const messages: ChatMessage[] = [];

  for (const record of records) {
    const key = `${record.speaker || 'system'}_${record.round || 0}`;
    const existing = messageMap.get(key);

    if (record.type === 'thinking') {
      if (existing) {
        existing.thinking = record.content;
        existing.thinkingDone = !record.streaming;
      } else {
        const msg: ChatMessage = {
          id: `msg-${messages.length}-${key}`,
          role: 'assistant',
          content: '',
          speaker: record.speaker,
          round: record.round,
          thinking: record.content,
          thinkingDone: !record.streaming,
          streaming: record.streaming || false,
          created_at: Date.now(),
        };
        messageMap.set(key, msg);
        messages.push(msg);
      }
    } else {
      if (existing) {
        if (record.content) existing.content = record.content;
        if (record.type) existing.type = record.type;
        existing.streaming = record.streaming || false;
        existing.thinkingDone = true;
      } else {
        const msg: ChatMessage = {
          id: `msg-${messages.length}-${key}`,
          role: 'assistant',
          content: record.content || '',
          speaker: record.speaker,
          round: record.round,
          type: record.type,
          streaming: record.streaming || false,
          thinkingDone: true,
          created_at: Date.now(),
        };
        messageMap.set(key, msg);
        messages.push(msg);
      }
    }
  }

  return messages;
}

function findOrCreateMessage(speaker: string, round: number, type?: string): ChatMessage {
  let idx = chatMessages.value.findIndex(
    (m) => m.speaker === speaker && m.round === round
  );
  if (idx >= 0) return chatMessages.value[idx];

  const msg: ChatMessage = {
    id: `msg-${Date.now()}-${speaker}_${round}`,
    role: 'assistant',
    content: '',
    speaker,
    round,
    type: type || 'speech',
    streaming: true,
    thinkingDone: true,
    created_at: Date.now(),
    _stats: null,
  };
  chatMessages.value.push(msg);
  return msg;
}

async function loadRoundtable() {
  const id = route.params.id as string;
  if (!id) return;

  refreshing.value = true;
  try {
    const response = await axios.get(`/api/plug/agent/roundtables/${id}`);
    if (response.data.status === 'ok') {
      const data = response.data.data;
      roundtable.value = data;

      let records = data.discussion_records || [];
      if (records.length === 0 && data.result?.discussion_rounds?.length > 0) {
        records = rebuildRecordsFromRounds(data.result.discussion_rounds, data);
      }
      if (records.length > 0 && records.length >= chatMessages.value.length) {
        chatMessages.value = convertRecordsToMessages(records);
      }
    }
  } catch (error) {
    console.error('Failed to load roundtable:', error);
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

function rebuildRecordsFromRounds(rounds: any[], data: any): any[] {
  const records: any[] = [];
  const hostName = data.has_moderator ? '主持人' : '系统';

  for (const r of rounds) {
    if (typeof r.content === 'string' && !r.speaker) {
      records.push({
        round: r.round,
        speaker: hostName,
        content: r.content,
        type: 'speech',
      });
    } else if (r.speaker) {
      let recordType = 'speech';
      if (r.type) {
        recordType = r.type;
      } else if (r.speaker === '主持人') {
        if (r.content && r.type !== 'opening' && r.type !== 'summary') {
          recordType = 'summary';
        }
      }
      records.push({
        round: r.round,
        speaker: r.speaker,
        content: r.content || '',
        type: recordType,
      });
    } else if (r.opening) {
      records.push({ round: r.round, speaker: hostName, content: r.opening, type: 'opening' });
      for (const s of (r.speeches || [])) {
        records.push({
          round: r.round,
          speaker: s.agent_name || '',
          content: s.content || '',
          type: s.role || 'speech',
        });
      }
      if (r.summary) {
        records.push({ round: r.round, speaker: hostName, content: r.summary, type: 'summary' });
      }
      if (r.votes) {
        for (const v of r.votes) {
          records.push({
            round: r.round,
            speaker: v.agent_name || '',
            content: `投票给: ${v.vote || ''}`,
            type: 'vote',
          });
        }
      }
    }
  }
  return records;
}

async function startExecution() {
  if (!roundtable.value) return;

  executing.value = true;
  try {
    const response = await axios.post(`/api/plug/agent/roundtables/${roundtable.value.id}/execute`, {});
    if (response.data.status === 'ok') {
      activeStageTab.value = 'running';
      startElapsedTimer();
      await loadRoundtable();
      startPolling();
    } else {
      alert(response.data.message || t('agent.roundtables.messages.executionError'));
    }
  } catch (error: any) {
    console.error('Failed to execute roundtable:', error);
    alert(error.response?.data?.message || t('agent.roundtables.messages.executionError'));
  } finally {
    executing.value = false;
  }
}

async function retryExecution() {
  await startExecution();
}

function goBack() {
  router.push('/roundtables');
}

function exportResult() {
  if (!roundtable.value) return;

  const data = {
    roundtable: roundtable.value,
    discussion_records: chatMessages.value,
    summary: roundtable.value.result?.summary,
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `roundtable_${roundtable.value.name}_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportDocument(type: 'summary' | 'deliverable') {
  if (!roundtable.value) return;

  try {
    const response = await axios.post(
      `/api/plug/agent/roundtables/${roundtable.value.id}/export`,
      {
        type,
        format: roundtable.value.export_format || 'markdown',
      },
      { responseType: 'blob' }
    );

    const blob = new Blob([response.data]);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ext = roundtable.value.export_format === 'word' ? 'docx' : 'md';
    const name = type === 'deliverable' ? '交付物' : '会议纪要';
    a.download = `${roundtable.value.name}_${name}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Failed to export document:', error);
    alert('导出失败');
  }
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'grey',
    running: 'info',
    completed: 'success',
    failed: 'error',
  };
  return colors[status] || 'grey';
}

function getStatusIcon(status: string): string {
  const icons: Record<string, string> = {
    pending: 'mdi-clock-outline',
    running: 'mdi-progress-clock',
    completed: 'mdi-check-circle',
    failed: 'mdi-alert-circle',
  };
  return icons[status] || 'mdi-help-circle';
}

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

async function startPolling() {
  if (abortController) return;
  if (!roundtable.value || roundtable.value.status !== 'running') return;

  isPolling.value = true;
  const id = roundtable.value.id;

  abortController = new AbortController();

  try {
    const response = await fetch(`/api/plug/agent/roundtables/${id}/stream`, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
      },
      signal: abortController.signal,
    });

    if (!response.ok || !response.body) {
      console.error(`SSE connection failed: HTTP ${response.status}`);
      isPolling.value = false;
      abortController = null;
      if (roundtable.value?.status === 'running') {
        setTimeout(() => {
          if (roundtable.value?.status === 'running') {
            startPolling();
          }
        }, 3000);
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      let currentEventType = '';
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6);
          if (jsonStr.trim() && currentEventType !== 'heartbeat') {
            try {
              const event = JSON.parse(jsonStr);
              handleSSEEvent(event);
            } catch (err) {
              console.error('Failed to parse SSE event:', jsonStr, err);
            }
          }
        } else if (line.trim() === '') {
          currentEventType = '';
        }
      }
    }

    isPolling.value = false;
    abortController = null;

    if (roundtable.value?.status === 'running') {
      setTimeout(() => {
        if (roundtable.value?.status === 'running') {
          startPolling();
        }
      }, 3000);
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      // 主动中断
    } else {
      console.error('SSE connection error:', error);
      if (roundtable.value?.status === 'running') {
        setTimeout(() => {
          if (roundtable.value?.status === 'running') {
            startPolling();
          }
        }, 3000);
      }
    }
    isPolling.value = false;
    abortController = null;
  }
}

function stopPolling() {
  disconnectSSE();
}

function disconnectSSE() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  isPolling.value = false;
}

function handleSSEEvent(event: any) {
  if (!roundtable.value) return;

  switch (event.type) {
    case 'status':
      if (event.data?.status) {
        roundtable.value.status = event.data.status;
      }
      break;

    case 'round_start':
      if (event.data?.round) {
        roundtable.value.current_round = event.data.round;
      }
      break;

    case 'speaker_start':
      if (event.data?.speaker) {
        roundtable.value.current_speaker = event.data.speaker;
      }
      break;

    case 'agent_speech_chunk':
      if (event.data?.agent_name && event.data?.content) {
        const msg = findOrCreateMessage(
          event.data.agent_name,
          event.data.round || roundtable.value.current_round,
          event.data.phase
        );
        msg.content += event.data.content;
        msg.streaming = true;
        nextTick(() => chatPanel.value?.scrollToBottom());
      }
      break;

    case 'agent_thinking':
      if (event.data?.agent_name && event.data?.content) {
        const msg = findOrCreateMessage(
          event.data.agent_name,
          event.data.round || roundtable.value.current_round
        );
        msg.thinking = (msg.thinking || '') + event.data.content;
        msg.thinkingDone = false;
        msg.streaming = true;
        nextTick(() => chatPanel.value?.scrollToBottom());
      }
      break;

    case 'tool_call':
      if (event.data?.name && event.data?.agent_name) {
        const msg = findOrCreateMessage(
          event.data.agent_name,
          event.data.round || roundtable.value.current_round
        );
        if (!msg.toolCalls) msg.toolCalls = [];
        const existing = msg.toolCalls.find(tc => tc.name === event.data.name && tc.status === 'running');
        if (!existing) {
          msg.toolCalls.push({ name: event.data.name, status: 'running', ts: Date.now() / 1000 });
        }
        nextTick(() => chatPanel.value?.scrollToBottom());
      }
      break;

    case 'tool_result':
      if (event.data?.name && event.data?.agent_name) {
        const msg = findOrCreateMessage(
          event.data.agent_name,
          event.data.round || roundtable.value.current_round
        );
        if (msg.toolCalls) {
          const tc = msg.toolCalls.find(t => t.name === event.data.name && t.status === 'running');
          if (tc) {
            tc.status = 'done';
            tc.result = event.data.content || event.data.result;
            tc.finished_ts = Date.now() / 1000;
          } else {
            msg.toolCalls.push({
              name: event.data.name,
              result: event.data.content || event.data.result,
              status: 'done',
              ts: Date.now() / 1000,
              finished_ts: Date.now() / 1000,
            });
          }
        }
        nextTick(() => chatPanel.value?.scrollToBottom());
      }
      break;

    case 'agent_speech':
      if (event.data?.agent_name) {
        const msg = chatMessages.value.find(
          (m) => m.speaker === event.data.agent_name && m.streaming
        );
        if (msg) {
          msg.streaming = false;
          msg.thinkingDone = true;
          if (event.data.content) msg.content = event.data.content;
        }
      }
      break;

    case 'speaker_chunk':
      if (event.data?.speaker && event.data?.chunk) {
        const msg = findOrCreateMessage(
          event.data.speaker,
          event.data.round || roundtable.value.current_round
        );
        msg.content = event.data.full_text || (msg.content + event.data.chunk);
        msg.streaming = true;
        nextTick(() => chatPanel.value?.scrollToBottom());
      }
      break;

    case 'speaker_end':
      if (event.data?.speaker) {
        const msg = chatMessages.value.find(
          (m) => m.speaker === event.data.speaker && m.streaming
        );
        if (msg) {
          msg.streaming = false;
          msg.thinkingDone = true;
          if (event.data.content) msg.content = event.data.content;
        }
      }
      break;

    case 'round_end':
      break;

    case 'completed':
      stopElapsedTimer();
      roundtable.value.status = 'completed';
      if (event.data) { roundtable.value.result = event.data; }
      disconnectSSE();
      loadRoundtable();
      break;

    case 'error':
      stopElapsedTimer();
      roundtable.value.status = 'failed';
      disconnectSSE();
      loadRoundtable();
      break;
  }
}

function togglePolling() {
  if (isPolling.value) {
    stopPolling();
  } else {
    startPolling();
  }
}

async function continueMeeting() {
  if (!roundtable.value || !continueFormData.value.review_comment) return;

  continuing.value = true;
  try {
    const response = await axios.post(
      `/api/plug/agent/roundtables/${roundtable.value.id}/continue`,
      {
        review_comment: continueFormData.value.review_comment,
        additional_rounds: continueFormData.value.additional_rounds,
        additional_topic: continueFormData.value.additional_topic,
      }
    );
    if (response.data.status === 'ok') {
      await loadRoundtable();
      activeStageTab.value = 'running';
      continueFormData.value = {
        review_comment: '',
        additional_rounds: 2,
        additional_topic: '',
      };
    } else {
      alert(response.data.message || '续会失败');
    }
  } catch (error: any) {
    console.error('Failed to continue meeting:', error);
    alert(error.response?.data?.message || '续会失败');
  } finally {
    continuing.value = false;
  }
}

onMounted(() => {
  loadRoundtable().then(() => {
    if (roundtable.value?.status === 'running') {
      startPolling();
    }
  });
});

onUnmounted(() => {
  disconnectSSE();
});
</script>

<style scoped>
.v-card {
  border-radius: 12px;
}
</style>
