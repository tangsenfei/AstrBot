<template>
  <section class="cli-agent-workspace">
    <main class="cli-agent-main">
      <header class="cli-agent-header">
        <div>
          <div class="cli-agent-kicker">CLI Agent</div>
          <h2>{{ client.name }}</h2>
          <p>{{ agentKindLabel(client.agent_kind) }} · {{ locationLabel }} · {{ transportLabel(client.transport_kind) }}</p>
        </div>
        <v-btn variant="tonal" prepend-icon="mdi-cog-outline" @click="$emit('manage')">
          管理配置
        </v-btn>
      </header>

      <section ref="messagesContainer" class="cli-agent-messages">
        <div v-if="loading" class="center-state">
          <v-progress-circular indeterminate size="30" width="3" />
        </div>
        <div v-else-if="!activeSession" class="empty-state">
          选择或创建一个工作区会话后即可开始对话
        </div>
        <div v-else-if="!messages.length" class="empty-state">
          当前会话暂无消息
        </div>
        <ChatMessageList
          v-else
          v-model:edit-draft="messageEditDraft"
          :messages="chatRecords"
          :active-cards="[]"
          :is-dark="isDark"
          :is-streaming="sending"
          :enable-edit="false"
          :enable-regenerate="false"
          :enable-thread-selection="false"
          :manage-refs-sidebar="false"
        />
      </section>

      <section class="cli-agent-composer">
        <v-alert v-if="errorText" class="cli-agent-error" type="error" variant="tonal" density="compact" closable @click:close="errorText = ''">
          {{ errorText }}
        </v-alert>
        <v-textarea
          v-model="draft"
          rows="2"
          auto-grow
          hide-details
          variant="outlined"
          :disabled="!activeSession || sending"
          placeholder="向当前 CLI Agent 会话发送消息..."
          @keydown.ctrl.enter.prevent="sendMessage"
          @keydown.meta.enter.prevent="sendMessage"
        />
        <v-btn
          color="primary"
          :disabled="!activeSession || !draft.trim()"
          :loading="sending"
          @click="sendMessage"
        >
          <v-icon start>mdi-send</v-icon>
          发送
        </v-btn>
      </section>
    </main>

    <aside class="cli-agent-side">
      <div class="side-section">
        <div class="side-title-row">
          <h3>工作区</h3>
          <v-btn icon="mdi-plus" size="small" variant="text" @click="openWorkspaceDialog" />
        </div>
        <button
          v-for="workspace in workspaces"
          :key="workspace.id"
          class="side-item"
          :class="{ active: selectedWorkspaceId === workspace.id }"
          type="button"
          @click="selectWorkspace(workspace.id)"
        >
          <v-icon size="17">mdi-folder-outline</v-icon>
          <span>{{ workspace.name }}</span>
        </button>
        <div v-if="!workspaces.length" class="side-empty">暂无工作区</div>
      </div>

      <div class="side-section sessions">
        <div class="side-title-row">
          <h3>会话</h3>
          <v-btn
            icon="mdi-plus"
            size="small"
            variant="text"
            :disabled="!selectedWorkspaceId"
            @click="openSessionDialog"
          />
        </div>
        <button
          v-for="session in sessions"
          :key="session.id"
          class="side-item"
          :class="{ active: selectedSessionId === session.id }"
          type="button"
          @click="selectSession(session.id)"
        >
          <v-icon size="17">mdi-message-text-outline</v-icon>
          <span>{{ session.title }}</span>
        </button>
        <div v-if="selectedWorkspaceId && !sessions.length" class="side-empty">暂无会话</div>
      </div>
    </aside>

    <v-dialog v-model="workspaceDialogOpen" max-width="520">
      <v-card>
        <v-card-title>新建工作区</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="workspaceForm.name" label="名称" variant="outlined" />
          <v-text-field v-model="workspaceForm.root_path" label="本地路径" variant="outlined" />
          <v-textarea v-model="workspaceForm.description" label="备注" variant="outlined" rows="3" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="workspaceDialogOpen = false">取消</v-btn>
          <v-btn color="primary" :loading="savingWorkspace" @click="saveWorkspace">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="sessionDialogOpen" max-width="480">
      <v-card>
        <v-card-title>新建会话</v-card-title>
        <v-card-text>
          <v-text-field v-model="sessionForm.title" label="标题" variant="outlined" autofocus />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="sessionDialogOpen = false">取消</v-btn>
          <v-btn color="primary" :loading="savingSession" @click="saveSession">创建</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import axios from 'axios';
import ChatMessageList from '@/components/chat/ChatMessageList.vue';
import type { ChatRecord } from '@/composables/useMessages';
import { useCustomizerStore } from '@/stores/customizer';

type CliAgentClient = {
  id: string;
  name: string;
  agent_kind: string;
  location_kind: 'local' | 'remote';
  transport_kind: string;
};

type CliWorkspace = {
  id: string;
  name: string;
  root_path?: string;
  path?: string;
  description?: string;
};

type CliSession = {
  id: string;
  title: string;
  status?: string;
  workspace_id: string;
};

type CliMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
};

const props = defineProps<{ client: CliAgentClient }>();
defineEmits<{ manage: [] }>();

const workspaces = ref<CliWorkspace[]>([]);
const sessions = ref<CliSession[]>([]);
const messages = ref<CliMessage[]>([]);
const errorText = ref('');
const selectedWorkspaceId = ref('');
const selectedSessionId = ref('');
const loading = ref(false);
const sending = ref(false);
const savingWorkspace = ref(false);
const savingSession = ref(false);
const draft = ref('');
const messagesContainer = ref<HTMLElement | null>(null);
const workspaceDialogOpen = ref(false);
const sessionDialogOpen = ref(false);
const workspaceForm = reactive({ name: '', root_path: '', description: '' });
const sessionForm = reactive({ title: '' });
const messageEditDraft = ref('');
const customizer = useCustomizerStore();

const activeSession = computed(() =>
  sessions.value.find((session) => session.id === selectedSessionId.value) || null,
);
const locationLabel = computed(() => (props.client.location_kind === 'remote' ? '远程' : '本地'));
const isDark = computed(() => customizer.uiTheme === 'PurpleThemeDark');
const chatRecords = computed<ChatRecord[]>(() => {
  const records = messages.value
    .filter((message) => message && message.id && message.content != null)
    .map((message) => toChatRecord(message));
  if (sending.value) {
    records.push({
      id: 'cli-agent-loading',
      created_at: new Date().toISOString(),
      content: {
        type: 'bot',
        message: [],
        isLoading: true,
      },
    });
  }
  return records;
});

onMounted(loadAll);
watch(() => props.client.id, loadAll);

async function loadAll() {
  loading.value = true;
  errorText.value = '';
  try {
    await loadWorkspaces();
    if (workspaces.value.length && !selectedWorkspaceId.value) {
      selectedWorkspaceId.value = workspaces.value[0].id;
    }
    await loadSessions();
    if (sessions.value.length && !selectedSessionId.value) {
      await selectSession(sessions.value[0].id);
    } else if (!sessions.value.length) {
      messages.value = [];
    }
  } finally {
    loading.value = false;
  }
}

async function loadWorkspaces() {
  const response = await axios.get('/api/plug/cli-agents/workspaces');
  const data = responseData(response);
  workspaces.value = Array.isArray(data) ? data : data?.workspaces || [];
}

async function loadSessions() {
  if (!selectedWorkspaceId.value) {
    sessions.value = [];
    return;
  }
  const response = await axios.get('/api/plug/cli-agents/sessions', {
    params: {
      client_id: props.client.id,
      workspace_id: selectedWorkspaceId.value,
    },
  });
  const data = responseData(response);
  sessions.value = Array.isArray(data) ? data : data?.sessions || [];
}

async function loadMessages() {
  if (!selectedSessionId.value) {
    messages.value = [];
    return;
  }
  const response = await axios.get(`/api/plug/cli-agents/sessions/${selectedSessionId.value}/messages`);
  const data = responseData(response);
  messages.value = Array.isArray(data) ? data : data?.messages || [];
  await scrollToBottom();
}

async function selectWorkspace(workspaceId: string) {
  selectedWorkspaceId.value = workspaceId;
  selectedSessionId.value = '';
  messages.value = [];
  await loadSessions();
  if (sessions.value.length) {
    await selectSession(sessions.value[0].id);
  }
}

async function selectSession(sessionId: string) {
  selectedSessionId.value = sessionId;
  await loadMessages();
}

function openWorkspaceDialog() {
  workspaceForm.name = '';
  workspaceForm.root_path = '';
  workspaceForm.description = '';
  workspaceDialogOpen.value = true;
}

async function saveWorkspace() {
  savingWorkspace.value = true;
  try {
    const response = await axios.post('/api/plug/cli-agents/workspaces', {
      name: workspaceForm.name.trim(),
      root_path: workspaceForm.root_path.trim(),
      description: workspaceForm.description.trim(),
      default_client_id: props.client.id,
      location_kind: props.client.location_kind,
    });
    const workspace = responseData(response);
    workspaceDialogOpen.value = false;
    await loadWorkspaces();
    if (workspace?.id) {
      await selectWorkspace(workspace.id);
    }
  } finally {
    savingWorkspace.value = false;
  }
}

function openSessionDialog() {
  sessionForm.title = '';
  sessionDialogOpen.value = true;
}

async function saveSession() {
  if (!selectedWorkspaceId.value) return;
  savingSession.value = true;
  try {
    const response = await axios.post('/api/plug/cli-agents/sessions', {
      client_id: props.client.id,
      workspace_id: selectedWorkspaceId.value,
      title: sessionForm.title.trim() || '新会话',
    });
    const session = responseData(response);
    sessionDialogOpen.value = false;
    await loadSessions();
    if (session?.id) {
      await selectSession(session.id);
    }
  } finally {
    savingSession.value = false;
  }
}

async function sendMessage() {
  if (!selectedSessionId.value || !draft.value.trim()) return;
  sending.value = true;
  errorText.value = '';
  const content = draft.value.trim();
  draft.value = '';
  try {
    const response = await axios.post(`/api/plug/cli-agents/sessions/${selectedSessionId.value}/messages`, {
      content,
    });
    const data = responseData(response);
    const nextMessages = [data.user_message, data.assistant_message].filter(Boolean);
    if (nextMessages.length) {
      messages.value.push(...nextMessages);
      await scrollToBottom();
    } else {
      await loadMessages();
    }
    await loadSessions();
  } catch (error: any) {
    errorText.value = errorMessage(error);
    await loadMessages();
    await loadSessions();
  } finally {
    sending.value = false;
  }
}

async function scrollToBottom() {
  await nextTick();
  const el = messagesContainer.value;
  if (el) el.scrollTop = el.scrollHeight;
}

function agentKindLabel(kind: string) {
  if (kind === 'claude') return 'Claude';
  if (kind === 'codex') return 'Codex';
  return '自定义';
}

function transportLabel(kind: string) {
  const labels: Record<string, string> = {
    native_stdio: '原生 STDIO',
    acp_stdio: 'ACP STDIO',
    remote_ws: '远程 WebSocket',
    remote_http_sse: '远程 HTTP SSE',
  };
  return labels[kind] || kind;
}

function responseData(response: any) {
  if (response.data?.status === 'error') {
    throw new Error(response.data?.message || '请求失败');
  }
  return response.data?.data;
}

function errorMessage(error: any) {
  return error?.response?.data?.message || error?.message || 'CLI Agent 执行失败';
}

function toChatRecord(message: CliMessage): ChatRecord {
  return {
    id: message.id,
    created_at: message.created_at,
    sender_name: message.role === 'user' ? 'You' : props.client.name,
    content: {
      type: message.role === 'user' ? 'user' : 'bot',
      message: [{ type: 'plain', text: message.content || '' }],
    },
  };
}
</script>

<style scoped>
.cli-agent-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  background: rgb(var(--v-theme-background));
}

.cli-agent-main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.cli-agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 76px;
  padding: 14px max(24px, calc((100% - 980px) / 2));
  border-bottom: 1px solid rgba(var(--v-border-color), 0.16);
}

.cli-agent-kicker {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.cli-agent-header h2 {
  margin: 2px 0;
  font-size: 20px;
  line-height: 1.2;
}

.cli-agent-header p {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 13px;
}

.cli-agent-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px max(24px, calc((100% - 980px) / 2)) 18px;
}

.center-state,
.empty-state {
  height: 100%;
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(var(--v-theme-on-surface), 0.58);
}

.cli-agent-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 0 max(24px, calc((100% - 980px) / 2)) 18px;
  border-top: 1px solid rgba(var(--v-border-color), 0.16);
  background: rgb(var(--v-theme-background));
}

.cli-agent-error {
  grid-column: 1 / -1;
}

.cli-agent-side {
  min-width: 0;
  border-left: 1px solid rgba(var(--v-border-color), 0.16);
  background: rgb(var(--v-theme-surface));
  overflow-y: auto;
  padding: 16px;
}

.side-section + .side-section {
  margin-top: 20px;
}

.side-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.side-title-row h3 {
  margin: 0;
  font-size: 16px;
}

.side-item {
  width: 100%;
  min-height: 38px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
}

.side-item:hover,
.side-item.active {
  border-color: rgba(var(--v-theme-primary), 0.24);
  background: rgba(var(--v-theme-primary), 0.08);
}

.side-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

.side-empty {
  padding: 10px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  font-size: 13px;
}

.dialog-grid {
  display: grid;
  gap: 12px;
}

@media (max-width: 960px) {
  .cli-agent-workspace {
    grid-template-columns: 1fr;
  }

  .cli-agent-side {
    border-left: 0;
    border-top: 1px solid rgba(var(--v-border-color), 0.16);
    max-height: 280px;
  }
}
</style>
