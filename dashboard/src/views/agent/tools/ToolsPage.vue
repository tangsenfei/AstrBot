<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-tools" class="mr-2" />


            {{ $t('agent.tools.title') }}


            <v-spacer />


            <v-btn color="primary" @click="openAddEditor" class="mr-2">


              <v-icon start icon="mdi-plus" />


              {{ $t('agent.tools.buttons.add') }}


            </v-btn>


            <v-btn variant="outlined" @click="loadTools" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.tools.buttons.refresh') }}


            </v-btn>


            <v-menu>


              <template v-slot:activator="{ props }">


                <v-btn variant="outlined" v-bind="props">


                  <v-icon start icon="mdi-dots-vertical" />


                  {{ $t('agent.tools.buttons.more') }}


                </v-btn>


              </template>


              <v-list>


                <v-list-item @click="importTools">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-import" />


                  </template>


                  <v-list-item-title>{{ $t('agent.tools.buttons.import') }}</v-list-item-title>


                </v-list-item>


                <v-list-item @click="exportTools">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-export" />


                  </template>


                  <v-list-item-title>{{ $t('agent.tools.buttons.export') }}</v-list-item-title>


                </v-list-item>


              </v-list>


            </v-menu>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.tools.subtitle') }}


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


                  <v-tab value="all">{{ $t('agent.tools.tabs.all') }}</v-tab>


                  <v-tab value="builtin">{{ $t('agent.tools.tabs.builtin') }}</v-tab>


                  <v-tab value="mcp">{{ $t('agent.tools.tabs.mcp') }}</v-tab>


                  <v-tab value="custom">{{ $t('agent.tools.tabs.custom') }}</v-tab>


                  <v-tab value="api_wrapper">{{ $t('agent.tools.tabs.apiWrapper') }}</v-tab>


                </v-tabs>


              </v-col>


              <v-col cols="12" md="4">


                <v-text-field


                  v-model="searchQuery"


                  :placeholder="$t('agent.tools.search.placeholder')"


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





    <!-- 工具列表 -->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-card-text v-if="loading" class="text-center py-8">


            <v-progress-circular indeterminate color="primary" />


            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


          </v-card-text>





          <v-card-text v-else-if="filteredTools.length === 0" class="text-center py-8">


            <v-icon icon="mdi-tools" size="60" color="grey-lighten-1" class="mb-4" />


            <p class="text-grey">{{ $t('agent.tools.empty') }}</p>


          </v-card-text>





          <v-container fluid v-else>


            <v-row>


              <v-col


                v-for="tool in filteredTools"


                :key="tool.name"


                cols="12"


                sm="6"


                md="4"


                lg="3"


              >


                <ToolCard


                  :tool="tool"


                  @edit="openEditor"


                  @test="openTester"


                  @delete="deleteTool"


                  @toggle="toggleTool"


                />


              </v-col>


            </v-row>


          </v-container>


        </v-card>


      </v-col>


    </v-row>





    <!-- 工具编辑器-->


    <ToolEditor


      v-model="showEditor"


      :tool="editingTool"


      :is-editing="isEditing"


      @save="handleSaveTool"


    />





    <!-- 工具测试器-->


    <ToolTester


      v-model="showTester"


      :tool="testingTool"


    />





    <!-- 导入对话框-->


    <v-dialog v-model="showImportDialog" max-width="600">


      <v-card>


        <v-card-title>{{ $t('agent.tools.import.title') }}</v-card-title>


        <v-card-text>


          <v-file-input


            v-model="importFile"


            :label="$t('agent.tools.import.selectFile')"


            accept=".json"


            prepend-icon="mdi-file-json"


            show-size


          />


          <v-alert type="info" variant="tonal" class="mt-4">


            {{ $t('agent.tools.import.hint') }}


          </v-alert>


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">


            {{ $t('agent.tools.import.button') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.tools.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.tools.delete.confirm', { name: deletingTool?.name }) }}


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


import ToolCard from './ToolCard.vue';


import ToolEditor from './ToolEditor.vue';


import ToolTester from './ToolTester.vue';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();





// 状


const loading = ref(false);


const tools = ref<any[]>([]);


const activeTab = ref('all');


const searchQuery = ref('');





// 编辑


const showEditor = ref(false);


const editingTool = ref<any>(null);


const isEditing = ref(false);





// 测试


const showTester = ref(false);


const testingTool = ref<any>(null);





// 删除


const showDeleteDialog = ref(false);


const deletingTool = ref<any>(null);


const deleting = ref(false);





// 导入


const showImportDialog = ref(false);


const importFile = ref<File | null>(null);


const importing = ref(false);





// 计算属性


const filteredTools = computed(() => {


  let result = tools.value;





  // 按来源筛选


  if (activeTab.value !== 'all') {


    result = result.filter(tool => tool.source === activeTab.value);


  }





  // 按搜索词筛选


  if (searchQuery.value) {


    const query = searchQuery.value.toLowerCase();


    result = result.filter(tool =>


      tool.name.toLowerCase().includes(query) ||


      (tool.description && tool.description.toLowerCase().includes(query))


    );


  }





  return result;


});





// 加载工具列表


async function loadTools() {


  loading.value = true;


  try {


    const response = await axios.get('/api/plug/agent/tools');


    if (response.data.status === 'ok') {


      tools.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load tools:', error);


  } finally {


    loading.value = false;


  }


}





// 打开添加编辑器


function openAddEditor() {


  editingTool.value = null;


  isEditing.value = false;


  showEditor.value = true;


}





// 打开编辑器


function openEditor(tool: any) {


  editingTool.value = { ...tool };


  isEditing.value = true;


  showEditor.value = true;


}





// 打开测试器


function openTester(tool: any) {


  testingTool.value = tool;


  showTester.value = true;


}





// 删除工具


function deleteTool(tool: any) {


  deletingTool.value = tool;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingTool.value) return;





  deleting.value = true;


  try {


    await axios.post('/api/plug/agent/tools/delete', {


      name: deletingTool.value.name,


    });


    tools.value = tools.value.filter(t => t.name !== deletingTool.value.name);


    showDeleteDialog.value = false;


    deletingTool.value = null;


  } catch (error: any) {


    console.error('Failed to delete tool:', error);


    alert(error.response?.data?.message || t('agent.tools.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 切换工具状态


async function toggleTool(tool: any) {


  try {


    await axios.post('/api/plug/agent/tools/toggle', {


      name: tool.name,


      enabled: tool.enabled,


    });


  } catch (error) {


    console.error('Failed to toggle tool:', error);


    tool.enabled = !tool.enabled;


  }


}





// 保存工具


async function handleSaveTool(toolData: any) {


  try {


    if (isEditing.value) {


      await axios.post('/api/plug/agent/tools/update', toolData);


    } else {


      await axios.post('/api/plug/agent/tools/add', toolData);


    }


    showEditor.value = false;


    await loadTools();


  } catch (error: any) {


    console.error('Failed to save tool:', error);


    throw error;


  }


}





// 导入工具


function importTools() {


  importFile.value = null;


  showImportDialog.value = true;


}





async function executeImport() {


  if (!importFile.value) return;





  importing.value = true;


  try {


    const text = await importFile.value.text();


    const data = JSON.parse(text);





    await axios.post('/api/plug/agent/tools/import', { tools: data });


    showImportDialog.value = false;


    await loadTools();


  } catch (error: any) {


    console.error('Failed to import tools:', error);


    alert(error.response?.data?.message || t('agent.tools.messages.importError'));


  } finally {


    importing.value = false;


  }


}





// 导出工具


function exportTools() {


  const data = JSON.stringify(tools.value, null, 2);


  const blob = new Blob([data], { type: 'application/json' });


  const url = URL.createObjectURL(blob);


  const a = document.createElement('a');


  a.href = url;


  a.download = `tools_${new Date().toISOString().slice(0, 10)}.json`;


  a.click();


  URL.revokeObjectURL(url);


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


