<template>
  <v-container fluid class="pa-6">
    <!-- 加载状态 -->
    <v-row v-if="loading">
      <v-col cols="12" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" />
        <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>
      </v-col>
    </v-row>

    <!-- 圆桌会议不存在 -->
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

    <!-- 执行与结果展示 -->
    <template v-else>
      <!-- 页面标题 -->
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

      <!-- 三阶段标签页 -->
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

          <!-- 材料准备记录 -->
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
          <!-- 待执行 -->
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

          <!-- 执行中/已完成/失败的讨论记录（只要有记录就显示） -->
          <template v-if="roundtable.status === 'running' || discussionRecords.length > 0">
            <!-- 进度卡片 -->
            <v-card class="mb-4">
              <v-card-text>
                <div class="d-flex align-center justify-space-between mb-4">
                  <div>
                    <div class="text-h6">
                      {{ $t('agent.roundtables.execution.progressTitle') }}
                    </div>
                    <div class="text-body-2 text-grey mt-1">
                      {{ $t('agent.roundtables.execution.currentRound', { current: roundtable.current_round || 0, total: roundtable.rounds }) }}
                    </div>
                  </div>
                  <v-chip color="info" size="large" variant="tonal">
                    <v-icon start icon="mdi-account-voice" />
                    {{ roundtable.current_speaker || '-' }}
                  </v-chip>
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

            <!-- 实时讨论流 -->
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
              <v-card-text>
                <div ref="discussionContainer" class="discussion-stream">
                  <template v-for="(record, index) in discussionRecords" :key="index">
                    <div v-if="isNewRound(index)" class="round-divider">
                      <v-divider class="my-4" />
                      <div class="text-center">
                        <v-chip color="primary" variant="tonal" size="small">
                          <v-icon start icon="mdi-rotate-right" size="small" />
                          {{ $t('agent.roundtables.execution.round', { round: record.round }) }}
                        </v-chip>
                      </div>
                    </div>

                    <div
                      class="speech-item mb-4"
                      :class="{ 'fade-in': index >= previousRecordCount }"
                    >
                      <div class="d-flex align-start">
                        <v-avatar
                          :color="getSpeakerColor(record.speaker)"
                          size="36"
                          class="mr-3 mt-1"
                        >
                          <v-icon :icon="getSpeakerIcon(record.type)" size="small" />
                        </v-avatar>

                        <div class="flex-grow-1">
                          <div class="d-flex align-center mb-1">
                            <span class="text-subtitle-2 font-weight-medium">{{ record.speaker }}</span>
                            <v-chip
                              v-if="record.type === 'thinking'"
                              size="x-small"
                              :color="record.streaming ? 'warning' : 'success'"
                              variant="tonal"
                              class="ml-2"
                            >
                              <v-icon start size="x-small">{{ record.streaming ? 'mdi-head-lightbulb-outline' : 'mdi-head-lightbulb' }}</v-icon>
                              {{ record.streaming ? '思考中' : '思考过程' }}
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'opening' || record.type === 'guide'"
                              size="x-small"
                              color="info"
                              variant="tonal"
                              class="ml-2"
                            >
                              引导
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'summary' || record.type === 'integration' || record.type === 'filter'"
                              size="x-small"
                              color="warning"
                              variant="tonal"
                              class="ml-2"
                            >
                              总结
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'speech'"
                              size="x-small"
                              color="primary"
                              variant="tonal"
                              class="ml-2"
                            >
                              发言
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'vote'"
                              size="x-small"
                              color="purple"
                              variant="tonal"
                              class="ml-2"
                            >
                              投票
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'question'"
                              size="x-small"
                              color="teal"
                              variant="tonal"
                              class="ml-2"
                            >
                              提问
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'answer'"
                              size="x-small"
                              color="green"
                              variant="tonal"
                              class="ml-2"
                            >
                              回答
                            </v-chip>
                            <v-chip
                              v-else-if="record.type === 'evaluation'"
                              size="x-small"
                              color="orange"
                              variant="tonal"
                              class="ml-2"
                            >
                              评估
                            </v-chip>
                          </div>
                          <v-card
                            v-if="record.type === 'thinking'"
                            variant="outlined"
                            class="pa-3 thinking-record-card"
                          >
                            <v-expansion-panels density="compact">
                              <v-expansion-panel>
                                <v-expansion-panel-title class="pa-2">
                                  <div class="d-flex align-center ga-1">
                                    <v-progress-circular v-if="record.streaming" indeterminate size="12" width="2" color="warning" />
                                    <v-icon v-else size="x-small" color="success">mdi-head-lightbulb</v-icon>
                                    <span class="text-caption">{{ record.streaming ? '正在思考...' : '查看思考过程' }}</span>
                                  </div>
                                </v-expansion-panel-title>
                                <v-expansion-panel-text>
                                  <pre class="text-body-2 thinking-record-text">{{ record.content }}</pre>
                                </v-expansion-panel-text>
                              </v-expansion-panel>
                            </v-expansion-panels>
                          </v-card>
                          <v-card
                            v-else
                            :variant="record.type === 'summary' ? 'elevated' : 'outlined'"
                            :color="record.type === 'summary' ? 'warning-lighten-5' : undefined"
                            class="pa-3"
                          >
                            <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word; margin: 0; font-family: inherit;">{{ record.content }}</pre>
                          </v-card>
                        </div>
                      </div>
                    </div>
                  </template>

                  <div v-if="discussionRecords.length === 0" class="text-center py-8 text-grey">
                    <v-progress-circular indeterminate color="primary" class="mb-2" />
                    <div>{{ $t('agent.roundtables.execution.waitingStart') }}</div>
                  </div>

                  <div v-else-if="roundtable.status === 'running'" class="thinking-indicator pa-3">
                    <div class="d-flex align-center">
                      <v-avatar color="grey-lighten-2" size="32" class="mr-3">
                        <v-icon icon="mdi-dots-horizontal" size="small" />
                      </v-avatar>
                      <div>
                        <div class="text-body-2 text-grey">
                          {{ roundtable.current_speaker }} {{ $t('agent.roundtables.execution.thinking') }}
                        </div>
                        <v-progress-linear
                          indeterminate
                          color="primary"
                          height="2"
                          class="mt-1"
                          style="width: 120px;"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </template>

          <!-- 执行失败 -->
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
          <!-- 会议纪要 -->
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

          <!-- 会议交付物 -->
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

          <!-- 续会操作 -->
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

          <!-- 完整讨论记录 -->
          <v-card>
            <v-card-title>
              <v-icon icon="mdi-forum" class="mr-2" />
              {{ $t('agent.roundtables.execution.discussionRecords') }}
            </v-card-title>
            <v-card-text>
              <div class="discussion-stream">
                <template v-for="(record, index) in discussionRecords" :key="index">
                  <div v-if="isNewRound(index)" class="round-divider">
                    <v-divider class="my-4" />
                    <div class="text-center">
                      <v-chip color="primary" variant="tonal" size="small">
                        <v-icon start icon="mdi-rotate-right" size="small" />
                        {{ $t('agent.roundtables.execution.round', { round: record.round }) }}
                      </v-chip>
                    </div>
                  </div>

                  <div class="speech-item mb-4">
                    <div class="d-flex align-start">
                      <v-avatar
                        :color="getSpeakerColor(record.speaker)"
                        size="36"
                        class="mr-3 mt-1"
                      >
                        <v-icon :icon="getSpeakerIcon(record.type)" size="small" />
                      </v-avatar>

                      <div class="flex-grow-1">
                        <div class="d-flex align-center mb-1">
                          <span class="text-subtitle-2 font-weight-medium">{{ record.speaker }}</span>
                          <v-chip
                            v-if="record.type === 'thinking'"
                            size="x-small"
                            color="success"
                            variant="tonal"
                            class="ml-2"
                          >
                            <v-icon start size="x-small">mdi-head-lightbulb</v-icon>
                            思考过程
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'opening' || record.type === 'guide'"
                            size="x-small"
                            color="info"
                            variant="tonal"
                            class="ml-2"
                          >
                            引导
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'summary' || record.type === 'integration' || record.type === 'filter'"
                            size="x-small"
                            color="warning"
                            variant="tonal"
                            class="ml-2"
                          >
                            总结
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'speech'"
                            size="x-small"
                            color="primary"
                            variant="tonal"
                            class="ml-2"
                          >
                            发言
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'vote'"
                            size="x-small"
                            color="purple"
                            variant="tonal"
                            class="ml-2"
                          >
                            投票
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'question'"
                            size="x-small"
                            color="teal"
                            variant="tonal"
                            class="ml-2"
                          >
                            提问
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'answer'"
                            size="x-small"
                            color="green"
                            variant="tonal"
                            class="ml-2"
                          >
                            回答
                          </v-chip>
                          <v-chip
                            v-else-if="record.type === 'evaluation'"
                            size="x-small"
                            color="orange"
                            variant="tonal"
                            class="ml-2"
                          >
                            评估
                          </v-chip>
                        </div>
                        <v-card
                          v-if="record.type === 'thinking'"
                          variant="outlined"
                          class="pa-3 thinking-record-card"
                        >
                          <v-expansion-panels density="compact">
                            <v-expansion-panel>
                              <v-expansion-panel-title class="pa-2">
                                <div class="d-flex align-center ga-1">
                                  <v-icon size="x-small" color="success">mdi-head-lightbulb</v-icon>
                                  <span class="text-caption">查看思考过程</span>
                                </div>
                              </v-expansion-panel-title>
                              <v-expansion-panel-text>
                                <pre class="text-body-2 thinking-record-text">{{ record.content }}</pre>
                              </v-expansion-panel-text>
                            </v-expansion-panel>
                          </v-expansion-panels>
                        </v-card>
                        <v-card
                          v-else
                          :variant="record.type === 'summary' ? 'elevated' : 'outlined'"
                          :color="record.type === 'summary' ? 'warning-lighten-5' : undefined"
                          class="pa-3"
                        >
                          <pre class="text-body-2" style="white-space: pre-wrap; word-break: break-word; margin: 0; font-family: inherit;">{{ record.content }}</pre>
                        </v-card>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

// 状态
const loading = ref(true);
const refreshing = ref(false);
const executing = ref(false);
const roundtable = ref<any>(null);
const discussionRecords = ref<any[]>([]);
const previousRecordCount = ref(0);
const discussionContainer = ref<HTMLElement | null>(null);
const activeStageTab = ref('preparation');
const continuing = ref(false);
const continueFormData = ref({
  review_comment: '',
  additional_rounds: 2,
  additional_topic: '',
});

// SSE 连接
let abortController: AbortController | null = null;
const isPolling = ref(false);
const streamingContent = ref<Record<string, string>>({});

// 执行进度
const executionProgress = computed(() => {
  if (!roundtable.value) return 0;
  if (roundtable.value.status === 'completed') return 100;
  if (roundtable.value.status === 'pending') return 0;
  const total = roundtable.value.rounds * (roundtable.value.participants?.length || 1) * 2 + roundtable.value.rounds;
  const completed = discussionRecords.value.length;
  return Math.min(Math.round((completed / total) * 100), 99);
});

// 最终纪要
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

// 交付物内容
const deliverableContent = computed(() => {
  return roundtable.value?.result?.deliverable || '';
});

// 材料类型标签
const materialsTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    url: '链接资料',
    file: '文件资料',
    manual: '人工补充',
  };
  return labels[roundtable.value?.materials?.type] || '';
});

// 加载圆桌会议详情
async function loadRoundtable() {
  const id = route.params.id as string;
  if (!id) return;

  refreshing.value = true;
  try {
    const response = await axios.get(`/api/plug/agent/roundtables/${id}`);
    if (response.data.status === 'ok') {
      const data = response.data.data;
      previousRecordCount.value = discussionRecords.value.length;
      roundtable.value = data;

      // 优先使用 discussion_records，如果为空则从 result.discussion_rounds 重建
      let records = data.discussion_records || [];
      if (records.length === 0 && data.result?.discussion_rounds?.length > 0) {
        records = rebuildRecordsFromRounds(data.result.discussion_rounds, data);
      }
      discussionRecords.value = records;
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
    if (r.opening) {
      records.push({ round: r.round, speaker: hostName, content: r.opening, type: 'opening' });
    }
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
  return records;
}

// 监听讨论记录变化，自动滚动
watch(() => discussionRecords.value.length, (newVal, oldVal) => {
  if (newVal > oldVal) {
    nextTick(() => {
      scrollToBottom();
    });
  }
});

// 滚动到底部
function scrollToBottom() {
  if (discussionContainer.value) {
    discussionContainer.value.scrollTop = discussionContainer.value.scrollHeight;
  }
}

// 判断是否是新一轮的开始
function isNewRound(index: number): boolean {
  if (index === 0) return true;
  const current = discussionRecords.value[index];
  const prev = discussionRecords.value[index - 1];
  return current.round !== prev.round;
}

// 获取发言者颜色
function getSpeakerColor(speaker: string): string {
  const colors: Record<string, string> = {
    '系统': 'grey',
    '主持人': 'warning',
  };
  return colors[speaker] || 'primary';
}

// 获取发言图标
function getSpeakerIcon(type: string): string {
  const icons: Record<string, string> = {
    thinking: 'mdi-head-lightbulb',
    opening: 'mdi-microphone',
    speech: 'mdi-account-voice',
    summary: 'mdi-text-box-check',
    guide: 'mdi-compass',
    filter: 'mdi-filter',
    integration: 'mdi-merge',
    vote: 'mdi-vote',
    question: 'mdi-help-circle',
    answer: 'mdi-message-reply',
    evaluation: 'mdi-star-check',
  };
  return icons[type] || 'mdi-account';
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

// 开始执行圆桌会议
async function startExecution() {
  if (!roundtable.value) return;

  executing.value = true;
  try {
    const response = await axios.post(`/api/plug/agent/roundtables/${roundtable.value.id}/execute`, {});
    if (response.data.status === 'ok') {
      activeStageTab.value = 'running';
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

// 重试执行
async function retryExecution() {
  await startExecution();
}

// 返回列表
function goBack() {
  router.push('/roundtables');
}

// 导出结果
function exportResult() {
  if (!roundtable.value) return;

  const data = {
    roundtable: roundtable.value,
    discussion_records: discussionRecords.value,
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

// 导出文档（Markdown/Word）
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
      // 主动中断，不需要重连
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

// 停止 SSE 连接
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

// 处理 SSE 事件
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
        streamingContent.value[event.data.speaker] = '';
      }
      break;

    case 'agent_speech_chunk':
      if (event.data?.agent_name && event.data?.content) {
        const speaker = event.data.agent_name;
        if (!streamingContent.value[speaker]) {
          streamingContent.value[speaker] = '';
        }
        streamingContent.value[speaker] += event.data.content;

        const existingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === speaker && r.round === event.data.round && r.type === event.data.phase && r.streaming
        );
        if (existingIdx >= 0) {
          discussionRecords.value[existingIdx].content = streamingContent.value[speaker];
        } else {
          discussionRecords.value.push({
            round: event.data.round || roundtable.value.current_round,
            speaker: speaker,
            content: streamingContent.value[speaker],
            type: event.data.phase || 'speech',
            streaming: true,
          });
          previousRecordCount.value = discussionRecords.value.length - 1;
        }

        nextTick(() => {
          if (discussionContainer.value) {
            discussionContainer.value.scrollTop = discussionContainer.value.scrollHeight;
          }
        });
      }
      break;

    case 'agent_thinking':
      if (event.data?.agent_name && event.data?.content) {
        const speaker = event.data.agent_name;
        const thinkingKey = `thinking_${speaker}`;
        if (!streamingContent.value[thinkingKey]) {
          streamingContent.value[thinkingKey] = '';
        }
        streamingContent.value[thinkingKey] += event.data.content;

        const existingThinkingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === speaker && r.round === event.data.round && r.type === 'thinking' && r.streaming
        );
        if (existingThinkingIdx >= 0) {
          discussionRecords.value[existingThinkingIdx].content = streamingContent.value[thinkingKey];
        } else {
          discussionRecords.value.push({
            round: event.data.round || roundtable.value.current_round,
            speaker: speaker,
            content: streamingContent.value[thinkingKey],
            type: 'thinking',
            streaming: true,
          });
          previousRecordCount.value = discussionRecords.value.length - 1;
        }

        nextTick(() => {
          if (discussionContainer.value) {
            discussionContainer.value.scrollTop = discussionContainer.value.scrollHeight;
          }
        });
      }
      break;

    case 'agent_speech':
      if (event.data?.agent_name) {
        const speaker = event.data.agent_name;
        delete streamingContent.value[speaker];
        delete streamingContent.value[`thinking_${speaker}`];

        const streamingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === speaker && r.streaming && r.type !== 'thinking'
        );
        if (streamingIdx >= 0) {
          discussionRecords.value[streamingIdx].streaming = false;
          if (event.data.content) {
            discussionRecords.value[streamingIdx].content = event.data.content;
          }
        }

        const thinkingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === speaker && r.type === 'thinking' && r.streaming
        );
        if (thinkingIdx >= 0) {
          discussionRecords.value[thinkingIdx].streaming = false;
        }
      }
      break;

    case 'speaker_chunk':
      if (event.data?.speaker && event.data?.chunk) {
        const speaker = event.data.speaker;
        if (!streamingContent.value[speaker]) {
          streamingContent.value[speaker] = '';
        }
        streamingContent.value[speaker] = event.data.full_text || (streamingContent.value[speaker] + event.data.chunk);

        const existingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === speaker && r.round === event.data.round && r.type === 'speech'
        );
        if (existingIdx >= 0) {
          discussionRecords.value[existingIdx].content = streamingContent.value[speaker];
        } else {
          discussionRecords.value.push({
            round: event.data.round,
            speaker: speaker,
            content: streamingContent.value[speaker],
            type: 'speech',
          });
          previousRecordCount.value = discussionRecords.value.length - 1;
        }

        nextTick(() => {
          if (discussionContainer.value) {
            discussionContainer.value.scrollTop = discussionContainer.value.scrollHeight;
          }
        });
      }
      break;

    case 'speaker_end':
      if (event.data?.speaker) {
        delete streamingContent.value[event.data.speaker];
        delete streamingContent.value[`thinking_${event.data.speaker}`];

        const streamingIdx = discussionRecords.value.findIndex(
          (r: any) => r.speaker === event.data.speaker && r.streaming
        );
        if (streamingIdx >= 0) {
          discussionRecords.value[streamingIdx].streaming = false;
          if (event.data.content) {
            discussionRecords.value[streamingIdx].content = event.data.content;
          }
        }
      }
      break;

    case 'round_end':
      break;

    case 'completed':
      roundtable.value.status = 'completed';
      if (event.data) {
        roundtable.value.result = event.data;
      }
      disconnectSSE();
      loadRoundtable();
      break;

    case 'error':
      roundtable.value.status = 'failed';
      disconnectSSE();
      loadRoundtable();
      break;
  }
}

// 切换轮询状态
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
      // 续会成功，刷新数据并切换到进行阶段
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

.discussion-stream {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 8px;
}

.discussion-stream::-webkit-scrollbar {
  width: 6px;
}

.discussion-stream::-webkit-scrollbar-track {
  background: transparent;
}

.discussion-stream::-webkit-scrollbar-thumb {
  background-color: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.speech-item {
  transition: all 0.3s ease;
}

.fade-in {
  animation: fadeInUp 0.5s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.round-divider {
  margin: 16px 0;
}

.thinking-indicator {
  border-left: 3px solid var(--v-primary-base);
  margin-left: 18px;
  padding-left: 16px;
}

.thinking-record-card :deep(.v-expansion-panel) {
  background: rgba(255, 152, 0, 0.04);
  border: 1px solid rgba(255, 152, 0, 0.12);
  border-radius: 8px !important;
}

.thinking-record-card :deep(.v-expansion-panel-title) {
  min-height: 32px;
}

.thinking-record-text {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: monospace;
  font-size: 12px;
  color: #666;
  background: rgba(0, 0, 0, 0.05);
  padding: 8px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
