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

        <v-chip size="small" color="primary" variant="flat" class="ml-3">

          {{ agent.model?.provider }} / {{ agent.model?.name }}

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

                        <pre class="message-text">{{ message.content }}</pre>

                        <div v-if="message.thinking" class="mt-2 pt-2 border-t">

                          <div class="text-caption text-grey mb-1">

                            <v-icon icon="mdi-head-lightbulb" size="small" class="mr-1" />

                            {{ $t('agent.agents.tester.thinking') }}

                          </div>

                          <pre class="thinking-text">{{ message.thinking }}</pre>

                        </div>

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

                  color="primary"

                  @click="sendMessage"

                  :loading="sending"

                  :disabled="!inputMessage.trim()"

                >

                  <v-icon start icon="mdi-send" />

                  {{ $t('agent.agents.tester.send') }}

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



                <div v-if="agent.knowledgeBases && agent.knowledgeBases.length > 0">

                  <span class="text-caption text-grey">{{ $t('agent.agents.tester.knowledgeBases') }}:</span>

                  <div class="mt-1">

                    <v-chip

                      v-for="kb in agent.knowledgeBases"

                      :key="kb"

                      size="x-small"

                      color="info"

                      variant="flat"

                      class="mr-1 mb-1"

                    >

                      {{ kb }}

                    </v-chip>

                  </div>

                </div>



                <div v-if="!agent.tools?.length && !agent.skills?.length && !agent.knowledgeBases?.length" class="text-grey">

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

                    :icon="agent.planning?.enabled ? 'mdi-check-circle' : 'mdi-close-circle'"

                    :color="agent.planning?.enabled ? 'success' : 'grey'"

                    size="small"

                    class="mr-1"

                  />

                  <span class="text-body-2">{{ $t('agent.agents.tester.planning') }}</span>

                </div>

                <div>

                  <v-icon

                    :icon="agent.memory?.enabled ? 'mdi-check-circle' : 'mdi-close-circle'"

                    :color="agent.memory?.enabled ? 'success' : 'grey'"

                    size="small"

                    class="mr-1"

                  />

                  <span class="text-body-2">{{ $t('agent.agents.tester.memory') }}</span>

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



// 监听对话框打开

watch(() => props.modelValue, (newVal) => {

  if (newVal) {

    // 重置状

    inputMessage.value = '';

    messages.value = [];

  }

});



// 发送消

async function sendMessage() {

  if (!inputMessage.value.trim() || sending.value) return;



  const userMessage = inputMessage.value.trim();

  inputMessage.value = '';



  // 添加用户消息

  messages.value.push({

    role: 'user',

    content: userMessage,

  });



  // 滚动到底

  await nextTick();

  scrollToBottom();



  sending.value = true;

  try {

    const response = await axios.post('/api/plug/agent/agents/test', {
      id: props.agent.id,
      message: userMessage,
      history: messages.value.slice(0, -1), // 不包含刚添加的用户消息
    });



    if (response.data.status === 'ok') {

      const data = response.data.data;

      messages.value.push({

        role: 'assistant',

        content: data.response || data.content || '',

        thinking: data.thinking || null,

        tools: data.tools_used || [],

      });

    } else {

      messages.value.push({

        role: 'assistant',

        content: response.data.message || t('agent.agents.tester.error'),

      });

    }

  } catch (error: any) {

    console.error('Failed to send message:', error);

    messages.value.push({

      role: 'assistant',

      content: error.response?.data?.message || error.message || t('agent.agents.tester.error'),

    });

  } finally {

    sending.value = false;

    await nextTick();

    scrollToBottom();

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

</style>

