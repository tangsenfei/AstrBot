<template>
  <div class="cli-agent-page">
    <header class="page-header">
      <div>
        <h1>CLI Agent</h1>
        <p>管理 Claude、Codex 等本地或远程 CLI 客户端，并为 Chat 页面提供入口。</p>
      </div>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openClientDialog()">
        新建客户端
      </v-btn>
    </header>

    <v-alert v-if="errorText" class="mb-4" type="error" variant="tonal" closable @click:close="errorText = ''">
      {{ errorText }}
    </v-alert>

    <v-tabs v-model="activeTab" color="primary" class="cli-tabs">
      <v-tab value="clients">客户端</v-tab>
      <v-tab value="workspaces">工作区</v-tab>
    </v-tabs>

    <v-window v-model="activeTab" class="cli-window">
      <v-window-item value="clients">
        <section class="toolbar-row">
          <v-text-field
            v-model="clientSearch"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索客户端"
          />
          <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loadingClients" @click="loadClients">
            刷新
          </v-btn>
        </section>

        <div class="client-grid">
          <article v-for="client in filteredClients" :key="client.id" class="client-card">
            <div class="card-top">
              <div class="client-main">
                <v-icon size="22" :color="client.enabled ? 'primary' : undefined">mdi-console</v-icon>
                <div>
                  <div class="client-name">{{ client.name }}</div>
                  <div class="client-meta">
                    <span>{{ agentKindLabel(client.agent_kind) }}</span>
                    <span>{{ client.location_kind === 'remote' ? '远程' : '本地' }}</span>
                    <span>{{ transportLabel(client.transport_kind) }}</span>
                  </div>
                </div>
              </div>
              <v-switch
                v-model="client.enabled"
                density="compact"
                color="primary"
                hide-details
                @update:model-value="toggleClient(client)"
              />
            </div>

            <div class="client-command">{{ clientDisplayTarget(client) }}</div>

            <div class="status-line">
              <v-chip size="small" :color="statusColor(client.status)" variant="tonal">
                {{ statusLabel(client.status) }}
              </v-chip>
              <span v-if="client.status_message || client.last_check_message">{{ client.status_message || client.last_check_message }}</span>
            </div>

            <div class="card-actions">
              <v-btn size="small" variant="tonal" prepend-icon="mdi-check-network-outline" @click="checkClient(client)">
                检测
              </v-btn>
              <v-btn size="small" variant="text" prepend-icon="mdi-pencil-outline" @click="openClientDialog(client)">
                编辑
              </v-btn>
              <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="deleteClient(client)">
                删除
              </v-btn>
            </div>
          </article>

          <div v-if="!filteredClients.length && !loadingClients" class="empty-state">
            暂无 CLI Agent 客户端
          </div>
        </div>
      </v-window-item>

      <v-window-item value="workspaces">
        <section class="toolbar-row">
          <v-text-field
            v-model="workspaceSearch"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            placeholder="搜索工作区"
          />
          <v-btn color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openWorkspaceDialog()">
            新建工作区
          </v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loadingWorkspaces" @click="loadWorkspaces">
            刷新
          </v-btn>
        </section>

        <v-table class="workspace-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>路径</th>
              <th>状态</th>
              <th>默认客户端</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="workspace in filteredWorkspaces" :key="workspace.id">
              <td>{{ workspace.name }}</td>
              <td class="path-cell">{{ workspace.root_path }}</td>
              <td>{{ workspace.status }}</td>
              <td>{{ clientName(workspace.default_client_id) }}</td>
              <td class="text-right">
                <v-btn icon="mdi-pencil-outline" size="small" variant="text" @click="openWorkspaceDialog(workspace)" />
                <v-btn icon="mdi-delete-outline" size="small" color="error" variant="text" @click="deleteWorkspace(workspace)" />
              </td>
            </tr>
          </tbody>
        </v-table>
        <div v-if="!filteredWorkspaces.length && !loadingWorkspaces" class="empty-state">
          暂无工作区
        </div>
      </v-window-item>
    </v-window>

    <v-dialog v-model="clientDialogOpen" max-width="760">
      <v-card>
        <v-card-title>{{ editingClient ? '编辑客户端' : '新建客户端' }}</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="clientForm.name" label="名称" variant="outlined" />
          <div class="dialog-row">
            <v-select v-model="clientForm.agent_kind" :items="agentKindOptions" label="类型" variant="outlined" />
            <v-select v-model="clientForm.location_kind" :items="locationOptions" label="位置" variant="outlined" />
            <v-select v-model="clientForm.transport_kind" :items="transportOptions" label="传输" variant="outlined" />
          </div>
          <v-text-field
            v-model="clientForm.command"
            label="命令"
            variant="outlined"
            :placeholder="clientForm.transport_kind === 'acp_stdio' ? '留空将使用 npx Zed ACP bridge' : 'claude、codex 或 more.com'"
          />
          <v-text-field
            v-model="clientForm.executable_path"
            label="可执行文件路径"
            variant="outlined"
            placeholder="可选，优先于命令"
          />
          <v-text-field
            v-model="clientForm.args_text"
            label="默认参数"
            variant="outlined"
            placeholder="每个参数用空格分隔；含空格的复杂参数建议写入包装脚本"
          />
          <v-alert type="info" variant="tonal" density="compact">
            ACP STDIO 用于 Claude/Codex 正式接入；原生 STDIO 仅适合 more.com、echo 脚本等调试客户端。
          </v-alert>
          <v-text-field
            v-if="clientForm.location_kind === 'remote'"
            v-model="clientForm.remote_url"
            label="远程地址"
            variant="outlined"
            placeholder="ws:// 或 https://"
          />
          <div class="dialog-row">
            <v-select v-model="clientForm.auth_type" :items="authTypeOptions" label="认证方式" variant="outlined" />
            <v-select v-model="clientForm.permission_policy" :items="permissionOptions" label="权限策略" variant="outlined" />
          </div>
          <v-textarea
            v-model="clientForm.env_text"
            label="环境变量 JSON"
            variant="outlined"
            rows="4"
            placeholder='{"ANTHROPIC_API_KEY":"..."}'
          />
          <v-switch v-model="clientForm.enabled" color="primary" hide-details label="在 Chat 页面显示入口" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="clientDialogOpen = false">取消</v-btn>
          <v-btn color="primary" :loading="savingClient" @click="saveClient">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="workspaceDialogOpen" max-width="640">
      <v-card>
        <v-card-title>{{ editingWorkspace ? '编辑工作区' : '新建工作区' }}</v-card-title>
        <v-card-text class="dialog-grid">
          <v-text-field v-model="workspaceForm.name" label="名称" variant="outlined" />
          <v-text-field v-model="workspaceForm.root_path" label="路径" variant="outlined" />
          <v-select
            v-model="workspaceForm.default_client_id"
            :items="clients"
            item-title="name"
            item-value="id"
            label="默认客户端"
            variant="outlined"
            clearable
          />
          <v-textarea v-model="workspaceForm.description" label="备注" variant="outlined" rows="3" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="workspaceDialogOpen = false">取消</v-btn>
          <v-btn color="primary" :loading="savingWorkspace" @click="saveWorkspace">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import axios from 'axios';

type CliClient = {
  id: string;
  name: string;
  agent_kind: string;
  location_kind: 'local' | 'remote';
  transport_kind: string;
  command?: string;
  args?: string[];
  executable_path?: string;
  remote_url?: string;
  auth_type?: string;
  env?: Record<string, string>;
  permission_policy?: string;
  enabled: boolean;
  status?: string;
  status_message?: string;
  last_check_message?: string;
};

type CliWorkspace = {
  id: string;
  name: string;
  root_path: string;
  description?: string;
  status?: string;
  default_client_id?: string | null;
};

const clients = ref<CliClient[]>([]);
const workspaces = ref<CliWorkspace[]>([]);
const loadingClients = ref(false);
const loadingWorkspaces = ref(false);
const savingClient = ref(false);
const savingWorkspace = ref(false);
const errorText = ref('');
const activeTab = ref('clients');
const clientSearch = ref('');
const workspaceSearch = ref('');
const clientDialogOpen = ref(false);
const workspaceDialogOpen = ref(false);
const editingClient = ref<CliClient | null>(null);
const editingWorkspace = ref<CliWorkspace | null>(null);

const clientForm = reactive({
  name: '',
  agent_kind: 'claude',
  location_kind: 'local' as 'local' | 'remote',
  transport_kind: 'native_stdio',
  command: '',
  executable_path: '',
  args_text: '',
  remote_url: '',
  auth_type: 'none',
  permission_policy: 'ask',
  env_text: '',
  enabled: true,
});

const workspaceForm = reactive({
  name: '',
  root_path: '',
  description: '',
  default_client_id: null as string | null,
});

const agentKindOptions = [
  { title: 'Claude', value: 'claude' },
  { title: 'Codex', value: 'codex' },
  { title: '自定义', value: 'custom' },
];
const locationOptions = [
  { title: '本地', value: 'local' },
  { title: '远程', value: 'remote' },
];
const transportOptions = [
  { title: '原生 STDIO', value: 'native_stdio' },
  { title: 'ACP STDIO', value: 'acp_stdio' },
  { title: '远程 WebSocket', value: 'remote_ws' },
  { title: '远程 HTTP SSE', value: 'remote_http_sse' },
];
const authTypeOptions = [
  { title: '无', value: 'none' },
  { title: 'Token', value: 'token' },
  { title: 'API Key', value: 'api_key' },
];
const permissionOptions = [
  { title: '每次询问', value: 'ask' },
  { title: '自动允许', value: 'allow' },
  { title: '自动拒绝', value: 'deny' },
];

const filteredClients = computed(() => {
  const query = clientSearch.value.trim().toLowerCase();
  if (!query) return clients.value;
  return clients.value.filter((client) =>
    [client.name, client.agent_kind, client.location_kind, client.command, client.executable_path]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query)),
  );
});

const filteredWorkspaces = computed(() => {
  const query = workspaceSearch.value.trim().toLowerCase();
  if (!query) return workspaces.value;
  return workspaces.value.filter((workspace) =>
    [workspace.name, workspace.root_path, workspace.description]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query)),
  );
});

onMounted(async () => {
  await Promise.all([loadClients(), loadWorkspaces()]);
});

async function loadClients() {
  loadingClients.value = true;
  try {
    const response = await axios.get('/api/plug/cli-agents/clients');
    const data = response.data?.data;
    clients.value = Array.isArray(data) ? data : data?.clients || [];
  } catch (error: any) {
    showError(error, '加载客户端失败');
  } finally {
    loadingClients.value = false;
  }
}

async function loadWorkspaces() {
  loadingWorkspaces.value = true;
  try {
    const response = await axios.get('/api/plug/cli-agents/workspaces');
    const data = response.data?.data;
    workspaces.value = Array.isArray(data) ? data : data?.workspaces || [];
  } catch (error: any) {
    showError(error, '加载工作区失败');
  } finally {
    loadingWorkspaces.value = false;
  }
}

function openClientDialog(client?: CliClient) {
  editingClient.value = client || null;
  clientForm.name = client?.name || '';
  clientForm.agent_kind = client?.agent_kind || 'claude';
  clientForm.location_kind = client?.location_kind || 'local';
  clientForm.transport_kind = client?.transport_kind || (clientForm.location_kind === 'remote' ? 'remote_ws' : 'acp_stdio');
  clientForm.command = client?.command || '';
  clientForm.executable_path = client?.executable_path || '';
  clientForm.args_text = (client?.args || []).join(' ');
  clientForm.remote_url = client?.remote_url || '';
  clientForm.auth_type = client?.auth_type || 'none';
  clientForm.permission_policy = client?.permission_policy || 'ask';
  clientForm.env_text = client?.env ? JSON.stringify(client.env, null, 2) : '';
  clientForm.enabled = client?.enabled ?? true;
  clientDialogOpen.value = true;
}

async function saveClient() {
  savingClient.value = true;
  try {
    const payload = {
      name: clientForm.name.trim(),
      agent_kind: clientForm.agent_kind,
      location_kind: clientForm.location_kind,
      transport_kind: clientForm.transport_kind,
      command: clientForm.command.trim(),
      executable_path: clientForm.executable_path.trim(),
      args: splitArgs(clientForm.args_text),
      remote_url: clientForm.remote_url.trim(),
      auth_type: clientForm.auth_type,
      permission_policy: clientForm.permission_policy,
      env: parseEnv(clientForm.env_text),
      enabled: clientForm.enabled,
    };
    if (editingClient.value) {
      await axios.patch(`/api/plug/cli-agents/clients/${editingClient.value.id}`, payload);
    } else {
      await axios.post('/api/plug/cli-agents/clients', payload);
    }
    clientDialogOpen.value = false;
    await loadClients();
  } catch (error: any) {
    showError(error, '保存客户端失败');
  } finally {
    savingClient.value = false;
  }
}

async function toggleClient(client: CliClient) {
  try {
    await axios.patch(`/api/plug/cli-agents/clients/${client.id}`, { enabled: client.enabled });
  } catch (error: any) {
    client.enabled = !client.enabled;
    showError(error, '更新启用状态失败');
  }
}

async function checkClient(client: CliClient) {
  try {
    await axios.post(`/api/plug/cli-agents/clients/${client.id}/check`);
    await loadClients();
  } catch (error: any) {
    showError(error, '检测客户端失败');
  }
}

async function deleteClient(client: CliClient) {
  if (!window.confirm(`删除客户端「${client.name}」？`)) return;
  try {
    await axios.delete(`/api/plug/cli-agents/clients/${client.id}`);
    await loadClients();
  } catch (error: any) {
    showError(error, '删除客户端失败');
  }
}

function openWorkspaceDialog(workspace?: CliWorkspace) {
  editingWorkspace.value = workspace || null;
  workspaceForm.name = workspace?.name || '';
  workspaceForm.root_path = workspace?.root_path || '';
  workspaceForm.description = workspace?.description || '';
  workspaceForm.default_client_id = workspace?.default_client_id || null;
  workspaceDialogOpen.value = true;
}

async function saveWorkspace() {
  savingWorkspace.value = true;
  try {
    const payload = {
      name: workspaceForm.name.trim(),
      root_path: workspaceForm.root_path.trim(),
      description: workspaceForm.description.trim(),
      default_client_id: workspaceForm.default_client_id,
    };
    if (editingWorkspace.value) {
      await axios.patch(`/api/plug/cli-agents/workspaces/${editingWorkspace.value.id}`, payload);
    } else {
      await axios.post('/api/plug/cli-agents/workspaces', payload);
    }
    workspaceDialogOpen.value = false;
    await loadWorkspaces();
  } catch (error: any) {
    showError(error, '保存工作区失败');
  } finally {
    savingWorkspace.value = false;
  }
}

async function deleteWorkspace(workspace: CliWorkspace) {
  if (!window.confirm(`删除工作区「${workspace.name}」？`)) return;
  try {
    await axios.delete(`/api/plug/cli-agents/workspaces/${workspace.id}`);
    await loadWorkspaces();
  } catch (error: any) {
    showError(error, '删除工作区失败');
  }
}

function parseEnv(text: string) {
  const trimmed = text.trim();
  if (!trimmed) return {};
  return JSON.parse(trimmed);
}

function splitArgs(text: string) {
  return text
    .split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function clientName(clientId?: string | null) {
  if (!clientId) return '-';
  return clients.value.find((client) => client.id === clientId)?.name || clientId;
}

function clientDisplayTarget(client: CliClient) {
  if (client.location_kind === 'remote') return client.remote_url || '未配置远程地址';
  return client.executable_path || client.command || '未配置命令';
}

function agentKindLabel(kind: string) {
  return agentKindOptions.find((item) => item.value === kind)?.title || kind;
}

function transportLabel(kind: string) {
  return transportOptions.find((item) => item.value === kind)?.title || kind;
}

function statusLabel(status?: string) {
  const map: Record<string, string> = {
    ready: '可用',
    available: '可用',
    checked: '已检测',
    unavailable: '不可用',
    unknown: '未检测',
  };
  return map[status || 'unknown'] || status || '未检测';
}

function statusColor(status?: string) {
  if (status === 'ready' || status === 'checked' || status === 'available') return 'success';
  if (status === 'unavailable') return 'error';
  return 'default';
}

function showError(error: any, fallback: string) {
  errorText.value =
    error?.response?.data?.message ||
    error?.message ||
    fallback;
}
</script>

<style scoped>
.cli-agent-page {
  padding: 20px;
  padding-top: 8px;
  color: rgb(var(--v-theme-on-surface));
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
}

.page-header p {
  margin: 6px 0 0;
  color: rgba(var(--v-theme-on-surface), 0.66);
}

.cli-tabs {
  border-bottom: 1px solid rgba(var(--v-border-color), 0.16);
}

.cli-window {
  padding-top: 16px;
}

.toolbar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.toolbar-row .v-text-field {
  max-width: 360px;
}

.client-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.client-card {
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 8px;
  padding: 14px;
  background: rgb(var(--v-theme-surface));
}

.card-top,
.client-main,
.status-line,
.card-actions {
  display: flex;
  align-items: center;
}

.card-top {
  justify-content: space-between;
  gap: 12px;
}

.client-main {
  min-width: 0;
  gap: 10px;
}

.client-name {
  font-weight: 700;
  line-height: 1.3;
}

.client-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
}

.client-command {
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.status-line {
  gap: 8px;
  margin-top: 12px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
}

.card-actions {
  justify-content: flex-end;
  gap: 6px;
  margin-top: 12px;
}

.workspace-table {
  border: 1px solid rgba(var(--v-border-color), 0.16);
  border-radius: 8px;
  overflow: hidden;
}

.path-cell {
  max-width: 420px;
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.empty-state {
  padding: 28px;
  border: 1px dashed rgba(var(--v-border-color), 0.24);
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-align: center;
}

.dialog-grid {
  display: grid;
  gap: 12px;
}

.dialog-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 760px) {
  .page-header,
  .toolbar-row {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-row .v-text-field {
    max-width: none;
  }

  .dialog-row {
    grid-template-columns: 1fr;
  }
}
</style>
