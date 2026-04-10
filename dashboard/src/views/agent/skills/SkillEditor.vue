<template>


  <v-navigation-drawer


    :model-value="modelValue"


    @update:model-value="$emit('update:modelValue', $event)"


    location="right"


    temporary


    width="700"


    class="skill-editor-drawer"


  >


    <v-card flat class="h-100 d-flex flex-column">


      <!-- 标题 -->


      <v-card-title class="d-flex align-center pa-4 border-b">


        <v-icon icon="mdi-lightning-bolt" class="mr-2" />


        {{ isEditing ? $t('agent.skills.editor.editTitle') : $t('agent.skills.editor.addTitle') }}


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


            {{ $t('agent.skills.editor.basicInfo') }}


          </div>





          <v-text-field


            v-model="formData.name"


            :label="$t('agent.skills.editor.name')"


            :rules="[rules.required, rules.nameFormat]"


            :disabled="isEditing"


            :hint="$t('agent.skills.editor.nameHint')"


            persistent-hint


            class="mb-3"


          />





          <v-text-field


            v-model="formData.description"


            :label="$t('agent.skills.editor.description')"


            :rules="[rules.required]"


            :hint="$t('agent.skills.editor.descriptionHint')"


            persistent-hint


            class="mb-3"


          />





          <v-row>


            <v-col cols="6">


              <v-select


                v-model="formData.category"


                :items="categoryOptions"


                :label="$t('agent.skills.editor.category')"


                :rules="[rules.required]"


                :hint="$t('agent.skills.editor.categoryHint')"


                persistent-hint


              />


            </v-col>


            <v-col cols="6">


              <v-text-field


                v-model="formData.version"


                :label="$t('agent.skills.editor.version')"


                :hint="$t('agent.skills.editor.versionHint')"


                persistent-hint


              />


            </v-col>


          </v-row>





          <v-divider class="my-4" />





          <!-- 渐进式披-->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.skills.editor.disclosure') }}


          </div>





          <v-select


            v-model="formData.disclosure_level"


            :items="disclosureOptions"


            :label="$t('agent.skills.editor.disclosureLevel')"


            :rules="[rules.required]"


            :hint="$t('agent.skills.editor.disclosureLevelHint')"


            persistent-hint


            class="mb-4"


          />





          <v-divider class="my-4" />





          <!-- 预批准工-->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.skills.editor.preapprovedTools') }}


          </div>





          <v-alert type="info" variant="tonal" class="mb-3" density="compact">


            {{ $t('agent.skills.editor.preapprovedToolsHint') }}


          </v-alert>





          <v-select


            v-model="formData.preapproved_tools"


            :items="toolOptions"


            :label="$t('agent.skills.editor.preapprovedTools')"


            multiple


            chips


            closable-chips


            class="mb-4"


          />





          <v-divider class="my-4" />





          <!-- 工作流配-->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.skills.editor.workflow') }}


          </div>





          <v-alert type="info" variant="tonal" class="mb-3" density="compact">


            {{ $t('agent.skills.editor.workflowHint') }}


          </v-alert>





          <WorkflowEditor v-model="formData.workflow" :tools="tools" />





          <v-divider class="my-4" />





          <!-- 元数据-->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.skills.editor.metadata') }}


          </div>





          <v-textarea


            v-model="metadataJson"


            :label="$t('agent.skills.editor.metadataJson')"


            :error="metadataError"


            :error-messages="metadataErrorMsg"


            rows="4"


            auto-grow


            class="mb-3"


            @blur="validateMetadata"


          />





          <v-btn


            variant="outlined"


            size="small"


            class="mb-4"


            @click="formatMetadata"


          >


            <v-icon start icon="mdi-format-align-left" />


            {{ $t('agent.skills.editor.formatJson') }}


          </v-btn>





          <v-divider class="my-4" />





          <!-- 标签 -->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.skills.editor.tags') }}


          </div>





          <v-combobox


            v-model="formData.tags"


            :label="$t('agent.skills.editor.tagsLabel')"


            multiple


            chips


            closable-chips


            :hint="$t('agent.skills.editor.tagsHint')"


            persistent-hint


            class="mb-4"


          />


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


import { ref, computed, watch } from 'vue';


import { useI18n } from 'vue-i18n';


import WorkflowEditor from './WorkflowEditor.vue';





const props = defineProps<{


  modelValue: boolean;


  skill: any;


  isEditing: boolean;


  tools: any[];


}>();





const emit = defineEmits<{


  (e: 'update:modelValue', value: boolean): void;


  (e: 'save', skillData: any): void;


}>();





const { t } = useI18n();





// 状


const formRef = ref();


const formValid = ref(false);


const saving = ref(false);





// 表单数据


const formData = ref({


  name: '',


  description: '',


  category: 'general',


  version: '1.0.0',


  disclosure_level: 'metadata',


  preapproved_tools: [] as string[],


  workflow: {


    steps: [] as any[]


  },


  tags: [] as string[],


});





const metadataJson = ref('{}');


const metadataError = ref(false);


const metadataErrorMsg = ref('');





// 验证规则


const rules = {


  required: (v: string) => !!v || t('agent.skills.editor.validation.required'),


  nameFormat: (v: string) => {


    if (!v) return true;


    return /^[a-z][a-z0-9_]*$/.test(v) || t('agent.skills.editor.validation.nameFormat');


  },


};





// 分类选项


const categoryOptions = computed(() => [


  { title: t('agent.skills.categories.general'), value: 'general' },


  { title: t('agent.skills.categories.programming'), value: 'programming' },


  { title: t('agent.skills.categories.analysis'), value: 'analysis' },


  { title: t('agent.skills.categories.creative'), value: 'creative' },


  { title: t('agent.skills.categories.other'), value: 'other' },


]);





// 披露级别选项


const disclosureOptions = computed(() => [


  { title: t('agent.skills.disclosureLevels.metadata'), value: 'metadata' },


  { title: t('agent.skills.disclosureLevels.instructions'), value: 'instructions' },


  { title: t('agent.skills.disclosureLevels.resources'), value: 'resources' },


]);





// 工具选项


const toolOptions = computed(() => {


  return props.tools.map(tool => ({


    title: tool.name,


    value: tool.name,


  }));


});





// 监听技能变


watch(() => props.skill, (newSkill) => {


  if (newSkill) {


    formData.value = {


      name: newSkill.name || '',


      description: newSkill.description || '',


      category: newSkill.category || 'general',


      version: newSkill.version || '1.0.0',


      disclosure_level: newSkill.disclosure_level || 'metadata',


      preapproved_tools: newSkill.preapproved_tools || [],


      workflow: newSkill.workflow || { steps: [] },


      tags: newSkill.tags || [],


    };


    metadataJson.value = newSkill.metadata
      ? JSON.stringify(newSkill.metadata, null, 2)
      : '{}';


  } else {


    resetForm();


  }


}, { immediate: true });





// 验证元数据 JSON


function validateMetadata() {


  if (!metadataJson.value.trim()) {


    metadataError.value = false;


    metadataErrorMsg.value = '';


    return true;


  }





  try {


    JSON.parse(metadataJson.value);


    metadataError.value = false;


    metadataErrorMsg.value = '';


    return true;


  } catch (e) {


    metadataError.value = true;


    metadataErrorMsg.value = t('agent.skills.editor.validation.invalidJson');


    return false;


  }


}





// 格式化元数据 JSON


function formatMetadata() {


  try {


    const parsed = JSON.parse(metadataJson.value);


    metadataJson.value = JSON.stringify(parsed, null, 2);


    metadataError.value = false;


    metadataErrorMsg.value = '';


  } catch (e) {


    // 保持原样


  }


}





// 重置表单


function resetForm() {


  formData.value = {


    name: '',


    description: '',


    category: 'general',


    version: '1.0.0',


    disclosure_level: 'metadata',


    preapproved_tools: [],


    workflow: { steps: [] },


    tags: [],


  };


  metadataJson.value = '{}';


  metadataError.value = false;


  metadataErrorMsg.value = '';


}





// 保存


async function handleSave() {


  const { valid } = await formRef.value?.validate();


  if (!valid) return;





  if (!validateMetadata()) return;





  saving.value = true;


  try {


    const skillData = {


      name: formData.value.name,


      description: formData.value.description,


      category: formData.value.category,


      version: formData.value.version,


      disclosure_level: formData.value.disclosure_level,


      preapproved_tools: formData.value.preapproved_tools,


      workflow: formData.value.workflow,


      metadata: JSON.parse(metadataJson.value || '{}'),


      tags: formData.value.tags,


    };





    await emit('save', skillData);


  } finally {


    saving.value = false;


  }


}


</script>





<style scoped>


.skill-editor-drawer {


  z-index: 1000;


}





.skill-editor-drawer .v-card {


  border-radius: 0;


}


</style>


