<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-robot" class="mr-2" />


            {{ $t('agent.agents.title') }}


            <v-spacer />


            <v-btn color="primary" @click="openAddEditor" class="mr-2">


              <v-icon start icon="mdi-plus" />


              {{ $t('agent.agents.buttons.add') }}


            </v-btn>


            <v-btn variant="outlined" @click="loadAgents" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.agents.buttons.refresh') }}


            </v-btn>


            <v-menu>


              <template v-slot:activator="{ props }">


                <v-btn variant="outlined" v-bind="props">


                  <v-icon start icon="mdi-dots-vertical" />


                  {{ $t('agent.agents.buttons.more') }}


                </v-btn>


              </template>


              <v-list>


                <v-list-item @click="showTemplatesDialog = true">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-file-document-multiple" />


                  </template>


                  <v-list-item-title>{{ $t('agent.agents.buttons.templates') }}</v-list-item-title>


                </v-list-item>


                <v-list-item @click="importAgents">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-import" />


                  </template>


                  <v-list-item-title>{{ $t('agent.agents.buttons.import') }}</v-list-item-title>


                </v-list-item>


                <v-list-item @click="exportAgents">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-export" />


                  </template>


                  <v-list-item-title>{{ $t('agent.agents.buttons.export') }}</v-list-item-title>


                </v-list-item>


              </v-list>


            </v-menu>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.agents.subtitle') }}


          </v-card-subtitle>


        </v-card>


      </v-col>


    </v-row>





    <!-- 筛选和搜索 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-4">


          <v-card-text class="pb-2">


            <v-row align="center">


              <v-col cols="12" md="8">


                <v-tabs v-model="activeTab" color="primary">


                  <v-tab value="all">{{ $t('agent.agents.tabs.all') }}</v-tab>


                  <v-tab value="enabled">{{ $t('agent.agents.tabs.enabled') }}</v-tab>


                  <v-tab value="disabled">{{ $t('agent.agents.tabs.disabled') }}</v-tab>


                </v-tabs>


              </v-col>


              <v-col cols="12" md="4">


                <v-text-field


                  v-model="searchQuery"


                  :placeholder="$t('agent.agents.search.placeholder')"


                  prepend-inner-icon="mdi-magnify"


                  variant="outlined"


                  density="compact"


                  hide-details


                  clearable


                />


              </v-col>


            </v-row>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <!-- 智能体列-->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-card-text v-if="loading" class="text-center py-8">


            <v-progress-circular indeterminate color="primary" />


            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


          </v-card-text>





          <v-card-text v-else-if="filteredAgents.length === 0" class="text-center py-8">


            <v-icon icon="mdi-robot" size="60" color="grey-lighten-1" class="mb-4" />


            <p class="text-grey">{{ $t('agent.agents.empty') }}</p>


          </v-card-text>





          <v-container fluid v-else>


            <v-row>


              <v-col


                v-for="agent in filteredAgents"


                :key="agent.name"


                cols="12"


                sm="6"


                md="4"


                lg="3"


              >


                <AgentCard


                  :agent="agent"


                  @edit="openEditor"


                  @test="openTester"


                  @copy="copyAgent"


                  @delete="deleteAgent"


                  @toggle="toggleAgent"


                />


              </v-col>


            </v-row>


          </v-container>


        </v-card>


      </v-col>


    </v-row>





    <!-- 智能体编辑器 -->


    <AgentEditor


      v-model="showEditor"


      :agent="editingAgent"


      :is-editing="isEditing"


      @save="handleSaveAgent"


    />





    <!-- 智能体测试器 -->


    <AgentTester


      v-model="showTester"


      :agent="testingAgent"


    />





    <!-- 模板选择对话-->


    <v-dialog v-model="showTemplatesDialog" max-width="800">


      <v-card>


        <v-card-title>{{ $t('agent.agents.templates.title') }}</v-card-title>


        <v-card-text>


          <v-row>


            <v-col


              v-for="template in templates"


              :key="template.name"


              cols="12"


              sm="6"


              md="4"


            >


              <v-card hover @click="createFromTemplate(template)">


                <v-card-title class="text-subtitle-1">


                  <v-icon :icon="template.icon" class="mr-2" />


                  {{ template.name }}


                </v-card-title>


                <v-card-text>


                  <p class="text-body-2 text-grey">{{ template.description }}</p>


                </v-card-text>


              </v-card>


            </v-col>


          </v-row>


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showTemplatesDialog = false">{{ $t('common.close') }}</v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>





    <!-- 导入对话框-->


    <v-dialog v-model="showImportDialog" max-width="600">


      <v-card>


        <v-card-title>{{ $t('agent.agents.import.title') }}</v-card-title>


        <v-card-text>


          <v-file-input


            v-model="importFile"


            :label="$t('agent.agents.import.selectFile')"


            accept=".json"


            prepend-icon="mdi-file-json"


            show-size


          />


          <v-alert type="info" variant="tonal" class="mt-4">


            {{ $t('agent.agents.import.hint') }}


          </v-alert>


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">


            {{ $t('agent.agents.import.button') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.agents.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.agents.delete.confirm', { name: deletingAgent?.name }) }}


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showDeleteDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="error" @click="confirmDelete" :loading="deleting">


            {{ $t('common.delete') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>


  </v-container>


</template>





<script setup lang="ts">


import { ref, computed, onMounted } from 'vue';


import axios from 'axios';


import AgentCard from './AgentCard.vue';


import AgentEditor from './AgentEditor.vue';


import AgentTester from './AgentTester.vue';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();





// 状


const loading = ref(false);


const agents = ref<any[]>([]);


const activeTab = ref('all');


const searchQuery = ref('');





// 编辑


const showEditor = ref(false);


const editingAgent = ref<any>(null);


const isEditing = ref(false);





// 测试


const showTester = ref(false);


const testingAgent = ref<any>(null);





// 删除


const showDeleteDialog = ref(false);


const deletingAgent = ref<any>(null);


const deleting = ref(false);





// 导入


const showImportDialog = ref(false);


const importFile = ref<File | null>(null);


const importing = ref(false);





// 模板


const showTemplatesDialog = ref(false);


const templates = ref([


  {


    name: t('agent.agents.templates.assistant.name'),


    icon: 'mdi-robot',


    description: t('agent.agents.templates.assistant.description'),


    config: {


      role: t('agent.agents.templates.assistant.role'),


      goal: t('agent.agents.templates.assistant.goal'),


      backstory: t('agent.agents.templates.assistant.backstory'),


      tools: [],


      skills: [],


      knowledgeBases: [],


      planning: { enabled: false, maxSteps: 5 },


      memory: { enabled: true, type: 'short_term', maxMessages: 20 },


    },


  },


  {


    name: t('agent.agents.templates.researcher.name'),


    icon: 'mdi-magnify',


    description: t('agent.agents.templates.researcher.description'),


    config: {


      role: t('agent.agents.templates.researcher.role'),


      goal: t('agent.agents.templates.researcher.goal'),


      backstory: t('agent.agents.templates.researcher.backstory'),


      tools: [],


      skills: [],


      knowledgeBases: [],


      planning: { enabled: true, maxSteps: 10 },


      memory: { enabled: true, type: 'long_term', maxMessages: 50 },


    },


  },


  {


    name: t('agent.agents.templates.coder.name'),


    icon: 'mdi-code-braces',


    description: t('agent.agents.templates.coder.description'),


    config: {


      role: t('agent.agents.templates.coder.role'),


      goal: t('agent.agents.templates.coder.goal'),


      backstory: t('agent.agents.templates.coder.backstory'),


      tools: [],


      skills: [],


      knowledgeBases: [],


      planning: { enabled: true, maxSteps: 8 },


      memory: { enabled: true, type: 'short_term', maxMessages: 30 },


    },


  },


]);





// 计算属性


const filteredAgents = computed(() => {


  let result = agents.value;





  // 按状态筛


  if (activeTab.value === 'enabled') {


    result = result.filter(agent => agent.enabled);


  } else if (activeTab.value === 'disabled') {


    result = result.filter(agent => !agent.enabled);


  }





  // 按搜索词筛选


  if (searchQuery.value) {


    const query = searchQuery.value.toLowerCase();


    result = result.filter(agent =>


      agent.name.toLowerCase().includes(query) ||


      (agent.role && agent.role.toLowerCase().includes(query))


    );


  }





  return result;


});





// 加载智能体列


async function loadAgents() {


  loading.value = true;


  try {


    const response = await axios.get('/api/plug/agent/agents');


    if (response.data.status === 'ok') {


      agents.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load agents:', error);


  } finally {


    loading.value = false;


  }


}





// 打开添加编辑器


function openAddEditor() {


  editingAgent.value = null;


  isEditing.value = false;


  showEditor.value = true;


}





// 打开编辑器


function openEditor(agent: any) {


  editingAgent.value = { ...agent };


  isEditing.value = true;


  showEditor.value = true;


}





// 打开测试器


function openTester(agent: any) {


  testingAgent.value = agent;


  showTester.value = true;


}





// 复制智能


async function copyAgent(agent: any) {


  const newAgent = {


    ...agent,


    name: `${agent.name}_copy`,


  };


  delete (newAgent as any).id;





  try {


    await axios.post('/api/plug/agent/agents/add', newAgent);


    await loadAgents();


  } catch (error: any) {


    console.error('Failed to copy agent:', error);


    alert(error.response?.data?.message || t('agent.agents.messages.copyError'));


  }


}





// 删除智能


function deleteAgent(agent: any) {


  deletingAgent.value = agent;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingAgent.value) return;





  deleting.value = true;


  try {


    await axios.post('/api/plug/agent/agents/delete', {


      name: deletingAgent.value.name,


    });


    agents.value = agents.value.filter(a => a.name !== deletingAgent.value.name);


    showDeleteDialog.value = false;


    deletingAgent.value = null;


  } catch (error: any) {


    console.error('Failed to delete agent:', error);


    alert(error.response?.data?.message || t('agent.agents.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 切换智能体状


async function toggleAgent(agent: any) {


  try {


    await axios.post('/api/plug/agent/agents/toggle', {


      name: agent.name,


      enabled: agent.enabled,


    });


  } catch (error) {


    console.error('Failed to toggle agent:', error);


    agent.enabled = !agent.enabled;


  }


}





// 保存智能


async function handleSaveAgent(agentData: any) {


  try {


    if (isEditing.value) {


      await axios.post('/api/plug/agent/agents/update', agentData);


    } else {


      await axios.post('/api/plug/agent/agents/add', agentData);


    }


    showEditor.value = false;


    await loadAgents();


  } catch (error: any) {


    console.error('Failed to save agent:', error);


    throw error;


  }


}





// 从模板创


async function createFromTemplate(template: any) {


  editingAgent.value = {


    name: '',


    ...template.config,


    model: {


      provider: '',


      name: '',


      temperature: 0.7,


      maxTokens: 4096,


      topP: 1.0,


    },


    behavior: {


      maxRetries: 3,


      timeout: 60,


      verbose: false,


    },


    enabled: true,


  };


  isEditing.value = false;


  showTemplatesDialog.value = false;


  showEditor.value = true;


}





// 导入智能


function importAgents() {


  importFile.value = null;


  showImportDialog.value = true;


}





async function executeImport() {


  if (!importFile.value) return;





  importing.value = true;


  try {


    const text = await importFile.value.text();


    const data = JSON.parse(text);





    await axios.post('/api/plug/agent/agents/import', { agents: data });


    showImportDialog.value = false;


    await loadAgents();


  } catch (error: any) {


    console.error('Failed to import agents:', error);


    alert(error.response?.data?.message || t('agent.agents.messages.importError'));


  } finally {


    importing.value = false;


  }


}





// 导出智能


function exportAgents() {


  const data = JSON.stringify(agents.value, null, 2);


  const blob = new Blob([data], { type: 'application/json' });


  const url = URL.createObjectURL(blob);


  const a = document.createElement('a');


  a.href = url;


  a.download = `agents_${new Date().toISOString().slice(0, 10)}.json`;


  a.click();


  URL.revokeObjectURL(url);


}





onMounted(() => {


  loadAgents();


});


</script>





<style scoped>


.v-card {


  border-radius: 12px;


}


</style>


