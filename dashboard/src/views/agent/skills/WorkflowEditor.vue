<template>

  <v-card variant="outlined" class="workflow-editor">

    <v-card-text>

      <!-- 步骤列表 -->

      <div v-if="modelValue.steps && modelValue.steps.length > 0" class="mb-4">

        <v-list density="compact" class="bg-grey-lighten-4 rounded">

          <v-list-item

            v-for="(step, index) in modelValue.steps"

            :key="index"

            class="px-2"

          >

            <template v-slot:prepend>

              <v-chip size="x-small" color="primary" class="mr-2">

                {{ index + 1 }}

              </v-chip>

            </template>



            <v-list-item-title class="text-body-2">{{ step.name }}</v-list-item-title>

            <v-list-item-subtitle v-if="step.description" class="text-caption">

              {{ step.description }}

            </v-list-item-subtitle>



            <template v-slot:append>

              <v-btn

                icon

                size="x-small"

                variant="text"

                :disabled="index === 0"

                @click="moveStep(index, -1)"

                :title="$t('agent.skills.workflow.moveUp')"

              >

                <v-icon icon="mdi-arrow-up" />

              </v-btn>

              <v-btn

                icon

                size="x-small"

                variant="text"

                :disabled="index === modelValue.steps.length - 1"

                @click="moveStep(index, 1)"

                :title="$t('agent.skills.workflow.moveDown')"

              >

                <v-icon icon="mdi-arrow-down" />

              </v-btn>

              <v-btn

                icon

                size="x-small"

                variant="text"

                color="error"

                @click="removeStep(index)"

                :title="$t('agent.skills.workflow.removeStep')"

              >

                <v-icon icon="mdi-delete" />

              </v-btn>

            </template>

          </v-list-item>

        </v-list>

      </div>



      <v-alert v-else type="info" variant="tonal" density="compact" class="mb-4">

        {{ $t('agent.skills.workflow.noSteps') }}

      </v-alert>



      <!-- 添加步骤 -->

      <v-expansion-panels>

        <v-expansion-panel>

          <v-expansion-panel-title>

            <v-icon icon="mdi-plus" class="mr-2" />

            {{ $t('agent.skills.workflow.addStep') }}

          </v-expansion-panel-title>

          <v-expansion-panel-text>

            <v-form ref="stepFormRef" class="mt-2">

              <v-text-field

                v-model="newStep.name"

                :label="$t('agent.skills.workflow.stepName')"

                :rules="[stepRules.required]"

                density="compact"

                class="mb-2"

              />



              <v-text-field

                v-model="newStep.description"

                :label="$t('agent.skills.workflow.stepDescription')"

                density="compact"

                class="mb-2"

              />



              <v-select

                v-model="newStep.tool"

                :items="toolOptions"

                :label="$t('agent.skills.workflow.stepTool')"

                density="compact"

                clearable

                class="mb-2"

              />



              <v-btn

                color="primary"

                size="small"

                @click="addStep"

                :disabled="!newStep.name"

              >

                <v-icon start icon="mdi-plus" />

                {{ $t('agent.skills.workflow.addStep') }}

              </v-btn>

            </v-form>

          </v-expansion-panel-text>

        </v-expansion-panel>

      </v-expansion-panels>



      <v-divider class="my-4" />



      <!-- JSON 预览 -->

      <v-expansion-panels>

        <v-expansion-panel>

          <v-expansion-panel-title>

            <v-icon icon="mdi-code-json" class="mr-2" />

            {{ $t('agent.skills.workflow.jsonPreview') }}

          </v-expansion-panel-title>

          <v-expansion-panel-text>

            <pre class="json-preview">{{ workflowJson }}</pre>

          </v-expansion-panel-text>

        </v-expansion-panel>

      </v-expansion-panels>

    </v-card-text>

  </v-card>

</template>



<script setup lang="ts">

import { ref, computed } from 'vue';

import { useI18n } from 'vue-i18n';



const props = defineProps<{

  modelValue: any;

  tools: any[];

}>();



const emit = defineEmits<{

  (e: 'update:modelValue', value: any): void;

}>();



const { t } = useI18n();



// 状

const stepFormRef = ref();

const newStep = ref({

  name: '',

  description: '',

  tool: '',

});



// 验证规则

const stepRules = {

  required: (v: string) => !!v || t('agent.skills.editor.validation.required'),

};



// 工具选项

const toolOptions = computed(() => {

  return props.tools.map(tool => ({

    title: tool.name,

    value: tool.name,

  }));

});



// 工作流 JSON

const workflowJson = computed(() => {

  return JSON.stringify(props.modelValue, null, 2);

});



// 添加步骤

function addStep() {

  if (!newStep.value.name) return;



  const steps = [...(props.modelValue.steps || [])];

  steps.push({

    name: newStep.value.name,

    description: newStep.value.description,

    tool: newStep.value.tool,

  });



  emit('update:modelValue', {

    ...props.modelValue,

    steps,

  });



  // 重置表单

  newStep.value = {

    name: '',

    description: '',

    tool: '',

  };

}



// 移动步骤

function moveStep(index: number, direction: number) {

  const steps = [...props.modelValue.steps];

  const newIndex = index + direction;



  if (newIndex < 0 || newIndex >= steps.length) return;



  const temp = steps[index];

  steps[index] = steps[newIndex];

  steps[newIndex] = temp;



  emit('update:modelValue', {

    ...props.modelValue,

    steps,

  });

}



// 删除步骤

function removeStep(index: number) {

  const steps = [...props.modelValue.steps];

  steps.splice(index, 1);



  emit('update:modelValue', {

    ...props.modelValue,

    steps,

  });

}

</script>



<style scoped>

.workflow-editor {

  border-radius: 8px;

}



.json-preview {

  background-color: #f5f5f5;

  padding: 12px;

  border-radius: 4px;

  font-family: monospace;

  font-size: 12px;

  overflow-x: auto;

  white-space: pre-wrap;

  word-wrap: break-word;

}

</style>

