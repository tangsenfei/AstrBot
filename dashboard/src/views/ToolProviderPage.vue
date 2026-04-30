<template>
  <v-container fluid class="pa-6">
    <v-row>
      <v-col cols="12">
        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon icon="mdi-toolbox" class="mr-2" />
            工具管理
            <v-spacer />
            <v-btn color="primary" @click="openAddDialog">
              <v-icon start icon="mdi-plus" />
              添加工具
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            管理 MCP 工具和 API Wrapper
          </v-card-subtitle>
        </v-card>

        <v-card>
          <v-tabs v-model="activeTab">
            <v-tab value="all">全部工具</v-tab>
            <v-tab value="mcp">MCP</v-tab>
            <v-tab value="api_wrapper">API Wrapper</v-tab>
          </v-tabs>

          <v-card-text>
            <v-data-table
              :headers="headers"
              :items="filteredTools"
              :loading="loading"
              class="elevation-1"
            >
              <template v-slot:item.source="{ item }">
                <v-chip :color="getSourceColor(item.source)" size="small">
                  {{ item.source }}
                </v-chip>
              </template>

              <template v-slot:item.status="{ item }">
                <v-switch
                  v-model="item.status"
                  true-value="enabled"
                  false-value="disabled"
                  color="success"
                  hide-details
                  @change="toggleTool(item)"
                />
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn icon size="small" @click="testTool(item)" color="info" class="mr-2" title="调试">
                  <v-icon icon="mdi-bug-play" />
                </v-btn>
                <v-btn icon size="small" @click="editTool(item)" color="primary" class="mr-2">
                  <v-icon icon="mdi-pencil" />
                </v-btn>
                <v-btn icon size="small" @click="deleteTool(item)" color="error">
                  <v-icon icon="mdi-delete" />
                </v-btn>
              </template>

              <template v-slot:no-data>
                <div class="text-center py-8">
                  <v-icon icon="mdi-tools" size="60" color="grey-lighten-1" class="mb-4" />
                  <p class="text-grey">暂无工具，请添加新工具</p>
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog v-model="showAddDialog" max-width="900" scrollable>
      <v-card>
        <v-card-title>{{ isEditing ? '编辑工具' : '添加工具' }}</v-card-title>

        <v-card-text style="max-height: 70vh;">
          <v-tabs v-model="addTab" v-if="!isEditing">
            <v-tab value="api">API Wrapper</v-tab>
            <v-tab value="mcp">MCP Server</v-tab>
          </v-tabs>

          <v-window v-model="addTab" class="mt-4">
            <v-window-item value="api">
              <v-form ref="apiForm">
                <v-text-field
                  v-model="apiConfig.name"
                  label="工具名称"
                  :rules="[v => !!v || '必填']"
                  hint="如: feishu_send_message"
                  class="mb-3"
                />
                <v-text-field
                  v-model="apiConfig.description"
                  label="工具描述"
                  hint="描述工具的功能，LLM 会根据此描述决定是否调用"
                  class="mb-3"
                />
                <v-text-field
                  v-model="apiConfig.url"
                  label="API URL"
                  :rules="[v => !!v || '必填']"
                  hint="支持变量替换: https://api.example.com/{endpoint}"
                  class="mb-3"
                />
                <v-select
                  v-model="apiConfig.method"
                  :items="['GET', 'POST', 'PUT', 'DELETE']"
                  label="HTTP 方法"
                  class="mb-3"
                />
                <v-text-field
                  v-model.number="apiConfig.timeout"
                  label="超时时间 (秒)"
                  type="number"
                  class="mb-3"
                />

                <v-divider class="my-4" />
                <h3 class="text-subtitle-1 mb-3">请求头</h3>
                <v-textarea
                  v-model="apiConfig.headersJson"
                  label="请求头 (JSON)"
                  hint='{"Authorization": "Bearer {token}", "Content-Type": "application/json"}'
                  rows="3"
                  class="mb-3"
                />

                <v-divider class="my-4" />
                <h3 class="text-subtitle-1 mb-3">请求体</h3>
                <v-textarea
                  v-model="apiConfig.bodyJson"
                  label="请求体模板 (JSON)"
                  hint='{"text": "{message}", "user_id": "{user_id}"}'
                  rows="4"
                  class="mb-3"
                />

                <v-divider class="my-4" />
                <h3 class="text-subtitle-1 mb-3">参数定义</h3>
                <v-textarea
                  v-model="apiConfig.paramsSchemaJson"
                  label="参数 Schema (JSON)"
                  hint='[{"name": "message", "type": "string", "description": "消息内容", "required": true}]'
                  rows="4"
                  class="mb-3"
                />

                <v-divider class="my-4" />
                <h3 class="text-subtitle-1 mb-3">响应提取</h3>
                <v-text-field
                  v-model="apiConfig.responsePath"
                  label="响应路径 (可选)"
                  hint="从响应中提取数据的路径，如: data.result"
                  class="mb-3"
                />
              </v-form>
            </v-window-item>

            <v-window-item value="mcp">
              <v-form ref="mcpForm">
                <v-text-field
                  v-model="mcpConfig.name"
                  label="服务器名称"
                  :rules="[v => !!v || '必填']"
                  hint="如: filesystem"
                  class="mb-3"
                />
                <v-text-field
                  v-model="mcpConfig.command"
                  label="命令"
                  hint="如: npx"
                  class="mb-3"
                />
                <v-textarea
                  v-model="mcpConfig.argsJson"
                  label="参数 (JSON 数组)"
                  hint='["-y", "@modelcontextprotocol/server-filesystem", "/data"]'
                  class="mb-3"
                />
                <v-textarea
                  v-model="mcpConfig.envJson"
                  label="环境变量 (JSON 对象)"
                  hint='{"GITHUB_TOKEN": "xxx"}'
                  class="mb-3"
                />
              </v-form>
            </v-window-item>
          </v-window>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn @click="showAddDialog = false">取消</v-btn>
          <v-btn color="primary" @click="isEditing ? updateTool() : addTool()" :loading="adding">
            {{ isEditing ? '保存' : '添加' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 调试对话框 -->
    <v-dialog v-model="showTestDialog" max-width="800" scrollable>
      <v-card>
        <v-card-title>调试工具: {{ testingTool?.name }}</v-card-title>
        <v-card-text style="max-height: 70vh;">
          <v-alert v-if="testingTool?.description" type="info" class="mb-4">
            {{ testingTool.description }}
          </v-alert>

          <v-divider class="my-4" />
          <h3 class="text-subtitle-1 mb-3">输入参数 (JSON)</h3>
          <v-textarea
            v-model="testParamsJson"
            label="参数 (JSON 对象)"
            hint='{"message": "测试消息", "user_id": "12345"}'
            rows="6"
            class="mb-3"
            :error="testParamsError"
            :error-messages="testParamsErrorMsg"
          />

          <v-divider class="my-4" />
          <h3 class="text-subtitle-1 mb-3">执行结果</h3>
          <v-card v-if="testResult !== null" :color="testSuccess ? 'success' : 'error'" variant="outlined">
            <v-card-text>
              <pre style="white-space: pre-wrap; word-break: break-word;">{{ testResult }}</pre>
            </v-card-text>
          </v-card>
          <v-card v-else-if="testing" variant="outlined" class="pa-4 text-center">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-2">正在执行...</p>
          </v-card>
          <v-card v-else variant="outlined" class="pa-4 text-center text-grey">
            点击"执行测试"查看结果
          </v-card>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showTestDialog = false">关闭</v-btn>
          <v-btn color="primary" @click="executeTest" :loading="testing">执行测试</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';

const loading = ref(false);
const adding = ref(false);
const tools = ref<any[]>([]);
const showAddDialog = ref(false);
const activeTab = ref('all');
const addTab = ref('api');
const isEditing = ref(false);
const editingToolName = ref('');

// 调试相关
const showTestDialog = ref(false);
const testingTool = ref<any>(null);
const testParamsJson = ref('{}');
const testParamsError = ref(false);
const testParamsErrorMsg = ref('');
const testing = ref(false);
const testResult = ref<string | null>(null);
const testSuccess = ref(false);

const headers = [
  { title: '工具名称', key: 'name', sortable: true },
  { title: '描述', key: 'description', sortable: false },
  { title: '来源', key: 'source', sortable: true },
  { title: '状态', key: 'status', sortable: true },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
];

const apiConfig = ref({
  name: '',
  description: '',
  url: '',
  method: 'POST',
  timeout: 30,
  headersJson: '',
  bodyJson: '',
  paramsSchemaJson: '',
  responsePath: '',
});

const mcpConfig = ref({
  name: '',
  command: 'npx',
  argsJson: '',
  envJson: '',
});

const filteredTools = computed(() => {
  if (activeTab.value === 'all') {
    return tools.value;
  }
  return tools.value.filter(tool => tool.source === activeTab.value);
});

function getSourceColor(source: string) {
  switch (source) {
    case 'mcp':
      return 'primary';
    case 'api_wrapper':
      return 'success';
    default:
      return 'grey';
  }
}

async function loadTools() {
  loading.value = true;
  try {
    const response = await axios.get('/api/plug/tool-provider/tools');
    if (response.data.status === 'ok') {
      tools.value = response.data.data || [];
    }
  } catch (error) {
    console.error('Failed to load tools:', error);
  } finally {
    loading.value = false;
  }
}

async function toggleTool(tool: any) {
  try {
    await axios.post('/api/plug/tool-provider/tools/toggle', {
      name: tool.name,
      enabled: tool.status === 'enabled',
    });
  } catch (error) {
    console.error('Failed to toggle tool:', error);
    tool.status = tool.status === 'enabled' ? 'disabled' : 'enabled';
  }
}

async function deleteTool(tool: any) {
  if (!confirm(`确定要删除工具 "${tool.name}" 吗？`)) {
    return;
  }

  try {
    await axios.post('/api/plug/tool-provider/tools/delete', {
      name: tool.name,
    });
    tools.value = tools.value.filter(t => t.name !== tool.name);
  } catch (error) {
    console.error('Failed to delete tool:', error);
    alert('删除失败');
  }
}

function openAddDialog() {
  resetApiConfig();
  addTab.value = 'api';
  showAddDialog.value = true;
}

function testTool(tool: any) {
  testingTool.value = tool;
  testParamsJson.value = '{}';
  testParamsError.value = false;
  testParamsErrorMsg.value = '';
  testResult.value = null;
  testSuccess.value = false;
  showTestDialog.value = true;
}

async function executeTest() {
  // 验证 JSON
  let params = {};
  try {
    params = JSON.parse(testParamsJson.value);
    testParamsError.value = false;
    testParamsErrorMsg.value = '';
  } catch (e) {
    testParamsError.value = true;
    testParamsErrorMsg.value = '无效的 JSON 格式';
    return;
  }

  testing.value = true;
  testResult.value = null;

  try {
    const response = await axios.post('/api/plug/tool-provider/tools/test', {
      name: testingTool.value.name,
      params: params,
    });

    if (response.data.status === 'ok') {
      testSuccess.value = true;
      const result = response.data.data;
      if (result.result) {
        // 尝试格式化 JSON
        try {
          const parsed = JSON.parse(result.result);
          testResult.value = JSON.stringify(parsed, null, 2);
        } catch {
          testResult.value = result.result;
        }
      } else {
        testResult.value = '执行成功，无返回值';
      }
    } else {
      testSuccess.value = false;
      testResult.value = response.data.message || '执行失败';
    }
  } catch (error: any) {
    testSuccess.value = false;
    testResult.value = error.response?.data?.message || error.message || '请求失败';
  } finally {
    testing.value = false;
  }
}

function editTool(tool: any) {
  // 只支持 API Wrapper 类型的编辑
  if (tool.source !== 'api_wrapper') {
    alert('暂不支持编辑 MCP 类型的工具');
    return;
  }

  isEditing.value = true;
  editingToolName.value = tool.name;
  addTab.value = 'api';

  // 填充表单数据
  const config = tool.config || {};
  apiConfig.value = {
    name: tool.name,
    description: tool.description || '',
    url: config.url || '',
    method: config.method || 'POST',
    timeout: config.timeout || 30,
    headersJson: config.headers ? JSON.stringify(config.headers, null, 2) : '',
    bodyJson: config.body ? JSON.stringify(config.body, null, 2) : '',
    paramsSchemaJson: config.params_schema ? JSON.stringify(config.params_schema, null, 2) : '',
    responsePath: config.response_path || '',
  };

  showAddDialog.value = true;
}

async function updateTool() {
  adding.value = true;
  try {
    if (!apiConfig.value.name || !apiConfig.value.url) {
      alert('请填写必填字段');
      adding.value = false;
      return;
    }

    const config: any = {
      name: apiConfig.value.name,
      description: apiConfig.value.description,
      url: apiConfig.value.url,
      method: apiConfig.value.method,
      timeout: apiConfig.value.timeout,
    };

    if (apiConfig.value.headersJson) {
      const headers = parseJsonSafe(apiConfig.value.headersJson, {});
      if (headers === null) {
        alert('请求头 JSON 格式错误');
        adding.value = false;
        return;
      }
      config.headers = headers;
    }

    if (apiConfig.value.bodyJson) {
      const body = parseJsonSafe(apiConfig.value.bodyJson, {});
      if (body === null) {
        alert('请求体 JSON 格式错误');
        adding.value = false;
        return;
      }
      config.body = body;
    }

    if (apiConfig.value.paramsSchemaJson) {
      const paramsSchema = parseJsonSafe(apiConfig.value.paramsSchemaJson, []);
      if (paramsSchema === null) {
        alert('参数 Schema JSON 格式错误');
        adding.value = false;
        return;
      }
      config.params_schema = paramsSchema;
    }

    if (apiConfig.value.responsePath) {
      config.response_path = apiConfig.value.responsePath;
    }

    await axios.post('/api/plug/tool-provider/tools/update', {
      name: editingToolName.value,
      config: config,
      description: apiConfig.value.description,
    });

    showAddDialog.value = false;
    resetApiConfig();
    isEditing.value = false;
    editingToolName.value = '';
    await loadTools();
  } catch (error: any) {
    console.error('Failed to update tool:', error);
    alert(error.response?.data?.message || '更新失败');
  } finally {
    adding.value = false;
  }
}

function parseJsonSafe(jsonStr: string, defaultValue: any) {
  if (!jsonStr || !jsonStr.trim()) {
    return defaultValue;
  }
  try {
    return JSON.parse(jsonStr);
  } catch (e) {
    return null;
  }
}

async function addTool() {
  adding.value = true;
  try {
    if (addTab.value === 'api') {
      if (!apiConfig.value.name || !apiConfig.value.url) {
        alert('请填写必填字段');
        adding.value = false;
        return;
      }

      const config: any = {
        name: apiConfig.value.name,
        description: apiConfig.value.description,
        url: apiConfig.value.url,
        method: apiConfig.value.method,
        timeout: apiConfig.value.timeout,
      };

      if (apiConfig.value.headersJson) {
        const headers = parseJsonSafe(apiConfig.value.headersJson, {});
        if (headers === null) {
          alert('请求头 JSON 格式错误');
          adding.value = false;
          return;
        }
        config.headers = headers;
      }

      if (apiConfig.value.bodyJson) {
        const body = parseJsonSafe(apiConfig.value.bodyJson, {});
        if (body === null) {
          alert('请求体 JSON 格式错误');
          adding.value = false;
          return;
        }
        config.body = body;
      }

      if (apiConfig.value.paramsSchemaJson) {
        const paramsSchema = parseJsonSafe(apiConfig.value.paramsSchemaJson, []);
        if (paramsSchema === null) {
          alert('参数 Schema JSON 格式错误');
          adding.value = false;
          return;
        }
        config.params_schema = paramsSchema;
      }

      if (apiConfig.value.responsePath) {
        config.response_path = apiConfig.value.responsePath;
      }

      await axios.post('/api/plug/tool-provider/tools/add', {
        type: 'api_wrapper',
        config: config,
      });
    } else {
      if (!mcpConfig.value.name) {
        alert('请填写服务器名称');
        adding.value = false;
        return;
      }

      let args: string[] = [];
      let env: Record<string, string> = {};

      if (mcpConfig.value.argsJson) {
        try {
          args = JSON.parse(mcpConfig.value.argsJson);
        } catch (e) {
          alert('参数格式错误，请输入有效的 JSON 数组');
          adding.value = false;
          return;
        }
      }

      if (mcpConfig.value.envJson) {
        try {
          env = JSON.parse(mcpConfig.value.envJson);
        } catch (e) {
          alert('环境变量格式错误，请输入有效的 JSON 对象');
          adding.value = false;
          return;
        }
      }

      await axios.post('/api/plug/tool-provider/mcp/add', {
        name: mcpConfig.value.name,
        config: {
          command: mcpConfig.value.command,
          args: args,
          env: env,
        },
      });
    }

    showAddDialog.value = false;
    resetApiConfig();
    await loadTools();
  } catch (error: any) {
    console.error('Failed to add tool:', error);
    alert(error.response?.data?.message || '添加失败');
  } finally {
    adding.value = false;
  }
}

function resetApiConfig() {
  apiConfig.value = {
    name: '',
    description: '',
    url: '',
    method: 'POST',
    timeout: 30,
    headersJson: '',
    bodyJson: '',
    paramsSchemaJson: '',
    responsePath: '',
  };
  mcpConfig.value = {
    name: '',
    command: 'npx',
    argsJson: '',
    envJson: '',
  };
  isEditing.value = false;
  editingToolName.value = '';
}

onMounted(() => {
  loadTools();
});
</script>

<style scoped>
.v-card {
  border-radius: 12px;
}
</style>
