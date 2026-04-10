<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-graph" class="mr-2" />


            {{ $t('agent.flows.title') }}


            <v-spacer />


            <v-btn color="primary" @click="openAddEditor" class="mr-2">


              <v-icon start icon="mdi-plus" />


              {{ $t('agent.flows.buttons.add') }}


            </v-btn>


            <v-btn variant="outlined" @click="loadFlows" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.flows.buttons.refresh') }}


            </v-btn>


            <v-menu>


              <template v-slot:activator="{ props }">


                <v-btn variant="outlined" v-bind="props">


                  <v-icon start icon="mdi-dots-vertical" />


                  {{ $t('agent.flows.buttons.more') }}


                </v-btn>


              </template>


              <v-list>


                <v-list-item @click="importFlows">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-import" />


                  </template>


                  <v-list-item-title>{{ $t('agent.flows.buttons.import') }}</v-list-item-title>


                </v-list-item>


                <v-list-item @click="exportFlows">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-export" />


                  </template>


                  <v-list-item-title>{{ $t('agent.flows.buttons.export') }}</v-list-item-title>


                </v-list-item>


              </v-list>


            </v-menu>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.flows.subtitle') }}


          </v-card-subtitle>


        </v-card>


      </v-col>


    </v-row>





    <!-- 搜索 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-4">


          <v-card-text class="pb-2">


            <v-row align="center">


              <v-col cols="12" md="8">


                <v-tabs v-model="activeTab" color="primary">


                  <v-tab value="all">{{ $t('agent.flows.tabs.all') }}</v-tab>


                  <v-tab value="enabled">{{ $t('agent.flows.tabs.enabled') }}</v-tab>


                  <v-tab value="disabled">{{ $t('agent.flows.tabs.disabled') }}</v-tab>


                </v-tabs>


              </v-col>


              <v-col cols="12" md="4">


                <v-text-field


                  v-model="searchQuery"


                  :placeholder="$t('agent.flows.search.placeholder')"


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





    <!-- Flow 列表 -->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-card-text v-if="loading" class="text-center py-8">


            <v-progress-circular indeterminate color="primary" />


            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


          </v-card-text>





          <v-card-text v-else-if="filteredFlows.length === 0" class="text-center py-8">


            <v-icon icon="mdi-graph" size="60" color="grey-lighten-1" class="mb-4" />


            <p class="text-grey">{{ $t('agent.flows.empty') }}</p>


          </v-card-text>





          <v-container fluid v-else>


            <v-row>


              <v-col


                v-for="flow in filteredFlows"


                :key="flow.name"


                cols="12"


                sm="6"


                md="4"


                lg="3"


              >


                <v-card hover class="flow-card">


                  <v-card-title class="d-flex align-center pb-2">


                    <v-icon icon="mdi-graph" color="primary" class="mr-2" />


                    <span class="text-truncate">{{ flow.name }}</span>


                    <v-spacer />


                    <v-chip


                      :color="flow.enabled ? 'success' : 'default'"


                      size="small"


                      variant="tonal"


                    >


                      {{ flow.enabled ? $t('agent.flows.status.enabled') : $t('agent.flows.status.disabled') }}


                    </v-chip>


                  </v-card-title>





                  <v-card-text class="pb-2">


                    <p class="text-body-2 text-grey mb-3">


                      {{ flow.description || $t('agent.flows.card.noDescription') }}


                    </p>


                    <v-row dense>


                      <v-col cols="6">


                        <div class="text-caption text-grey">


                          {{ $t('agent.flows.card.nodes') }}


                        </div>


                        <div class="text-h6">


                          {{ flow.nodes?.length || 0 }}


                        </div>


                      </v-col>


                      <v-col cols="6">


                        <div class="text-caption text-grey">


                          {{ $t('agent.flows.card.edges') }}


                        </div>


                        <div class="text-h6">


                          {{ flow.edges?.length || 0 }}


                        </div>


                      </v-col>


                    </v-row>


                  </v-card-text>





                  <v-divider />





                  <v-card-actions class="pa-2">


                    <v-btn


                      size="small"


                      variant="text"


                      color="primary"


                      @click="openEditor(flow)"


                    >


                      <v-icon start icon="mdi-pencil" />


                      {{ $t('agent.flows.card.edit') }}


                    </v-btn>


                    <v-btn


                      size="small"


                      variant="text"


                      color="success"


                      @click="executeFlow(flow)"


                    >


                      <v-icon start icon="mdi-play" />


                      {{ $t('agent.flows.card.execute') }}


                    </v-btn>


                    <v-spacer />


                    <v-menu>


                      <template v-slot:activator="{ props }">


                        <v-btn size="small" variant="text" v-bind="props">


                          <v-icon icon="mdi-dots-vertical" />


                        </v-btn>


                      </template>


                      <v-list density="compact">


                        <v-list-item @click="copyFlow(flow)">


                          <template v-slot:prepend>


                            <v-icon icon="mdi-content-copy" />


                          </template>


                          <v-list-item-title>{{ $t('agent.flows.card.copy') }}</v-list-item-title>


                        </v-list-item>


                        <v-list-item @click="toggleFlow(flow)">


                          <template v-slot:prepend>


                            <v-icon :icon="flow.enabled ? 'mdi-pause' : 'mdi-play'" />


                          </template>


                          <v-list-item-title>


                            {{ flow.enabled ? $t('agent.flows.card.disable') : $t('agent.flows.card.enable') }}


                          </v-list-item-title>


                        </v-list-item>


                        <v-list-item @click="deleteFlow(flow)" class="text-error">


                          <template v-slot:prepend>


                            <v-icon icon="mdi-delete" color="error" />


                          </template>


                          <v-list-item-title>{{ $t('agent.flows.card.delete') }}</v-list-item-title>


                        </v-list-item>


                      </v-list>


                    </v-menu>


                  </v-card-actions>


                </v-card>


              </v-col>


            </v-row>


          </v-container>


        </v-card>


      </v-col>


    </v-row>





    <!-- Flow 编辑-->


    <FlowEditor


      v-model="showEditor"


      :flow="editingFlow"


      :is-editing="isEditing"


      @save="handleSaveFlow"


    />





    <!-- 导入对话框-->


    <v-dialog v-model="showImportDialog" max-width="600">


      <v-card>


        <v-card-title>{{ $t('agent.flows.import.title') }}</v-card-title>


        <v-card-text>


          <v-file-input


            v-model="importFile"


            :label="$t('agent.flows.import.selectFile')"


            accept=".json"


            prepend-icon="mdi-file-json"


            show-size


          />


          <v-alert type="info" variant="tonal" class="mt-4">


            {{ $t('agent.flows.import.hint') }}


          </v-alert>


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">


            {{ $t('agent.flows.import.button') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.flows.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.flows.delete.confirm', { name: deletingFlow?.name }) }}


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





    <!-- 执行对话-->


    <v-dialog v-model="showExecuteDialog" max-width="600">


      <v-card>


        <v-card-title>{{ $t('agent.flows.execute.title') }}</v-card-title>


        <v-card-text>


          <v-alert type="info" variant="tonal" class="mb-4">


            {{ $t('agent.flows.execute.hint', { name: executingFlow?.name }) }}


          </v-alert>


          <v-textarea


            v-model="executeInput"


            :label="$t('agent.flows.execute.input')"


            rows="4"


            auto-grow


          />


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showExecuteDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="primary" @click="confirmExecute" :loading="executing">


            {{ $t('agent.flows.execute.button') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>


  </v-container>


</template>





<script setup lang="ts">


import { ref, computed, onMounted } from 'vue';


import axios from 'axios';


import FlowEditor from './FlowEditor.vue';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();





// 状


const loading = ref(false);


const flows = ref<any[]>([]);


const activeTab = ref('all');


const searchQuery = ref('');





// 编辑


const showEditor = ref(false);


const editingFlow = ref<any>(null);


const isEditing = ref(false);





// 删除


const showDeleteDialog = ref(false);


const deletingFlow = ref<any>(null);


const deleting = ref(false);





// 导入


const showImportDialog = ref(false);


const importFile = ref<File | null>(null);


const importing = ref(false);





// 执行


const showExecuteDialog = ref(false);


const executingFlow = ref<any>(null);


const executeInput = ref('');


const executing = ref(false);





// 计算属性


const filteredFlows = computed(() => {


  let result = flows.value;





  // 按状态筛


  if (activeTab.value === 'enabled') {


    result = result.filter(flow => flow.enabled);


  } else if (activeTab.value === 'disabled') {


    result = result.filter(flow => !flow.enabled);


  }





  // 按搜索词筛选


  if (searchQuery.value) {


    const query = searchQuery.value.toLowerCase();


    result = result.filter(flow =>


      flow.name.toLowerCase().includes(query) ||


      (flow.description && flow.description.toLowerCase().includes(query))


    );


  }





  return result;


});





// 加载 Flow 列表


async function loadFlows() {


  loading.value = true;


  try {


    const response = await axios.get('/api/plug/agent/flows');


    if (response.data.status === 'ok') {


      flows.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load flows:', error);


  } finally {


    loading.value = false;


  }


}





// 打开添加编辑器


function openAddEditor() {


  editingFlow.value = null;


  isEditing.value = false;


  showEditor.value = true;


}





// 打开编辑器


function openEditor(flow: any) {


  editingFlow.value = { ...flow };


  isEditing.value = true;


  showEditor.value = true;


}





// 复制 Flow


async function copyFlow(flow: any) {


  const newFlow = {


    ...flow,


    name: `${flow.name}_copy`,


  };


  delete (newFlow as any).id;





  try {


    await axios.post('/api/plug/agent/flows/add', newFlow);


    await loadFlows();


  } catch (error: any) {


    console.error('Failed to copy flow:', error);


    alert(error.response?.data?.message || t('agent.flows.messages.copyError'));


  }


}





// 删除 Flow


function deleteFlow(flow: any) {


  deletingFlow.value = flow;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingFlow.value) return;





  deleting.value = true;


  try {


    await axios.post('/api/plug/agent/flows/delete', {


      name: deletingFlow.value.name,


    });


    flows.value = flows.value.filter(f => f.name !== deletingFlow.value.name);


    showDeleteDialog.value = false;


    deletingFlow.value = null;


  } catch (error: any) {


    console.error('Failed to delete flow:', error);


    alert(error.response?.data?.message || t('agent.flows.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 切换 Flow 状


async function toggleFlow(flow: any) {


  try {


    await axios.post('/api/plug/agent/flows/toggle', {


      name: flow.name,


      enabled: !flow.enabled,


    });


    flow.enabled = !flow.enabled;


  } catch (error) {


    console.error('Failed to toggle flow:', error);


  }


}





// 保存 Flow


async function handleSaveFlow(flowData: any) {


  try {


    if (isEditing.value) {


      await axios.post('/api/plug/agent/flows/update', flowData);


    } else {


      await axios.post('/api/plug/agent/flows/add', flowData);


    }


    showEditor.value = false;


    await loadFlows();


  } catch (error: any) {


    console.error('Failed to save flow:', error);


    throw error;


  }


}





// 执行 Flow


function executeFlow(flow: any) {


  executingFlow.value = flow;


  executeInput.value = '';


  showExecuteDialog.value = true;


}





// 确认执行


async function confirmExecute() {


  if (!executingFlow.value) return;





  executing.value = true;


  try {


    await axios.post('/api/plug/agent/flows/execute', {


      name: executingFlow.value.name,


      input: executeInput.value,


    });


    showExecuteDialog.value = false;


  } catch (error: any) {


    console.error('Failed to execute flow:', error);


    alert(error.response?.data?.message || t('agent.flows.messages.executeError'));


  } finally {


    executing.value = false;


  }


}





// 导入 Flow


function importFlows() {


  importFile.value = null;


  showImportDialog.value = true;


}





async function executeImport() {


  if (!importFile.value) return;





  importing.value = true;


  try {


    const text = await importFile.value.text();


    const data = JSON.parse(text);





    await axios.post('/api/plug/agent/flows/import', { flows: data });


    showImportDialog.value = false;


    await loadFlows();


  } catch (error: any) {


    console.error('Failed to import flows:', error);


    alert(error.response?.data?.message || t('agent.flows.messages.importError'));


  } finally {


    importing.value = false;


  }


}





// 导出 Flow


function exportFlows() {


  const data = JSON.stringify(flows.value, null, 2);


  const blob = new Blob([data], { type: 'application/json' });


  const url = URL.createObjectURL(blob);


  const a = document.createElement('a');


  a.href = url;


  a.download = `flows_${new Date().toISOString().slice(0, 10)}.json`;


  a.click();


  URL.revokeObjectURL(url);


}





onMounted(() => {


  loadFlows();


});


</script>





<style scoped>


.flow-card {


  border-radius: 12px;


  transition: transform 0.2s, box-shadow 0.2s;


}





.flow-card:hover {


  transform: translateY(-2px);


  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);


}


</style>


