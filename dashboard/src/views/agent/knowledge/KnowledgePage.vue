<template>


  <v-container fluid class="pa-6">


    <!-- 页面标题 -->


    <v-row>


      <v-col cols="12">


        <v-card class="mb-6">


          <v-card-title class="d-flex align-center">


            <v-icon icon="mdi-database" class="mr-2" />


            {{ $t('agent.knowledge.title') }}


            <v-spacer />


            <v-btn color="primary" @click="openAddEditor" class="mr-2">


              <v-icon start icon="mdi-plus" />


              {{ $t('agent.knowledge.buttons.add') }}


            </v-btn>


            <v-btn variant="outlined" @click="loadKnowledgeBases" :loading="loading" class="mr-2">


              <v-icon start icon="mdi-refresh" />


              {{ $t('agent.knowledge.buttons.refresh') }}


            </v-btn>


          </v-card-title>


          <v-card-subtitle>


            {{ $t('agent.knowledge.subtitle') }}


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


              <v-col cols="12" md="6">


                <v-text-field


                  v-model="searchQuery"


                  :placeholder="$t('agent.knowledge.search.placeholder')"


                  prepend-inner-icon="mdi-magnify"


                  variant="outlined"


                  density="compact"


                  hide-details


                  clearable


                />


              </v-col>


              <v-col cols="12" md="6" class="d-flex justify-end">


                <v-chip color="info" variant="outlined">


                  <v-icon start icon="mdi-counter" />


                  {{ $t('agent.knowledge.stats.total', { count: filteredKnowledgeBases.length }) }}


                </v-chip>


              </v-col>


            </v-row>


          </v-card-text>


        </v-card>


      </v-col>


    </v-row>





    <!-- 知识库列-->


    <v-row>


      <v-col cols="12">


        <v-card>


          <v-card-text v-if="loading" class="text-center py-8">


            <v-progress-circular indeterminate color="primary" />


            <p class="mt-4 text-grey">{{ $t('common.loading') }}</p>


          </v-card-text>





          <v-card-text v-else-if="filteredKnowledgeBases.length === 0" class="text-center py-8">


            <v-icon icon="mdi-database-off" size="60" color="grey-lighten-1" class="mb-4" />


            <p class="text-grey">{{ $t('agent.knowledge.empty') }}</p>


          </v-card-text>





          <v-container fluid v-else>


            <v-row>


              <v-col


                v-for="kb in filteredKnowledgeBases"


                :key="kb.id"


                cols="12"


                sm="6"


                md="4"


                lg="3"


              >


                <KnowledgeCard


                  :knowledge-base="kb"


                  @edit="openEditor"


                  @add-source="openSourceEditor"


                  @test="openRetrievalTest"


                  @delete="deleteKnowledgeBase"


                />


              </v-col>


            </v-row>


          </v-container>


        </v-card>


      </v-col>


    </v-row>





    <!-- 知识库编辑器 -->


    <KnowledgeEditor


      v-model="showEditor"


      :knowledge-base="editingKnowledgeBase"


      :is-editing="isEditing"


      @save="handleSave"


    />





    <!-- 检索测试对话框 -->


    <v-dialog v-model="showRetrievalTest" max-width="800">


      <v-card>


        <v-card-title class="d-flex align-center">


          <v-icon icon="mdi-magnify" class="mr-2" />


          {{ $t('agent.knowledge.retrieval.title') }}


          <v-spacer />


          <v-btn icon variant="text" @click="showRetrievalTest = false">


            <v-icon icon="mdi-close" />


          </v-btn>


        </v-card-title>


        <v-card-text>


          <v-text-field


            v-model="retrievalQuery"


            :label="$t('agent.knowledge.retrieval.query')"


            :placeholder="$t('agent.knowledge.retrieval.queryPlaceholder')"


            prepend-inner-icon="mdi-magnify"


            variant="outlined"


            class="mb-4"


            @keyup.enter="executeRetrieval"


          />


          <v-slider


            v-model="retrievalTopK"


            :label="$t('agent.knowledge.retrieval.topK')"


            :min="1"


            :max="20"


            :step="1"


            thumb-label


            class="mb-4"


          />


          <v-btn


            color="primary"


            @click="executeRetrieval"


            :loading="retrieving"


            :disabled="!retrievalQuery"


          >


            <v-icon start icon="mdi-search" />


            {{ $t('agent.knowledge.retrieval.search') }}


          </v-btn>





          <!-- 检索结-->


          <div v-if="retrievalResults.length > 0" class="mt-6">


            <div class="text-subtitle-1 font-weight-medium mb-3">


              {{ $t('agent.knowledge.retrieval.results') }}


            </div>


            <v-list>


              <v-list-item


                v-for="(result, index) in retrievalResults"


                :key="index"


                class="mb-2"


              >


                <v-card variant="outlined" class="w-100">


                  <v-card-text>


                    <div class="d-flex align-center mb-2">


                      <v-chip size="x-small" color="primary" class="mr-2">


                        {{ $t('agent.knowledge.retrieval.score') }}: {{ result.score?.toFixed(4) }}


                      </v-chip>


                      <v-chip size="x-small" variant="outlined">


                        {{ result.source_type }}


                      </v-chip>


                    </div>


                    <p class="text-body-2">{{ result.content }}</p>


                    <div v-if="result.metadata" class="text-caption text-grey mt-2">


                      {{ JSON.stringify(result.metadata) }}


                    </div>


                  </v-card-text>


                </v-card>


              </v-list-item>


            </v-list>


          </div>


          <v-alert


            v-else-if="retrievalExecuted && retrievalResults.length === 0"


            type="info"


            variant="tonal"


            class="mt-4"


          >


            {{ $t('agent.knowledge.retrieval.noResults') }}


          </v-alert>


        </v-card-text>


      </v-card>


    </v-dialog>





    <!-- 确认删除对话框-->


    <v-dialog v-model="showDeleteDialog" max-width="400">


      <v-card>


        <v-card-title>{{ $t('agent.knowledge.delete.title') }}</v-card-title>


        <v-card-text>


          {{ $t('agent.knowledge.delete.confirm', { name: deletingKnowledgeBase?.name }) }}


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


import KnowledgeCard from './KnowledgeCard.vue';


import KnowledgeEditor from './KnowledgeEditor.vue';


import { useI18n } from 'vue-i18n';





const { t } = useI18n();





// 状


const loading = ref(false);


const knowledgeBases = ref<any[]>([]);


const searchQuery = ref('');





// 编辑


const showEditor = ref(false);


const editingKnowledgeBase = ref<any>(null);


const isEditing = ref(false);





// 删除


const showDeleteDialog = ref(false);


const deletingKnowledgeBase = ref<any>(null);


const deleting = ref(false);





// 检索测


const showRetrievalTest = ref(false);


const testingKnowledgeBase = ref<any>(null);


const retrievalQuery = ref('');


const retrievalTopK = ref(5);


const retrievalResults = ref<any[]>([]);


const retrieving = ref(false);


const retrievalExecuted = ref(false);





// 计算属性


const filteredKnowledgeBases = computed(() => {


  if (!searchQuery.value) return knowledgeBases.value;





  const query = searchQuery.value.toLowerCase();


  return knowledgeBases.value.filter(kb =>


    kb.name.toLowerCase().includes(query) ||


    (kb.description && kb.description.toLowerCase().includes(query))


  );


});





// 加载知识库列


async function loadKnowledgeBases() {


  loading.value = true;


  try {


    const response = await axios.get('/api/plug/agent/knowledge');


    if (response.data.status === 'ok') {


      knowledgeBases.value = response.data.data || [];


    }


  } catch (error) {


    console.error('Failed to load knowledge bases:', error);


  } finally {


    loading.value = false;


  }


}





// 打开添加编辑器


function openAddEditor() {


  editingKnowledgeBase.value = null;


  isEditing.value = false;


  showEditor.value = true;


}





// 打开编辑器


function openEditor(kb: any) {


  editingKnowledgeBase.value = { ...kb };


  isEditing.value = true;


  showEditor.value = true;


}





// 打开知识源编辑器


function openSourceEditor(kb: any) {


  editingKnowledgeBase.value = { ...kb };


  isEditing.value = true;


  showEditor.value = true;


}





// 打开检索测


function openRetrievalTest(kb: any) {


  testingKnowledgeBase.value = kb;


  retrievalQuery.value = '';


  retrievalTopK.value = 5;


  retrievalResults.value = [];


  retrievalExecuted.value = false;


  showRetrievalTest.value = true;


}





// 执行检


async function executeRetrieval() {


  if (!testingKnowledgeBase.value || !retrievalQuery.value) return;





  retrieving.value = true;


  retrievalExecuted.value = true;


  try {


    const response = await axios.post('/api/plug/agent/knowledge/retrieve', {


      knowledge_base_id: testingKnowledgeBase.value.id,


      query: retrievalQuery.value,


      top_k: retrievalTopK.value,


    });


    if (response.data.status === 'ok') {


      retrievalResults.value = response.data.data || [];


    }


  } catch (error: any) {


    console.error('Failed to retrieve:', error);


    alert(error.response?.data?.message || t('agent.knowledge.messages.retrievalError'));


  } finally {


    retrieving.value = false;


  }


}





// 删除知识


function deleteKnowledgeBase(kb: any) {


  deletingKnowledgeBase.value = kb;


  showDeleteDialog.value = true;


}





// 确认删除


async function confirmDelete() {


  if (!deletingKnowledgeBase.value) return;





  deleting.value = true;


  try {


    await axios.post('/api/plug/agent/knowledge/delete', {


      id: deletingKnowledgeBase.value.id,


    });


    knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== deletingKnowledgeBase.value.id);


    showDeleteDialog.value = false;


    deletingKnowledgeBase.value = null;


  } catch (error: any) {


    console.error('Failed to delete knowledge base:', error);


    alert(error.response?.data?.message || t('agent.knowledge.messages.deleteError'));


  } finally {


    deleting.value = false;


  }


}





// 保存知识


async function handleSave(kbData: any) {


  try {


    if (isEditing.value) {


      await axios.post('/api/plug/agent/knowledge/update', kbData);


    } else {


      await axios.post('/api/plug/agent/knowledge/create', kbData);


    }


    showEditor.value = false;


    await loadKnowledgeBases();


  } catch (error: any) {


    console.error('Failed to save knowledge base:', error);


    throw error;


  }


}





onMounted(() => {


  loadKnowledgeBases();


});


</script>





<style scoped>


.v-card {


  border-radius: 12px;


}


</style>


