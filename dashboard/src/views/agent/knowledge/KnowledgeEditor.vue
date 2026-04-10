<template>

  <v-navigation-drawer

    :model-value="modelValue"

    @update:model-value="$emit('update:modelValue', $event)"

    location="right"

    temporary

    width="700"

    class="knowledge-editor-drawer"

  >

    <v-card flat class="h-100 d-flex flex-column">

      <!-- 标题 -->

      <v-card-title class="d-flex align-center pa-4 border-b">

        <v-icon icon="mdi-database-edit" class="mr-2" />

        {{ isEditing ? $t('agent.knowledge.editor.editTitle') : $t('agent.knowledge.editor.addTitle') }}

        <v-spacer />

        <v-btn icon variant="text" @click="$emit('update:modelValue', false)">

          <v-icon icon="mdi-close" />

        </v-btn>

      </v-card-title>



      <!-- 表单内容 -->

      <v-card-text class="flex-grow-1 overflow-y-auto pa-4">

        <v-form ref="formRef" v-model="formValid">

          <!-- 基本信息 -->

          <div class="text-subtitle-1 font-weight-medium mb-3">

            <v-icon icon="mdi-information" class="mr-1" />

            {{ $t('agent.knowledge.editor.basicInfo') }}

          </div>



          <v-text-field

            v-model="formData.name"

            :label="$t('agent.knowledge.editor.name')"

            :rules="[rules.required]"

            :hint="$t('agent.knowledge.editor.nameHint')"

            persistent-hint

            class="mb-3"

          />



          <v-textarea

            v-model="formData.description"

            :label="$t('agent.knowledge.editor.description')"

            :hint="$t('agent.knowledge.editor.descriptionHint')"

            persistent-hint

            rows="2"

            auto-grow

            class="mb-4"

          />



          <v-divider class="my-4" />



          <!-- 嵌入模型配置 -->

          <div class="text-subtitle-1 font-weight-medium mb-3">

            <v-icon icon="mdi-brain" class="mr-1" />

            {{ $t('agent.knowledge.editor.embeddingConfig') }}

          </div>



          <v-row>

            <v-col cols="6">

              <v-select

                v-model="formData.embedding_provider"

                :items="providerOptions"

                :label="$t('agent.knowledge.editor.provider')"

                :rules="[rules.required]"

                :loading="loadingProviders"

                class="mb-3"

                @update:model-value="loadModels"

              />

            </v-col>

            <v-col cols="6">

              <v-select

                v-model="formData.embedding_model"

                :items="modelOptions"

                :label="$t('agent.knowledge.editor.model')"

                :rules="[rules.required]"

                :loading="loadingModels"

                :disabled="!formData.embedding_provider"

                class="mb-3"

              />

            </v-col>

          </v-row>



          <v-text-field

            v-model="formData.collection_name"

            :label="$t('agent.knowledge.editor.collectionName')"

            :hint="$t('agent.knowledge.editor.collectionNameHint')"

            persistent-hint

            :disabled="isEditing"

            class="mb-4"

          >

            <template v-slot:append-inner>

              <v-btn

                variant="text"

                size="small"

                @click="generateCollectionName"

                :disabled="isEditing"

              >

                <v-icon icon="mdi-auto-fix" />

              </v-btn>

            </template>

          </v-text-field>



          <v-divider class="my-4" />



          <!-- 知识源管-->

          <div class="text-subtitle-1 font-weight-medium mb-3">

            <v-icon icon="mdi-source-branch" class="mr-1" />

            {{ $t('agent.knowledge.editor.knowledgeSources') }}

          </div>



          <v-tabs v-model="sourceTab" color="primary" class="mb-3">

            <v-tab value="text">

              <v-icon start icon="mdi-text" />

              {{ $t('agent.knowledge.sources.text') }}

            </v-tab>

            <v-tab value="file">

              <v-icon start icon="mdi-file" />

              {{ $t('agent.knowledge.sources.file') }}

            </v-tab>

            <v-tab value="url">

              <v-icon start icon="mdi-link" />

              {{ $t('agent.knowledge.sources.url') }}

            </v-tab>

            <v-tab value="database">

              <v-icon start icon="mdi-database" />

              {{ $t('agent.knowledge.sources.database') }}

            </v-tab>

          </v-tabs>



          <!-- 文本知识 -->

          <v-window v-model="sourceTab">

            <v-window-item value="text">

              <v-textarea

                v-model="textSource.content"

                :label="$t('agent.knowledge.editor.textContent')"

                :placeholder="$t('agent.knowledge.editor.textContentPlaceholder')"

                rows="6"

                auto-grow

                class="mb-3"

              />

              <v-btn

                color="primary"

                @click="addTextSource"

                :disabled="!textSource.content"

              >

                <v-icon start icon="mdi-plus" />

                {{ $t('agent.knowledge.editor.addTextSource') }}

              </v-btn>

            </v-window-item>



            <!-- 文件知识 -->

            <v-window-item value="file">

              <v-file-input

                v-model="fileSource.files"

                :label="$t('agent.knowledge.editor.selectFiles')"

                accept=".pdf,.md,.txt,.doc,.docx"

                multiple

                show-size

                prepend-icon="mdi-paperclip"

                class="mb-3"

              />

              <v-alert type="info" variant="tonal" density="compact" class="mb-3">

                {{ $t('agent.knowledge.editor.fileHint') }}

              </v-alert>

              <v-btn

                color="primary"

                @click="addFileSource"

                :disabled="!fileSource.files?.length"

                :loading="uploadingFiles"

              >

                <v-icon start icon="mdi-upload" />

                {{ $t('agent.knowledge.editor.uploadFiles') }}

              </v-btn>

            </v-window-item>



            <!-- URL 知识 -->

            <v-window-item value="url">

              <v-text-field

                v-model="urlSource.url"

                :label="$t('agent.knowledge.editor.url')"

                :placeholder="$t('agent.knowledge.editor.urlPlaceholder')"

                prepend-inner-icon="mdi-link"

                class="mb-3"

              />

              <v-text-field

                v-model="urlSource.selector"

                :label="$t('agent.knowledge.editor.selector')"

                :placeholder="$t('agent.knowledge.editor.selectorPlaceholder')"

                :hint="$t('agent.knowledge.editor.selectorHint')"

                persistent-hint

                class="mb-3"

              />

              <v-btn

                color="primary"

                @click="addUrlSource"

                :disabled="!urlSource.url"

                :loading="fetchingUrl"

              >

                <v-icon start icon="mdi-download" />

                {{ $t('agent.knowledge.editor.fetchUrl') }}

              </v-btn>

            </v-window-item>



            <!-- 数据库知-->

            <v-window-item value="database">

              <v-select

                v-model="databaseSource.db_type"

                :items="dbTypeOptions"

                :label="$t('agent.knowledge.editor.dbType')"

                class="mb-3"

              />

              <v-text-field

                v-model="databaseSource.connection_string"

                :label="$t('agent.knowledge.editor.connectionString')"

                :placeholder="$t('agent.knowledge.editor.connectionStringPlaceholder')"

                class="mb-3"

              />

              <v-text-field

                v-model="databaseSource.query"

                :label="$t('agent.knowledge.editor.query')"

                :placeholder="$t('agent.knowledge.editor.queryPlaceholder')"

                class="mb-3"

              />

              <v-btn

                color="primary"

                @click="addDatabaseSource"

                :disabled="!databaseSource.connection_string || !databaseSource.query"

                :loading="connectingDb"

              >

                <v-icon start icon="mdi-database-import" />

                {{ $t('agent.knowledge.editor.importFromDb') }}

              </v-btn>

            </v-window-item>

          </v-window>



          <!-- 已添加的知识源列-->

          <div v-if="formData.sources && formData.sources.length > 0" class="mt-4">

            <div class="text-subtitle-2 mb-2">{{ $t('agent.knowledge.editor.addedSources') }}</div>

            <v-list density="compact">

              <v-list-item

                v-for="(source, index) in formData.sources"

                :key="index"

                class="px-2"

              >

                <template v-slot:prepend>

                  <v-icon :icon="getSourceIcon(source.type)" />

                </template>

                <v-list-item-title>{{ source.name || source.type }}</v-list-item-title>

                <v-list-item-subtitle v-if="source.content">

                  {{ source.content.substring(0, 50) }}...

                </v-list-item-subtitle>

                <template v-slot:append>

                  <v-btn

                    icon

                    size="small"

                    variant="text"

                    color="error"

                    @click="removeSource(index)"

                  >

                    <v-icon icon="mdi-close" />

                  </v-btn>

                </template>

              </v-list-item>

            </v-list>

          </div>

        </v-form>

      </v-card-text>



      <!-- 操作按钮 -->

      <v-card-actions class="pa-4 border-t">

        <v-spacer />

        <v-btn variant="outlined" @click="$emit('update:modelValue', false)">

          {{ $t('common.cancel') }}

        </v-btn>

        <v-btn

          color="primary"

          @click="handleSave"

          :loading="saving"

          :disabled="!formValid"

        >

          {{ $t('common.save') }}

        </v-btn>

      </v-card-actions>

    </v-card>

  </v-navigation-drawer>

</template>



<script setup lang="ts">

import { ref, computed, watch, onMounted } from 'vue';

import { useI18n } from 'vue-i18n';

import axios from 'axios';



const props = defineProps<{

  modelValue: boolean;

  knowledgeBase: any;

  isEditing: boolean;

}>();



const emit = defineEmits<{

  (e: 'update:modelValue', value: boolean): void;

  (e: 'save', data: any): void;

}>();



const { t } = useI18n();



// 状

const formRef = ref();

const formValid = ref(false);

const saving = ref(false);

const sourceTab = ref('text');



// 提供商和模型

const loadingProviders = ref(false);

const loadingModels = ref(false);

const providers = ref<any[]>([]);

const models = ref<any[]>([]);



// 文件上传

const uploadingFiles = ref(false);

const fetchingUrl = ref(false);

const connectingDb = ref(false);



// 表单数据

const formData = ref({

  name: '',

  description: '',

  embedding_provider: '',

  embedding_model: '',

  collection_name: '',

  sources: [] as any[],

});



// 文本知识

const textSource = ref({

  content: '',

});



// 文件知识

const fileSource = ref({

  files: [] as File[],

});



// URL 知识

const urlSource = ref({

  url: '',

  selector: '',

});



// 数据库知识源

const databaseSource = ref({

  db_type: 'postgresql',

  connection_string: '',

  query: '',

});



// 验证规则

const rules = {

  required: (v: string) => !!v || t('agent.knowledge.editor.validation.required'),

};



// 提供商选项

const providerOptions = computed(() =>

  providers.value.map(p => ({

    title: p.name || p.id,

    value: p.id,

  }))

);



// 模型选项

const modelOptions = computed(() =>

  models.value.map(m => ({

    title: m.name || m.id,

    value: m.id,

  }))

);



// 数据库类型选项

const dbTypeOptions = computed(() => [

  { title: 'PostgreSQL', value: 'postgresql' },

  { title: 'MySQL', value: 'mysql' },

  { title: 'SQLite', value: 'sqlite' },

  { title: 'MongoDB', value: 'mongodb' },

]);



// 加载提供

async function loadProviders() {

  loadingProviders.value = true;

  try {

    const response = await axios.get('/api/config/provider/list', {

      params: { provider_type: 'embedding' }

    });

    if (response.data.status === 'ok') {

      providers.value = (response.data.data || [])

        .filter((provider: any) => provider.enable !== false);

    }

  } catch (error) {

    console.error('Failed to load providers:', error);

  } finally {

    loadingProviders.value = false;

  }

}



// 加载模型

async function loadModels(providerId: string) {

  if (!providerId) {

    models.value = [];

    return;

  }



  loadingModels.value = true;

  try {

    // 从已加载的提供商列表中获取模型信

    const provider = providers.value.find((p: any) => p.id === providerId);

    if (provider && provider.model) {

      models.value = [{

        id: provider.model,

        name: provider.model,

      }];

    } else {

      models.value = [];

    }

  } catch (error) {

    console.error('Failed to load models:', error);

  } finally {

    loadingModels.value = false;

  }

}



// 生成集合名称

function generateCollectionName() {

  const timestamp = Date.now().toString(36);

  const random = Math.random().toString(36).substring(2, 6);

  formData.value.collection_name = `kb_${timestamp}_${random}`;

}



// 获取知识源图

function getSourceIcon(type: string) {

  switch (type) {

    case 'text': return 'mdi-text';

    case 'file': return 'mdi-file';

    case 'url': return 'mdi-link';

    case 'database': return 'mdi-database';

    default: return 'mdi-source-branch';

  }

}



// 添加文本知识

function addTextSource() {

  if (!textSource.value.content) return;



  formData.value.sources.push({

    type: 'text',

    name: t('agent.knowledge.sources.text'),

    content: textSource.value.content,

  });



  textSource.value.content = '';

}



// 添加文件知识

async function addFileSource() {

  if (!fileSource.value.files?.length) return;



  uploadingFiles.value = true;

  try {

    const formDataObj = new FormData();

    fileSource.value.files.forEach((file, index) => {

      formDataObj.append(`files`, file);

    });



    const response = await axios.post('/api/plug/agent/knowledge/upload', formDataObj, {

      headers: { 'Content-Type': 'multipart/form-data' },

    });



    if (response.data.status === 'ok') {

      const uploadedFiles = response.data.data || [];

      uploadedFiles.forEach((file: any) => {

        formData.value.sources.push({

          type: 'file',

          name: file.name,

          file_id: file.id,

          file_path: file.path,

        });

      });

      fileSource.value.files = [];

    }

  } catch (error: any) {

    console.error('Failed to upload files:', error);

    alert(error.response?.data?.message || t('agent.knowledge.messages.uploadError'));

  } finally {

    uploadingFiles.value = false;

  }

}



// 添加 URL 知识

async function addUrlSource() {

  if (!urlSource.value.url) return;



  fetchingUrl.value = true;

  try {

    const response = await axios.post('/api/plug/agent/knowledge/fetch-url', {

      url: urlSource.value.url,

      selector: urlSource.value.selector,

    });



    if (response.data.status === 'ok') {

      formData.value.sources.push({

        type: 'url',

        name: urlSource.value.url,

        url: urlSource.value.url,

        content: response.data.data.content,

      });

      urlSource.value.url = '';

      urlSource.value.selector = '';

    }

  } catch (error: any) {

    console.error('Failed to fetch URL:', error);

    alert(error.response?.data?.message || t('agent.knowledge.messages.fetchError'));

  } finally {

    fetchingUrl.value = false;

  }

}



// 添加数据库知识源

async function addDatabaseSource() {

  if (!databaseSource.value.connection_string || !databaseSource.value.query) return;



  connectingDb.value = true;

  try {

    const response = await axios.post('/api/plug/agent/knowledge/import-db', {

      db_type: databaseSource.value.db_type,

      connection_string: databaseSource.value.connection_string,

      query: databaseSource.value.query,

    });



    if (response.data.status === 'ok') {

      formData.value.sources.push({

        type: 'database',

        name: `${databaseSource.value.db_type} - ${t('agent.knowledge.sources.database')}`,

        db_type: databaseSource.value.db_type,

        query: databaseSource.value.query,

        content: response.data.data.content,

      });

      databaseSource.value.connection_string = '';

      databaseSource.value.query = '';

    }

  } catch (error: any) {

    console.error('Failed to import from database:', error);

    alert(error.response?.data?.message || t('agent.knowledge.messages.dbImportError'));

  } finally {

    connectingDb.value = false;

  }

}



// 移除知识

function removeSource(index: number) {

  formData.value.sources.splice(index, 1);

}



// 重置表单

function resetForm() {

  formData.value = {

    name: '',

    description: '',

    embedding_provider: '',

    embedding_model: '',

    collection_name: '',

    sources: [],

  };

  textSource.value.content = '';

  fileSource.value.files = [];

  urlSource.value.url = '';

  urlSource.value.selector = '';

  databaseSource.value.connection_string = '';

  databaseSource.value.query = '';

}



// 监听知识库变

watch(() => props.knowledgeBase, (newKb) => {

  if (newKb) {

    formData.value = {

      name: newKb.name || '',

      description: newKb.description || '',

      embedding_provider: newKb.embedding_provider || '',

      embedding_model: newKb.embedding_model || '',

      collection_name: newKb.collection_name || '',

      sources: newKb.sources || [],

    };



    if (newKb.embedding_provider) {

      loadModels(newKb.embedding_provider);

    }

  } else {

    resetForm();

  }

}, { immediate: true });



// 保存

async function handleSave() {

  const { valid } = await formRef.value?.validate();

  if (!valid) return;



  saving.value = true;

  try {

    const data = {

      id: props.knowledgeBase?.id,

      name: formData.value.name,

      description: formData.value.description,

      embedding_provider: formData.value.embedding_provider,

      embedding_model: formData.value.embedding_model,

      collection_name: formData.value.collection_name,

      sources: formData.value.sources,

    };



    await emit('save', data);

  } finally {

    saving.value = false;

  }

}



onMounted(() => {

  loadProviders();

});

</script>



<style scoped>

.knowledge-editor-drawer {

  z-index: 1000;

}



.knowledge-editor-drawer .v-card {

  border-radius: 0;

}

</style>

