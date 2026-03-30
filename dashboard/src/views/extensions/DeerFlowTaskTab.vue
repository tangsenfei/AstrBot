<template>
  <div class="deerflow-tab">
    <v-row>
      <v-col cols="12" md="8">
        <v-card class="rounded-lg mb-4" variant="flat">
          <v-card-title class="d-flex align-center py-4">
            <v-icon start>mdi-clipboard-list-outline</v-icon>
            {{ tm('deerflow.title') }}
          </v-card-title>
          <v-card-subtitle>{{ tm('deerflow.description') }}</v-card-subtitle>
          <v-card-text>
            <div class="d-flex ga-2 mb-4">
              <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreateDialog" :disabled="!hasProvider">
                {{ tm('deerflow.actions.create') }}
              </v-btn>
              <v-btn variant="outlined" prepend-icon="mdi-refresh" @click="loadTasks" :loading="loading">
                {{ tm('deerflow.actions.refresh') }}
              </v-btn>
            </div>

            <v-data-table
              :headers="headers"
              :items="tasks"
              :loading="loading"
              class="elevation-0"
              item-value="id"
            >
              <template v-slot:no-data>
                <div class="text-center py-8">
                  <v-icon size="64" color="grey-lighten-1">mdi-clipboard-text-off-outline</v-icon>
                  <p class="text-grey mt-2">{{ tm('deerflow.table.empty') }}</p>
                </div>
              </template>

              <template v-slot:item.status="{ item }">
                <v-chip :color="getStatusColor(item.status)" size="small">
                  {{ tm(`deerflow.status.${item.status}`) }}
                </v-chip>
              </template>

              <template v-slot:item.progress="{ item }">
                <v-progress-linear
                  :model-value="getProgressPercent(item)"
                  color="primary"
                  height="6"
                  rounded
                />
                <span class="text-caption">{{ getProgressText(item) }}</span>
              </template>

              <template v-slot:item.created_at="{ item }">
                {{ formatDate(item.created_at) }}
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn-group density="compact" variant="outlined">
                  <v-btn
                    v-if="item.status === 'pending'"
                    size="small"
                    color="success"
                    @click="startTask(item.id)"
                  >
                    <v-icon>mdi-play</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'waiting_approval'"
                    size="small"
                    color="primary"
                    @click="openPlanDialog(item)"
                  >
                    <v-icon>mdi-check</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="item.status === 'executing'"
                    size="small"
                    color="warning"
                    @click="pauseTask(item.id)"
                  >
                    <v-icon>mdi-pause</v-icon>
                  </v-btn>
                  <v-btn
                    v-if="['executing', 'paused'].includes(item.status)"
                    size="small"
                    color="error"
                    @click="cancelTask(item.id)"
                  >
                    <v-icon>mdi-stop</v-icon>
                  </v-btn>
                  <v-btn
                    size="small"
                    color="error"
                    variant="text"
                    @click="deleteTask(item.id)"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </v-btn-group>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card class="rounded-lg mb-4" variant="flat">
          <v-card-title class="py-4">
            <v-icon start>mdi-cog</v-icon>
            {{ tm('deerflow.config.title') }}
          </v-card-title>
          <v-card-text>
            <v-select
              v-model="selectedProvider"
              :items="providerItems"
              :label="tm('deerflow.config.provider')"
              variant="outlined"
              density="compact"
              class="mb-3"
              :loading="loadingProviders"
              @update:model-value="onProviderChange"
            />
            <v-switch
              v-model="thinkingEnabled"
              :label="tm('deerflow.config.thinking')"
              color="primary"
              hide-details
              class="mb-2"
              @change="saveOptions"
            />
            <v-switch
              v-model="planModeEnabled"
              :label="tm('deerflow.config.planMode')"
              color="primary"
              hide-details
              class="mb-2"
              @change="saveOptions"
            />
            <v-switch
              v-model="subagentEnabled"
              :label="tm('deerflow.config.subagent')"
              color="primary"
              hide-details
              class="mb-4"
              @change="saveOptions"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog v-model="createDialog" max-width="600">
      <v-card>
        <v-card-title>{{ tm('deerflow.form.title') }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newTask.title"
            :label="tm('deerflow.form.taskTitle')"
            variant="outlined"
            class="mb-3"
          />
          <v-textarea
            v-model="newTask.description"
            :label="tm('deerflow.form.taskDescription')"
            :placeholder="tm('deerflow.form.taskDescriptionPlaceholder')"
            variant="outlined"
            rows="4"
            class="mb-3"
          />
          <v-text-field
            :model-value="currentProviderInfo"
            :label="tm('deerflow.form.model')"
            variant="outlined"
            readonly
            class="mb-3"
            :hint="tm('deerflow.form.modelHint')"
            persistent-hint
          />
          <v-switch
            v-model="newTask.is_plan_mode"
            :label="tm('deerflow.form.planMode')"
            :hint="tm('deerflow.form.planModeHint')"
            color="primary"
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="createDialog = false">{{ tm('deerflow.actions.cancel') }}</v-btn>
          <v-btn color="primary" @click="createTask" :loading="creating">{{ tm('deerflow.actions.create') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="planDialog" max-width="700">
      <v-card v-if="selectedTask">
        <v-card-title>{{ tm('deerflow.plan.title') }}</v-card-title>
        <v-card-subtitle>{{ tm('deerflow.plan.approveHint') }}</v-card-subtitle>
        <v-card-text>
          <v-list>
            <v-list-item
              v-for="(todo, index) in selectedTask.todos"
              :key="todo.id"
              :class="{ 'bg-grey-lighten-4': todo.status === 'skipped' }"
            >
              <template v-slot:prepend>
                <v-avatar :color="getTodoColor(todo.status)" size="32">
                  <span class="text-white">{{ index + 1 }}</span>
                </v-avatar>
              </template>
              <v-list-item-title>{{ todo.content }}</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip :color="getTodoColor(todo.status)" size="x-small">
                  {{ tm(`deerflow.todoStatus.${todo.status}`) }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="planDialog = false">{{ tm('deerflow.actions.cancel') }}</v-btn>
          <v-btn color="primary" @click="approvePlan" :loading="approving">{{ tm('deerflow.actions.approve') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useModuleI18n } from '@/i18n/composables'
import axios from 'axios'

const { tm } = useModuleI18n('features/task-management')

interface Todo {
  id: string
  content: string
  status: string
  result?: string
  error?: string
}

interface Task {
  id: string
  title: string
  description: string
  status: string
  thread_id: string
  model_name?: string
  is_plan_mode: boolean
  todos: Todo[]
  result?: string
  error?: string
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
}

interface Provider {
  name: string
  provider_type: string
  models: string[]
  default_model?: string
}

const loading = ref(false)
const tasks = ref<Task[]>([])
const hasProvider = ref(false)
const currentProviderInfo = ref('')

const loadingProviders = ref(false)
const providers = ref<Provider[]>([])
const selectedProvider = ref('')
const thinkingEnabled = ref(true)
const planModeEnabled = ref(true)
const subagentEnabled = ref(false)

const createDialog = ref(false)
const creating = ref(false)
const newTask = ref({
  title: '',
  description: '',
  model_name: '',
  is_plan_mode: true
})

const planDialog = ref(false)
const approving = ref(false)
const selectedTask = ref<Task | null>(null)

const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})

const headers = [
  { title: tm('deerflow.table.headers.title'), key: 'title' },
  { title: tm('deerflow.table.headers.status'), key: 'status' },
  { title: tm('deerflow.table.headers.model'), key: 'model_name' },
  { title: tm('deerflow.table.headers.progress'), key: 'progress' },
  { title: tm('deerflow.table.headers.created'), key: 'created_at' },
  { title: tm('deerflow.table.headers.actions'), key: 'actions', sortable: false }
]

const apiBase = '/api/plug/task_manager'

const providerItems = computed(() => {
  // 使用 DeerFlow 模型列表
  return providers.value.map((model: any) => ({
    title: model.display_name || model.name,
    value: model.name
  }))
})

const showSnackbar = (message: string, color: string = 'success') => {
  snackbar.value = { show: true, message, color }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString()
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'grey',
    planning: 'info',
    waiting_approval: 'warning',
    executing: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'error',
    cancelled: 'grey'
  }
  return colors[status] || 'grey'
}

const getTodoColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'grey',
    in_progress: 'primary',
    completed: 'success',
    failed: 'error',
    skipped: 'warning'
  }
  return colors[status] || 'grey'
}

const getProgressPercent = (task: Task) => {
  if (!task.todos || task.todos.length === 0) return 0
  const completed = task.todos.filter(t => t.status === 'completed' || t.status === 'skipped').length
  return Math.round((completed / task.todos.length) * 100)
}

const getProgressText = (task: Task) => {
  if (!task.todos || task.todos.length === 0) return '0/0'
  const completed = task.todos.filter(t => t.status === 'completed').length
  return `${completed}/${task.todos.length}`
}

const loadTasks = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${apiBase}/tasks`)
    const result = response.data
    if (result.status === 'ok' && result.data) {
      tasks.value = result.data
    } else {
      tasks.value = []
    }
  } catch (error) {
    showSnackbar(tm('deerflow.messages.loadFailed'), 'error')
  } finally {
    loading.value = false
  }
}

const loadConfig = async () => {
  try {
    const response = await axios.get(`${apiBase}/config?t=${Date.now()}`)
    const result = response.data
    console.log('Config loaded:', result)
    
    if (result.status !== 'ok' || !result.data) {
      console.error('Config API error:', result.message)
      hasProvider.value = false
      return
    }
    
    const config = result.data
    // 使用 DeerFlow 模型列表
    providers.value = config.deerflow_models || []
    
    // 使用 provider_id 存储的是 DeerFlow 模型名称
    const modelName = config.deerflow?.provider_id || ''
    if (modelName && modelName.trim() !== '') {
      hasProvider.value = true
      currentProviderInfo.value = modelName
      selectedProvider.value = modelName
    } else if (providers.value.length > 0) {
      // 如果没有选择，默认选择第一个
      hasProvider.value = true
      const defaultModel = providers.value[0].name
      currentProviderInfo.value = defaultModel
      selectedProvider.value = defaultModel
    } else {
      hasProvider.value = false
      currentProviderInfo.value = ''
      selectedProvider.value = ''
    }
    
    thinkingEnabled.value = config.deerflow?.thinking_enabled ?? true
    planModeEnabled.value = config.deerflow?.is_plan_mode ?? true
    subagentEnabled.value = config.deerflow?.subagent_enabled ?? false
  } catch (error) {
    console.error('Failed to load config:', error)
    hasProvider.value = false
  }
}

const onProviderChange = async (value: string) => {
  if (!value) return
  
  try {
    await axios.post(`${apiBase}/config/provider`, {
      provider_id: value
    })
    hasProvider.value = true
    currentProviderInfo.value = value
    showSnackbar(tm('deerflow.messages.configSaved'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.configFailed'), 'error')
  }
}

const saveOptions = async () => {
  try {
    await axios.post(`${apiBase}/config/options`, {
      thinking_enabled: thinkingEnabled.value,
      is_plan_mode: planModeEnabled.value,
      subagent_enabled: subagentEnabled.value
    })
  } catch (error) {
    console.error('Failed to save options:', error)
  }
}

const openCreateDialog = () => {
  newTask.value = {
    title: '',
    description: '',
    model_name: selectedProvider.value,
    is_plan_mode: planModeEnabled.value
  }
  createDialog.value = true
}

const createTask = async () => {
  creating.value = true
  try {
    const response = await axios.post(`${apiBase}/tasks`, newTask.value)
    const result = response.data
    if (result.status === 'ok' && result.data) {
      tasks.value.unshift(result.data)
      createDialog.value = false
      showSnackbar(tm('deerflow.messages.createSuccess'))
    } else {
      showSnackbar(result.message || tm('deerflow.messages.createFailed'), 'error')
    }
  } catch (error) {
    showSnackbar(tm('deerflow.messages.createFailed'), 'error')
  } finally {
    creating.value = false
  }
}

const startTask = async (taskId: string) => {
  try {
    await axios.post(`${apiBase}/tasks/${taskId}/start`)
    const task = tasks.value.find(t => t.id === taskId)
    if (task) task.status = 'planning'
    showSnackbar(tm('deerflow.messages.startSuccess'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.startFailed'), 'error')
  }
}

const pauseTask = async (taskId: string) => {
  try {
    await axios.post(`${apiBase}/tasks/${taskId}/pause`)
    const task = tasks.value.find(t => t.id === taskId)
    if (task) task.status = 'paused'
    showSnackbar(tm('deerflow.messages.pauseSuccess'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.pauseFailed'), 'error')
  }
}

const cancelTask = async (taskId: string) => {
  try {
    await axios.post(`${apiBase}/tasks/${taskId}/cancel`)
    const task = tasks.value.find(t => t.id === taskId)
    if (task) task.status = 'cancelled'
    showSnackbar(tm('deerflow.messages.cancelSuccess'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.cancelFailed'), 'error')
  }
}

const openPlanDialog = (task: Task) => {
  selectedTask.value = task
  planDialog.value = true
}

const approvePlan = async () => {
  if (!selectedTask.value) return
  approving.value = true
  try {
    await axios.post(`${apiBase}/tasks/${selectedTask.value.id}/approve`)
    selectedTask.value.status = 'executing'
    planDialog.value = false
    showSnackbar(tm('deerflow.messages.approveSuccess'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.approveFailed'), 'error')
  } finally {
    approving.value = false
  }
}

const deleteTask = async (taskId: string) => {
  try {
    await axios.delete(`${apiBase}/tasks/${taskId}`)
    tasks.value = tasks.value.filter(t => t.id !== taskId)
    showSnackbar(tm('deerflow.messages.deleteSuccess'))
  } catch (error) {
    showSnackbar(tm('deerflow.messages.deleteFailed'), 'error')
  }
}

onMounted(() => {
  loadTasks()
  loadConfig()
})
</script>

<style scoped>
.deerflow-tab {
  padding: 0;
}
</style>
