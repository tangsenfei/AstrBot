<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-lightning-bolt" class="mr-2" />


            {{ $t('agent.skills.title') }}


            <v-spacer />


            <v-btn color="primary" @click="openAddEditor" class="mr-2">


              <v-icon start icon="mdi-plus" />


              {{ $t('agent.skills.buttons.add') }}


            </v-btn>


            <v-btn variant="outlined" @click="loadSkills" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.skills.buttons.refresh') }}


            </v-btn>


            <v-menu>


              <template v-slot:activator="{ props }">


                <v-btn variant="outlined" v-bind="props" class="mr-2">


                  <v-icon start icon="mdi-dots-vertical" />


                  {{ $t('agent.skills.buttons.more') }}


                </v-btn>


              </template>


              <v-list>


                <v-list-item @click="importSkills">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-import" />


                  </template>


                  <v-list-item-title>{{ $t('agent.skills.buttons.import') }}</v-list-item-title>


                </v-list-item>


                <v-list-item @click="exportSkills">


                  <template v-slot:prepend>


                    <v-icon icon="mdi-export" />


                  </template>


                  <v-list-item-title>{{ $t('agent.skills.buttons.export') }}</v-list-item-title>


                </v-list-item>


              </v-list>


            </v-menu>


            <v-btn variant="outlined" color="secondary" @click="openMarket">


              <v-icon start icon="mdi-store" />


              {{ $t('agent.skills.buttons.market') }}


            </v-btn>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.skills.subtitle') }}


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


                  <v-tab value="all">{{ $t('agent.skills.tabs.all') }}</v-tab>


                  <v-tab value="general">{{ $t('agent.skills.tabs.general') }}</v-tab>


                  <v-tab value="programming">{{ $t('agent.skills.tabs.programming') }}</v-tab>


                  <v-tab value="analysis">{{ $t('agent.skills.tabs.analysis') }}</v-tab>


                  <v-tab value="creative">{{ $t('agent.skills.tabs.creative') }}</v-tab>


                  <v-tab value="other">{{ $t('agent.skills.tabs.other') }}</v-tab>


                </v-tabs>


              </v-col>


              <v-col cols="12" md="4">


                <v-text-field


                  v-model="searchQuery"


                  :placeholder="$t('agent.skills.search.placeholder')"


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





    <!-- 技能列-->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-card-text v-if="loading" class="text-center py-8">


            <v-progress-circular indeterminate color="primary" />


            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


          </v-card-text>





          <v-card-text v-else-if="filteredSkills.length === 0" class="text-center py-8">


            <v-icon icon="mdi-lightning-bolt" size="60" color="grey-lighten-1" class="mb-4" />


            <p class="text-grey">{{ $t('agent.skills.empty') }}</p>


          </v-card-text>





          <v-container fluid v-else>


            <v-row>


              <v-col


                v-for="skill in filteredSkills"


                :key="skill.name"


                cols="12"


                sm="6"


                md="4"


                lg="3"


              >


                <SkillCard


                  :skill="skill"


                  @edit="openEditor"


                  @test="openTester"


                  @delete="deleteSkill"


                />


              </v-col>


            </v-row>


          </v-container>


        </v-card>


      </v-col>


    </v-row>





    <!-- 技能编辑器 -->


    <SkillEditor


      v-model="showEditor"


      :skill="editingSkill"


      :is-editing="isEditing"


      :tools="availableTools"


      @save="handleSaveSkill"


    />





    <!-- 技能测试器 -->


    <v-dialog v-model="showTester" max-width="800">


      <v-card>


        <v-card-title class="d-flex align-center">


          <v-icon icon="mdi-bug-play" class="mr-2" />


          {{ $t('agent.skills.card.test') }}: {{ testingSkill?.name }}


          <v-spacer />


          <v-btn icon variant="text" @click="showTester = false">


            <v-icon icon="mdi-close" />


          </v-btn>


        </v-card-title>


        <v-divider />


        <v-card-text class="pa-4">


          <v-alert type="info" variant="tonal" class="mb-4">


            {{ $t('agent.skills.card.test') }}功能开发中...


          </v-alert>


        </v-card-text>


      </v-card>


    </v-dialog>





    <!-- 导入对话框-->


    <v-dialog v-model="showImportDialog" max-width="600">


      <v-card>


        <v-card-title>{{ $t('agent.skills.import.title') }}</v-card-title>


        <v-card-text>


          <v-file-input


            v-model="importFile"


            :label="$t('agent.skills.import.selectFile')"


            accept=".json"


            prepend-icon="mdi-file-json"


            show-size


          />


          <v-alert type="info" variant="tonal" class="mt-4">


            {{ $t('agent.skills.import.hint') }}


          </v-alert>


        </v-card-text>


        <v-card-actions>


          <v-spacer />


          <v-btn @click="showImportDialog = false">{{ $t('common.cancel') }}</v-btn>


          <v-btn color="primary" @click="executeImport" :loading="importing" :disabled="!importFile">


            {{ $t('agent.skills.import.button') }}


          </v-btn>


        </v-card-actions>


      </v-card>


    </v-dialog>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.skills.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.skills.delete.confirm', { name: deletingSkill?.name }) }}


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


import SkillCard from './SkillCard.vue';


import SkillEditor from './SkillEditor.vue';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();





// 状


const loading = ref(false);


const skills = ref<any[]>([]);


const availableTools = ref<any[]>([]);


const activeTab = ref('all');


const searchQuery = ref('');





// 编辑


const showEditor = ref(false);


const editingSkill = ref<any>(null);


const isEditing = ref(false);





// 测试


const showTester = ref(false);


const testingSkill = ref<any>(null);





// 删除


const showDeleteDialog = ref(false);


const deletingSkill = ref<any>(null);


const deleting = ref(false);





// 导入


const showImportDialog = ref(false);


const importFile = ref<File | null>(null);


const importing = ref(false);





// 计算属性


const filteredSkills = computed(() => {


  let result = skills.value;





  // 按分类筛


  if (activeTab.value !== 'all') {


    result = result.filter(skill => skill.category === activeTab.value);


  }





  // 按搜索词筛选


  if (searchQuery.value) {


    const query = searchQuery.value.toLowerCase();


    result = result.filter(skill =>


      skill.name.toLowerCase().includes(query) ||


      (skill.description && skill.description.toLowerCase().includes(query))


    );


  }





  return result;


});





// 加载技能列


async function loadSkills() {


  loading.value = true;


  try {


    const response = await axios.get('/api/plug/agent/skills');


    if (response.data.status === 'ok') {


      skills.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load skills:', error);


  } finally {


    loading.value = false;


  }


}





// 加载可用工具列表


async function loadAvailableTools() {


  try {


    const response = await axios.get('/api/plug/agent/tools');


    if (response.data.status === 'ok') {


      availableTools.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load tools:', error);


  }


}





// 打开添加编辑器


function openAddEditor() {


  editingSkill.value = null;


  isEditing.value = false;


  showEditor.value = true;


}





// 打开编辑器


function openEditor(skill: any) {


  editingSkill.value = { ...skill };


  isEditing.value = true;


  showEditor.value = true;


}





// 打开测试器


function openTester(skill: any) {


  testingSkill.value = skill;


  showTester.value = true;


}





// 删除技


function deleteSkill(skill: any) {


  deletingSkill.value = skill;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingSkill.value) return;





  deleting.value = true;


  try {


    await axios.post('/api/plug/agent/skills/delete', {


      name: deletingSkill.value.name,


    });


    skills.value = skills.value.filter(s => s.name !== deletingSkill.value.name);


    showDeleteDialog.value = false;


    deletingSkill.value = null;


  } catch (error: any) {


    console.error('Failed to delete skill:', error);


    alert(error.response?.data?.message || t('agent.skills.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 保存技


async function handleSaveSkill(skillData: any) {


  try {


    if (isEditing.value) {


      await axios.post('/api/plug/agent/skills/update', skillData);


    } else {


      await axios.post('/api/plug/agent/skills/add', skillData);


    }


    showEditor.value = false;


    await loadSkills();


  } catch (error: any) {


    console.error('Failed to save skill:', error);


    throw error;


  }


}





// 导入技


function importSkills() {


  importFile.value = null;


  showImportDialog.value = true;


}





async function executeImport() {


  if (!importFile.value) return;





  importing.value = true;


  try {


    const text = await importFile.value.text();


    const data = JSON.parse(text);





    await axios.post('/api/plug/agent/skills/import', { skills: data });


    showImportDialog.value = false;


    await loadSkills();


  } catch (error: any) {


    console.error('Failed to import skills:', error);


    alert(error.response?.data?.message || t('agent.skills.messages.importError'));


  } finally {


    importing.value = false;


  }


}





// 导出技


function exportSkills() {


  const data = JSON.stringify(skills.value, null, 2);


  const blob = new Blob([data], { type: 'application/json' });


  const url = URL.createObjectURL(blob);


  const a = document.createElement('a');


  a.href = url;


  a.download = `skills_${new Date().toISOString().slice(0, 10)}.json`;


  a.click();


  URL.revokeObjectURL(url);


}





// 打开技能市


function openMarket() {


  // TODO: 实现技能市场功


  alert('技能市场功能开发中...');


}





onMounted(() => {


  loadSkills();


  loadAvailableTools();


});


</script>





<style scoped>


.v-card {


  border-radius: 12px;


}


</style>


