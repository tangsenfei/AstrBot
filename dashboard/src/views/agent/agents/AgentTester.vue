<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" fullscreen scrollable>
    <v-card v-if="agent">
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

      <v-card-text class="pa-0" style="height: calc(100vh - 100px);">
        <v-row no-gutters class="h-100">
          <v-col cols="12" md="8" class="d-flex flex-column border-e">
            <AgentChatPanel
              ref="chatPanel"
              :messages="messages"
              :sending="sending"
              :show-input="true"
              :input-placeholder="$t('agent.agents.tester.inputPlaceholder')"
              :empty-text="$t('agent.agents.tester.emptyMessage')"
              @send="sendMessage"
              @stop="stopGeneration"
            />
          </v-col>

          <v-col cols="12" md="4" class="pa-4 overflow-y-auto">
            <div class="text-subtitle-1 font-weight-medium mb-3">{{ $t('agent.agents.tester.currentConfig') }}</div>
            <v-card variant="outlined" class="mb-4">
              <v-card-title class="text-subtitle-2 pb-0">{{ $t('agent.agents.tester.basicInfo') }}</v-card-title>
              <v-card-text>
                <div class="mb-2"><span class="text-caption text-grey">Soul:</span><p class="text-body-2 mb-0">{{ agent.soul || '--' }}</p></div>
              </v-card-text>
            </v-card>
            <v-card variant="outlined" class="mb-4">
              <v-card-title class="text-subtitle-2 pb-0">LLM</v-card-title>
              <v-card-text>
                <div class="mb-2"><span class="text-caption text-grey">Provider:</span><p class="text-body-2 mb-0">{{ agent.provider_id || '--' }}</p></div>
                <div class="mb-2"><span class="text-caption text-grey">Model:</span><p class="text-body-2 mb-0">{{ agent.model_name || '--' }}</p></div>
                <div class="mb-2"><span class="text-caption text-grey">Temperature:</span><p class="text-body-2 mb-0">{{ agent.llm_config?.temperature ?? 'default' }}</p></div>
                <div><span class="text-caption text-grey">Max Tokens:</span><p class="text-body-2 mb-0">{{ agent.llm_config?.max_tokens ?? 'default' }}</p></div>
              </v-card-text>
            </v-card>
            <v-card variant="outlined" class="mb-4">
              <v-card-title class="text-subtitle-2 pb-0">Tools</v-card-title>
              <v-card-text>
                <template v-if="agent.tools && agent.tools.length > 0">
                  <v-chip v-for="tool in agent.tools" :key="tool" size="small" variant="flat" color="info" class="mr-1 mb-1">{{ tool }}</v-chip>
                </template>
                <span v-else class="text-caption text-grey">No tools configured</span>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import AgentChatPanel from '@/components/agent/AgentChatPanel.vue';
import type { ChatMessage, ToolCallInfo } from '@/components/agent/AgentChatPanel.vue';

const props = defineProps<{
  modelValue: boolean;
  agent: any;
}>();

const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const { t } = useI18n();

const sending = ref(false);
const messages = ref<ChatMessage[]>([]);
const chatPanel = ref<InstanceType<typeof AgentChatPanel> | null>(null);
let abortController: AbortController | null = null;

watch(() => props.modelValue, (newVal) => {
  if (newVal) { messages.value = []; }
});

async function sendMessage(userMessage: string) {
  if (!userMessage || sending.value) return;

  const userTime = Date.now();
  messages.value.push({ role: 'user', content: userMessage, created_at: userTime });

  sending.value = true;
  const assistantMessage: ChatMessage = {
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content: '',
    thinking: '',
    thinkingDone: false,
    toolCalls: [],
    planning_steps: null,
    created_at: Date.now(),
    _stats: null,
    _time_to_first_token: 0,
    _execution_time_ms: 0,
  };
  messages.value.push(assistantMessage);

  abortController = new AbortController();

  try {
    const response = await fetch('/api/plug/agent/agents/test-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ id: props.agent.id, message: userMessage }),
      signal: abortController.signal,
    });

    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

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
          try { handleStreamEvent(JSON.parse(line.slice(6)), assistantMessage); } catch (e) { /* skip */ }
        }
      }
      await nextTick();
      chatPanel.value?.scrollToBottom();
    }
  } catch (error: any) {
    if (error.name !== 'AbortError') {
      assistantMessage.content = error.message || t('agent.agents.tester.error');
    } else if (!assistantMessage.content) {
      assistantMessage.content = '（已停止）';
    }
  } finally {
    sending.value = false;
    abortController = null;
    assistantMessage.thinkingDone = true;
    await nextTick();
    chatPanel.value?.scrollToBottom();
  }
}

function handleStreamEvent(event: any, msg: ChatMessage) {
  switch (event.type) {
    case 'chunk':
      msg.content += event.data;
      break;
    case 'thinking':
      msg.thinking = (msg.thinking || '') + event.data;
      msg.thinkingDone = false;
      break;
    case 'planning':
      msg.planning_steps = event.data;
      break;
    case 'tool_start': {
      const toolName = typeof event.data === 'string' ? event.data : event.data?.name || '';
      if (toolName) {
        if (!msg.toolCalls) msg.toolCalls = [];
        const existing = msg.toolCalls.find(tc => tc.name === toolName && tc.status === 'running');
        if (!existing) {
          msg.toolCalls.push({ name: toolName, status: 'running' });
        }
      }
      break;
    }
    case 'tool_result': {
      const name = event.data?.name || '';
      const result = event.data?.result || event.data?.content || '';
      if (name && msg.toolCalls) {
        const tc = msg.toolCalls.find(t => t.name === name && t.status === 'running');
        if (tc) {
          tc.status = 'done';
          tc.result = result;
        } else {
          msg.toolCalls.push({ name, result, status: 'done' });
        }
      }
      break;
    }
    case 'done':
      if (event.data) {
        if (event.data.response && !msg.content) msg.content = event.data.response;
        if (event.data.tools_used?.length) {
          if (!msg.toolCalls) msg.toolCalls = [];
          for (const toolName of event.data.tools_used) {
            if (!msg.toolCalls.find(tc => tc.name === toolName)) {
              msg.toolCalls.push({ name: toolName, status: 'done' });
            }
          }
        }
        if (event.data.planning_steps) msg.planning_steps = event.data.planning_steps;
        if (event.data.tokens) {
          msg._stats = {
            input: event.data.tokens.input || event.data.tokens.prompt_tokens || 0,
            output: event.data.tokens.output || event.data.tokens.completion_tokens || 0,
            total: event.data.tokens.total || event.data.tokens.total_tokens || 0,
          };
        }
        msg._execution_time_ms = event.data.execution_time_ms || 0;
        msg._time_to_first_token = event.data.time_to_first_token || 0;
      }
      msg.thinkingDone = true;
      break;
    case 'error':
      msg.content = event.data || t('agent.agents.tester.error');
      break;
  }
}

function stopGeneration() { abortController?.abort(); }
</script>
