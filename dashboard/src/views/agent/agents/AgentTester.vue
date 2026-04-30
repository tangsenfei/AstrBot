<template>

  <v-dialog

    :model-value="modelValue"

    @update:model-value="$emit('update:modelValue', $event)"

    fullscreen

    scrollable

  >

    <v-card v-if="agent">

      <!-- 标题 -->

      <v-card-title class="d-flex align-center pa-4 border-b">

        <v-icon icon="mdi-message-text" class="mr-2" color="info" />

        {{ $t('agent.agents.tester.title') }}: {{ agent.name }}

        <v-chip v-if="agent.provider_id || agent.model_name" size="small" color="primary" variant="flat" class="ml-3">

          {{ agent.provider_id }} / {{ agent.model_name }}

        </v-chip>

        <v-spacer />

        <v-btn icon variant="text" @click="$emit('update:modelValue', false)">

          <v-icon icon="mdi-close" />

        </v-btn>

      </v-card-title>



      <v-card-text class="pa-0" style="height: calc(100vh - 140px);">

        <v-row no-gutters class="h-100">

          <!-- 左侧：对话历-->

          <v-col cols="12" md="8" class="d-flex flex-column border-e">

            <!-- 对话历史 -->

            <div ref="messagesContainer" class="flex-grow-1 overflow-y-auto pa-4">

              <div v-if="messages.length === 0" class="text-center py-12">

                <v-icon icon="mdi-chat-outline" size="64" color="grey-lighten-1" class="mb-4" />

                <p class="text-grey">{{ $t('agent.agents.tester.emptyMessage') }}</p>

              </div>



              <div v-else>

                <div

                  v-for="(message, index) in messages"

                  :key="index"

                  class="mb-4"

                >

                  <!-- 用户消息 -->

                  <div v-if="message.role === 'user'" class="d-flex justify-end">

                    <v-card color="primary" variant="flat" max-width="70%" class="message-card">

                      <v-card-text class="text-white">

                        <pre class="message-text">{{ message.content }}</pre>

                      </v-card-text>

                    </v-card>

                  </div>



                  <!-- 助手消息 -->
                  <div v-else class="d-flex justify-start">
                    <v-card variant="outlined" max-width="70%" class="message-card">
                      <v-card-text>
                        <div v-if="message.planning_steps" class="planning-steps mb-2">
                          <v-expansion-panels density="compact">
                            <v-expansion-panel>
                              <v-expansion-panel-title class="pa-2">
                                <div class="d-flex align-center ga-1">
                                  <v-icon size="x-small" color="primary">mdi-clipboard-list-outline</v-icon>
                                  <span class="text-caption">执行计划</span>
                                </div>
                              </v-expansion-panel-title>
                              <v-expansion-panel-text class="planning-content">
                                <div class="text-body-2 text-medium-emphasis" style="white-space: pre-wrap;">{{ message.planning_steps }}</div>
                              </v-expansion-panel-text>
                            </v-expansion-panel>
                          </v-expansion-panels>
                        </div>
                        <div v-if="message.thinking" class="thinking-section mb-2">
                          <v-expansion-panels density="compact" :model-value="!message.thinkingDone ? [0] : []">
                            <v-expansion-panel value="0">
                              <v-expansion-panel-title class="pa-2">
                                <div class="d-flex align-center ga-1">
                                  <v-icon size="x-small" :color="message.thinkingDone ? 'success' : 'warning'">
                                    {{ message.thinkingDone ? 'mdi-head-lightbulb' : 'mdi-head-lightbulb-outline' }}
                                  </v-icon>
                                  <span class="text-caption">{{ message.thinkingDone ? '思考过程' : '正在思考...' }}</span>
                                </div>
                              </v-expansion-panel-title>
                              <v-expansion-panel-text class="thinking-content">
                                <pre class="thinking-text">{{ message.thinking }}</pre>
                              </v-expansion-panel-text>
                            </v-expansion-panel>
                          </v-expansion-panels>
                        </div>
                        <pre class="message-text">{{ message.content }}</pre>
                        <div v-if="message.tools && message.tools.length > 0" class="mt-2 pt-2 border-t">
                          <div class="text-caption text-grey mb-1">
                            <v-icon icon="mdi-tools" size="small" class="mr-1" />
                            {{ $t('agent.agents.tester.toolsUsed') }}
                          </div>
                          <v-chip
                            v-for="tool in message.tools"
                            :key="tool"
                            size="x-small"
                            color="primary"
                            variant="flat"
                            class="mr-1"
                          >
                            {{ tool }}
                          </v-chip>
                        </div>
                        <div v-if="message.memory_used && message.memory_used > 0" class="memory-info mt-1">
                          <v-chip size="x-small" variant="tonal" color="info" label>
                            <v-icon start size="x-small">mdi-brain</v-icon>
                            使用了 {{ message.memory_used }} 条记忆
                          </v-chip>
                        </div>
                      </v-card-text>
                    </v-card>
                  </div>

                </div>



                <!-- 加载-->

                <div v-if="sending" class="d-flex justify-start mb-4">

                  <v-card variant="outlined" max-width="70%" class="message-card">

                    <v-card-text>

                      <v-progress-circular indeterminate size="20" width="2" class="mr-2" />

                      <span class="text-grey">{{ $t('agent.agents.tester.thinking') }}...</span>

                    </v-card-text>

                  </v-card>

                </div>

              </div>

            </div>



            <!-- 输入区域 -->

            <div class="border-t pa-4">

              <v-textarea

                v-model="inputMessage"

                :placeholder="$t('agent.agents.tester.inputPlaceholder')"

                rows="2"

                auto-grow

                max-rows="6"

                variant="outlined"

                :disabled="sending"

                @keydown.enter.ctrl="sendMessage"

              />

              <div class="d-flex justify-space-between align-center mt-2">

                <span class="text-caption text-grey">

                  {{ $t('agent.agents.tester.hint') }}

                </span>

                <v-btn
                  v-if="!sending"
                  color="primary"
                  @click="sendMessage"
                  :disabled="!inputMessage.trim()"
                >
                  <v-icon start icon="mdi-send" />
                  {{ $t('agent.agents.tester.send') }}
                </v-btn>
                <v-btn
                  v-else
                  color="error"
                  @click="stopGeneration"
                >
                  <v-icon start icon="mdi-stop" />
                  停止
                </v-btn>

              </div>

            </div>

          </v-col>



          <!-- 右侧：智能体配置 -->

          <v-col cols="12" md="4" class="pa-4 overflow-y-auto">

            <div class="text-subtitle-1 font-weight-medium mb-3">

              {{ $t('agent.agents.tester.currentConfig') }}

            </div>



            <!-- 基本信息 -->

            <v-card variant="outlined" class="mb-4">

              <v-card-title class="text-subtitle-2 pb-0">

                {{ $t('agent.agents.tester.basicInfo') }}

              </v-card-title>

              <v-card-text>

                <div class="mb-2">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.role') }}:</span>

                  <p class="text-body-2">{{ agent.role }}</p>

                </div>

                <div v-if="agent.goal">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.goal') }}:</span>

                  <p class="text-body-2">{{ agent.goal }}</p>

                </div>

              </v-card-text>

            </v-card>



            <!-- LLM配置 -->

            <v-card variant="outlined" class="mb-4">

              <v-card-title class="text-subtitle-2 pb-0">

                {{ $t('agent.agents.tester.llmConfig') }}

              </v-card-title>

              <v-card-text>

                <div class="mb-2">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.provider') }}:</span>

                  <p class="text-body-2">{{ agent.provider_id || $t('agent.agents.tester.notConfigured') }}</p>

                </div>

                <div class="mb-2">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.model') }}:</span>

                  <p class="text-body-2">{{ agent.model_name || $t('agent.agents.tester.notConfigured') }}</p>

                </div>

                <div class="mb-2">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.temperature') }}:</span>

                  <p class="text-body-2">{{ agent.llm_config?.temperature ?? $t('agent.agents.tester.default') }}</p>

                </div>

                <div>

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.maxTokens') }}:</span>

                  <p class="text-body-2">{{ agent.llm_config?.max_tokens ?? $t('agent.agents.tester.default') }}</p>

                </div>

              </v-card-text>

            </v-card>



            <!-- 能力配置 -->

            <v-card variant="outlined" class="mb-4">

              <v-card-title class="text-subtitle-2 pb-0">

                {{ $t('agent.agents.tester.abilities') }}

              </v-card-title>

              <v-card-text>

                <div v-if="agent.tools && agent.tools.length > 0" class="mb-3">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.tools') }}:</span>

                  <div class="mt-1">

                    <v-chip

                      v-for="tool in agent.tools"

                      :key="tool"

                      size="x-small"

                      color="primary"

                      variant="flat"

                      class="mr-1 mb-1"

                    >

                      {{ tool }}

                    </v-chip>

                  </div>

                </div>



                <div v-if="agent.skills && agent.skills.length > 0" class="mb-3">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.skills') }}:</span>

                  <div class="mt-1">

                    <v-chip

                      v-for="skill in agent.skills"

                      :key="skill"

                      size="x-small"

                      color="success"

                      variant="flat"

                      class="mr-1 mb-1"

                    >

                      {{ skill }}

                    </v-chip>

                  </div>

                </div>



                <div v-if="agent.knowledge_id">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.knowledgeBase') }}:</span>

                  <div class="mt-1">

                    <v-chip

                      size="x-small"

                      color="info"

                      variant="flat"

                      class="mr-1 mb-1"

                    >

                      {{ agent.knowledge_id }}

                    </v-chip>

                  </div>

                </div>



                <div v-if="!agent.tools?.length && !agent.skills?.length && !agent.knowledge_id" class="text-grey">

                  {{ $t('agent.agents.tester.noAbilities') }}

                </div>

              </v-card-text>

            </v-card>



            <!-- 高级配置 -->

            <v-card variant="outlined">

              <v-card-title class="text-subtitle-2 pb-0">

                {{ $t('agent.agents.tester.advanced') }}

              </v-card-title>

              <v-card-text>

                <div class="mb-2">
                  <v-icon
                    :icon="agent.planning ? 'mdi-check-circle' : 'mdi-close-circle'"
                    :color="agent.planning ? 'success' : 'grey'"
                    size="small"
                    class="mr-1"
                  />
                  <span class="text-body-2">{{ $t('agent.agents.tester.planning') }}</span>
                </div>
                <div v-if="agent.planning" class="d-flex align-center ga-1 mb-2 ml-5">
                  <v-icon size="small" color="success">mdi-clipboard-check</v-icon>
                  <span class="text-body-2">规划模式：{{ agent.planning_effort || 'medium' }}</span>
                </div>
                <div class="mb-2">
                  <v-icon
                    :icon="agent.memory_config ? 'mdi-check-circle' : 'mdi-close-circle'"
                    :color="agent.memory_config ? 'success' : 'grey'"
                    size="small"
                    class="mr-1"
                  />
                  <span class="text-body-2">{{ $t('agent.agents.tester.memory') }}</span>
                </div>
                <div v-if="agent.memory_config?.enabled" class="d-flex align-center ga-1 ml-5">
                  <v-icon size="small" color="info">mdi-brain</v-icon>
                  <span class="text-body-2">记忆：{{ agent.memory_config.type === 'long_term' ? '长期' : '短期' }}</span>
                </div>

              </v-card-text>

            </v-card>



            <!-- 操作按钮 -->

            <div class="mt-4">

              <v-btn

                variant="outlined"

                block

                @click="clearMessages"

                :disabled="messages.length === 0"

              >

                <v-icon start icon="mdi-delete-sweep" />

                {{ $t('agent.agents.tester.clearHistory') }}

              </v-btn>

            </div>

          </v-col>

        </v-row>

      </v-card-text>

    </v-card>

  </v-dialog>

</template>



<script setup lang="ts">

import { ref, watch, nextTick } from 'vue';

import axios from 'axios';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  modelValue: boolean;

  agent: any;

}>();



const emit = defineEmits<{

  (e: 'update:modelValue', value: boolean): void;

}>();



const { t } = useI18n();



// 状

const inputMessage = ref('');

const sending = ref(false);

const messages = ref<any[]>([]);

const messagesContainer = ref<HTMLElement | null>(null);

let abortController: AbortController | null = null;



// 监听对话框打开

watch(() => props.modelValue, (newVal) => {

  if (newVal) {

    // 重置状

    inputMessage.value = '';

    messages.value = [];

  }

});



// 发送消息（流式输出）
async function sendMessage() {
  if (!inputMessage.value.trim() || sending.value) return;

  const userMessage = inputMessage.value.trim();
  inputMessage.value = '';

  messages.value.push({
    role: 'user',
    content: userMessage,
  });

  await nextTick();
  scrollToBottom();

  sending.value = true;

  const assistantMessage: any = {
    role: 'assistant',
    content: '',
    thinking: '',
    thinkingDone: false,
    tools: [] as string[],
    planning_steps: null as string | null,
    memory_used: 0,
  };
  messages.value.push(assistantMessage);

  abortController = new AbortController();

  try {
    const response = await fetch('/api/plug/agent/agents/test-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        id: props.agent.id,
        message: userMessage,
      }),
      signal: abortController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
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

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6);
          if (jsonStr.trim()) {
            try {
              const event = JSON.parse(jsonStr);
              handleStreamEvent(event, assistantMessage);
            } catch (e) {
              console.error('Failed to parse SSE event:', jsonStr, e);
            }
          }
        }
      }

      await nextTick();
      scrollToBottom();
    }

    if (buffer.trim()) {
      for (const line of buffer.split('\n')) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6);
          if (jsonStr.trim()) {
            try {
              const event = JSON.parse(jsonStr);
              handleStreamEvent(event, assistantMessage);
            } catch (e) {
              console.error('Failed to parse SSE event:', jsonStr, e);
            }
          }
        }
      }
    }

  } catch (error: any) {
    if (error.name === 'AbortError') {
      if (!assistantMessage.content) {
        assistantMessage.content = '（已停止）';
      }
    } else {
      console.error('Failed to send message:', error);
      assistantMessage.content = error.message || t('agent.agents.tester.error');
    }
  } finally {
    sending.value = false;
    abortController = null;
    await nextTick();
    scrollToBottom();
  }
}

function stopGeneration() {
  if (abortController) {
    abortController.abort();
  }
}



// 处理流式事件
function handleStreamEvent(event: any, assistantMessage: any) {
  switch (event.type) {
    case 'chunk':
      assistantMessage.content += event.data;
      break;

    case 'thinking':
      assistantMessage.thinking += event.data;
      assistantMessage.thinkingDone = false;
      break;

    case 'planning':
      assistantMessage.planning_steps = event.data;
      break;

    case 'tool_start':
      if (typeof event.data === 'string') {
        assistantMessage.tools = [...assistantMessage.tools, event.data];
      } else if (Array.isArray(event.data)) {
        assistantMessage.tools = [...assistantMessage.tools, ...event.data];
      }
      break;

    case 'tool_result':
      break;

    case 'done':
      if (event.data) {
        if (event.data.response && !assistantMessage.content) {
          assistantMessage.content = event.data.response;
        }
        if (event.data.tools_used && event.data.tools_used.length > 0) {
          assistantMessage.tools = event.data.tools_used;
        }
        if (event.data.planning_steps) {
          assistantMessage.planning_steps = event.data.planning_steps;
        }
      }
      if (assistantMessage.thinking) {
        assistantMessage.thinkingDone = true;
      }
      break;

    case 'error':
      assistantMessage.content = event.data || t('agent.agents.tester.error');
      break;

    default:
      console.warn('Unknown SSE event type:', event.type);
  }
}



// 滚动到底

function scrollToBottom() {

  if (messagesContainer.value) {

    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;

  }

}



// 清空历史

function clearMessages() {

  messages.value = [];

}

</script>



<style scoped>

.message-card {

  border-radius: 12px;

}



.message-text {

  white-space: pre-wrap;

  word-break: break-word;

  margin: 0;

  font-family: inherit;

}



.thinking-section :deep(.v-expansion-panel) {
  background: rgba(255, 152, 0, 0.04);
  border: 1px solid rgba(255, 152, 0, 0.12);
  border-radius: 8px !important;
}

.thinking-section :deep(.v-expansion-panel-title) {
  min-height: 32px;
}

.thinking-content {
  max-height: 300px;
  overflow-y: auto;
}

.thinking-text {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: monospace;
  font-size: 12px;
  color: #666;
  background: rgba(0, 0, 0, 0.05);
  padding: 8px;
  border-radius: 4px;
}

.planning-steps :deep(.v-expansion-panel) {

  background: rgba(var(--v-theme-primary), 0.04);

  border: 1px solid rgba(var(--v-theme-primary), 0.12);

  border-radius: 8px !important;

}

.planning-steps :deep(.v-expansion-panel-title) {

  min-height: 32px;

}

.planning-content {

  max-height: 300px;

  overflow-y: auto;

}

</style>

