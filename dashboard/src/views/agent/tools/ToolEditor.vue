<template>


  <v-navigation-drawer


    :model-value="modelValue"


    @update:model-value="$emit('update:modelValue', $event)"


    location="right"


    temporary


    width="600"


    class="tool-editor-drawer"


  >


    <v-card flat class="h-100 d-flex flex-column">


      <!-- 标题 -->


      <v-card-title class="d-flex align-center pa-4 border-b">


        <v-icon icon="mdi-tools" class="mr-2" />


        {{ isEditing ? $t('agent.tools.editor.editTitle') : $t('agent.tools.editor.addTitle') }}


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


            {{ $t('agent.tools.editor.basicInfo') }}


          </div>





          <v-text-field


            v-model="formData.name"


            :label="$t('agent.tools.editor.name')"


            :rules="[rules.required, rules.nameFormat]"


            :disabled="isEditing"


            :hint="$t('agent.tools.editor.nameHint')"


            persistent-hint


            class="mb-3"


          />





          <v-text-field


            v-model="formData.description"


            :label="$t('agent.tools.editor.description')"


            :rules="[rules.required]"


            :hint="$t('agent.tools.editor.descriptionHint')"


            persistent-hint


            class="mb-3"


          />





          <v-select


            v-model="formData.source"


            :items="sourceOptions"


            :label="$t('agent.tools.editor.source')"


            :rules="[rules.required]"


            :disabled="isEditing"


            class="mb-3"


          />





          <v-text-field


            v-model="formData.returnType"


            :label="$t('agent.tools.editor.returnType')"


            :hint="$t('agent.tools.editor.returnTypeHint')"


            persistent-hint


            class="mb-4"


          />





          <v-divider class="my-4" />





          <!-- 参数定义 -->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.tools.editor.parameters') }}


          </div>





          <v-alert type="info" variant="tonal" class="mb-3" density="compact">


            {{ $t('agent.tools.editor.parametersHint') }}


          </v-alert>





          <v-textarea


            v-model="parametersJson"


            :label="$t('agent.tools.editor.parametersJson')"


            :error="parametersError"


            :error-messages="parametersErrorMsg"


            rows="8"


            auto-grow


            class="mb-3"


            @blur="validateParameters"


          />





          <v-btn


            variant="outlined"


            size="small"


            class="mb-4"


            @click="formatParameters"


          >


            <v-icon start icon="mdi-format-align-left" />


            {{ $t('agent.tools.editor.formatJson') }}


          </v-btn>





          <v-divider class="my-4" />





          <!-- 元数据-->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.tools.editor.metadata') }}


          </div>





          <v-textarea


            v-model="metadataJson"


            :label="$t('agent.tools.editor.metadataJson')"


            :error="metadataError"


            :error-messages="metadataErrorMsg"


            rows="4"


            auto-grow


            class="mb-3"


            @blur="validateMetadata"


          />





          <v-divider class="my-4" />





          <!-- 标签 -->


          <div class="text-subtitle-1 font-weight-medium mb-3">


            {{ $t('agent.tools.editor.tags') }}


          </div>





          <v-combobox


            v-model="formData.tags"


            :label="$t('agent.tools.editor.tagsLabel')"


            multiple


            chips


            closable-chips


            :hint="$t('agent.tools.editor.tagsHint')"


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





const props = defineProps<{


  modelValue: boolean;


  tool: any;


  isEditing: boolean;


}>();





const emit = defineEmits<{


  (e: 'update:modelValue', value: boolean): void;


  (e: 'save', toolData: any): void;


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


  source: 'custom',


  returnType: 'string',


  tags: [] as string[],


});





const parametersJson = ref('{\n  \n}');


const parametersError = ref(false);


const parametersErrorMsg = ref('');





const metadataJson = ref('{}');


const metadataError = ref(false);


const metadataErrorMsg = ref('');





// 验证规则


const rules = {


  required: (v: string) => !!v || t('agent.tools.editor.validation.required'),


  nameFormat: (v: string) => {


    if (!v) return true;


    return /^[a-z][a-z0-9_]*$/.test(v) || t('agent.tools.editor.validation.nameFormat');


  },


};





// 来源选项


const sourceOptions = computed(() => [


  { title: t('agent.tools.sources.custom'), value: 'custom' },


  { title: t('agent.tools.sources.apiWrapper'), value: 'api_wrapper' },


]);





// 监听工具变化


watch(() => props.tool, (newTool) => {


  if (newTool) {


    formData.value = {


      name: newTool.name || '',


      description: newTool.description || '',


      source: newTool.source || 'custom',


      returnType: newTool.returnType || 'string',


      tags: newTool.tags || [],


    };


    parametersJson.value = newTool.parameters
      ? JSON.stringify(newTool.parameters, null, 2)
      : '{\n  \n}';
    metadataJson.value = newTool.metadata
      ? JSON.stringify(newTool.metadata, null, 2)
      : '{}';


  } else {


    resetForm();


  }


}, { immediate: true });





// 验证参数 JSON


function validateParameters() {


  if (!parametersJson.value.trim()) {


    parametersError.value = false;


    parametersErrorMsg.value = '';


    return true;


  }





  try {


    JSON.parse(parametersJson.value);


    parametersError.value = false;


    parametersErrorMsg.value = '';


    return true;


  } catch (e) {


    parametersError.value = true;


    parametersErrorMsg.value = t('agent.tools.editor.validation.invalidJson');


    return false;


  }


}





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


    metadataErrorMsg.value = t('agent.tools.editor.validation.invalidJson');


    return false;


  }


}





// 格式化参数 JSON


function formatParameters() {


  try {


    const parsed = JSON.parse(parametersJson.value);


    parametersJson.value = JSON.stringify(parsed, null, 2);


    parametersError.value = false;


    parametersErrorMsg.value = '';


  } catch (e) {


    // 保持原样


  }


}





// 重置表单


function resetForm() {


  formData.value = {


    name: '',


    description: '',


    source: 'custom',


    returnType: 'string',


    tags: [],


  };


  parametersJson.value = '{\n  \n}';


  metadataJson.value = '{}';


  parametersError.value = false;


  parametersErrorMsg.value = '';


  metadataError.value = false;


  metadataErrorMsg.value = '';


}





// 保存


async function handleSave() {


  const { valid } = await formRef.value?.validate();


  if (!valid) return;





  if (!validateParameters() || !validateMetadata()) return;





  saving.value = true;


  try {


    const toolData = {


      name: formData.value.name,


      description: formData.value.description,


      source: formData.value.source,


      returnType: formData.value.returnType,


      parameters: JSON.parse(parametersJson.value || '{}'),


      metadata: JSON.parse(metadataJson.value || '{}'),


      tags: formData.value.tags,


    };





    await emit('save', toolData);


  } finally {


    saving.value = false;


  }


}


</script>





<style scoped>


.tool-editor-drawer {


  z-index: 1000;


}





.tool-editor-drawer .v-card {


  border-radius: 0;


}


</style>


