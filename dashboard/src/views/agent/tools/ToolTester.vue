<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    max-width="800"
    scrollable
  >
    <v-card v-if="tool">
      <v-card-title class="d-flex align-center pa-4 border-b">
        <v-icon icon="mdi-bug-play" class="mr-2" color="info" />
        {{ $t('agent.tools.tester.title') }}: {{ tool.name }}
        <v-spacer />
        <v-btn icon variant="text" @click="$emit('update:modelValue', false)">
          <v-icon icon="mdi-close" />
        </v-btn>
      </v-card-title>

      <v-card-text style="max-height: 70vh;" class="pa-4">
        <v-alert v-if="tool.description" type="info" variant="tonal" class="mb-4">
          {{ tool.description }}
        </v-alert>

        <div class="mb-4">
          <div class="text-subtitle-1 font-weight-medium mb-2">
            {{ $t('agent.tools.tester.inputParams') }}
          </div>

          <div v-if="hasParameters" class="mb-3">
            <v-row>
              <v-col
                v-for="(param, key) in tool.parameters"
                :key="key"
                cols="12"
                md="6"
              >
                <v-text-field
                  v-if="param.type === 'string' || param.type === 'str'"
                  :model-value="getParamValue(key)"
                  @update:model-value="setParamValue(key, $event)"
                  :label="getKeyLabel(key)"
                  :hint="param.description"
                  persistent-hint
                  :required="param.required"
                  variant="outlined"
                  density="compact"
                />
                <v-text-field
                  v-else-if="param.type === 'number' || param.type === 'integer' || param.type === 'int'"
                  :model-value="getParamValue(key)"
                  @update:model-value="setParamValue(key, Number($event))"
                  :label="getKeyLabel(key)"
                  :hint="param.description"
                  persistent-hint
                  :required="param.required"
                  type="number"
                  variant="outlined"
                  density="compact"
                />
                <v-switch
                  v-else-if="param.type === 'boolean' || param.type === 'bool'"
                  :model-value="!!paramValues[key]"
                  @update:model-value="setParamValue(key, $event)"
                  :label="getKeyLabel(key)"
                  :hint="param.description"
                  persistent-hint
                  color="primary"
                  hide-details
                />
                <v-textarea
                  v-else-if="param.type === 'array' || param.type === 'list'"
                  :model-value="getParamValue(key)"
                  @update:model-value="setParamValue(key, $event)"
                  :label="getKeyLabel(key)"
                  :hint="param.description"
                  persistent-hint
                  :required="param.required"
                  variant="outlined"
                  density="compact"
                  rows="2"
                  auto-grow
                />
                <v-text-field
                  v-else
                  :model-value="getParamValue(key)"
                  @update:model-value="setParamValue(key, $event)"
                  :label="getKeyLabel(key)"
                  :hint="param.description"
                  persistent-hint
                  :required="param.required"
                  variant="outlined"
                  density="compact"
                />
              </v-col>
            </v-row>
          </div>

          <v-textarea
            v-model="paramsJson"
            :label="$t('agent.tools.tester.paramsJson')"
            :error="paramsError"
            :error-messages="paramsErrorMsg"
            rows="6"
            auto-grow
            variant="outlined"
            @blur="validateParams"
          />

          <v-btn variant="outlined" size="small" class="mr-2" @click="formatParams">
            <v-icon start icon="mdi-format-align-left" />
            {{ $t('agent.tools.tester.formatJson') }}
          </v-btn>

          <v-btn variant="outlined" size="small" @click="resetParams">
            <v-icon start icon="mdi-refresh" />
            {{ $t('agent.tools.tester.reset') }}
          </v-btn>
        </div>

        <v-divider class="my-4" />

        <div>
          <div class="text-subtitle-1 font-weight-medium mb-2">
            {{ $t('agent.tools.tester.result') }}
          </div>

          <v-card v-if="executing" variant="outlined" class="pa-4 text-center">
            <v-progress-circular indeterminate color="primary" />
            <p class="mt-2 text-grey">{{ $t('agent.tools.tester.executing') }}</p>
          </v-card>

          <v-card v-else-if="result !== null" :color="success ? 'success' : 'error'" variant="outlined">
            <v-card-text>
              <div class="d-flex align-center mb-2">
                <v-icon :icon="success ? 'mdi-check-circle' : 'mdi-alert-circle'" class="mr-2" />
                <span class="font-weight-medium">
                  {{ success ? $t('agent.tools.tester.success') : $t('agent.tools.tester.failed') }}
                </span>
                <v-spacer />
                <v-btn v-if="resultText" icon size="small" variant="text" @click="copyResult">
                  <v-icon icon="mdi-content-copy" />
                </v-btn>
              </div>
              <pre v-if="resultText" class="result-text">{{ resultText }}</pre>
              <p v-else class="text-grey">{{ $t('agent.tools.tester.noResult') }}</p>
            </v-card-text>
          </v-card>

          <v-card v-else variant="outlined" class="pa-4 text-center text-grey">
            <v-icon icon="mdi-play-circle-outline" size="48" class="mb-2" />
            <p>{{ $t('agent.tools.tester.clickToTest') }}</p>
          </v-card>
        </div>
      </v-card-text>

      <v-card-actions class="pa-4 border-t">
        <v-spacer />
        <v-btn variant="outlined" @click="$emit('update:modelValue', false)">
          {{ $t('common.close') }}
        </v-btn>
        <v-btn color="primary" @click="executeTest" :loading="executing" :disabled="paramsError">
          <v-icon start icon="mdi-play" />
          {{ $t('agent.tools.tester.execute') }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import axios from 'axios';
import { useI18n } from 'vue-i18n';

const props = defineProps<{
  modelValue: boolean;
  tool: any;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const { t } = useI18n();

const paramValues = ref<Record<string, any>>({});
const paramsJson = ref('{}');
const paramsError = ref(false);
const paramsErrorMsg = ref('');
const executing = ref(false);
const result = ref<any>(null);
const success = ref(false);

function getParamValue(key: string | number): string {
  const val = paramValues.value[key];
  return val === null || val === undefined ? '' : String(val);
}

function setParamValue(key: string | number, value: any): void {
  paramValues.value[key] = value;
}

function getKeyLabel(key: string | number): string {
  return String(key);
}

const hasParameters = computed(() => {
  return props.tool?.parameters && Object.keys(props.tool.parameters).length > 0;
});

const resultText = computed(() => {
  if (result.value === null) return null;
  if (typeof result.value === 'string') return result.value;
  try {
    return JSON.stringify(result.value, null, 2);
  } catch {
    return String(result.value);
  }
});

watch(() => props.tool, (newTool) => {
  if (newTool && newTool.parameters) {
    const values: Record<string, any> = {};
    for (const [key, param] of Object.entries(newTool.parameters)) {
      const p = param as any;
      if (p.default !== undefined) {
        values[key] = p.default;
      } else if (p.type === 'boolean' || p.type === 'bool') {
        values[key] = false;
      } else if (p.type === 'number' || p.type === 'integer' || p.type === 'int') {
        values[key] = 0;
      } else {
        values[key] = '';
      }
    }
    paramValues.value = values;
    updateParamsJson();
  } else {
    paramValues.value = {};
    paramsJson.value = '{}';
  }
  result.value = null;
  success.value = false;
}, { immediate: true });

watch(paramValues, () => {
  updateParamsJson();
}, { deep: true });

function updateParamsJson() {
  const params: Record<string, any> = {};
  for (const [key, value] of Object.entries(paramValues.value)) {
    if (value !== '' && value !== null && value !== undefined) {
      params[key] = value;
    }
  }
  paramsJson.value = JSON.stringify(params, null, 2);
}

function validateParams() {
  if (!paramsJson.value.trim()) {
    paramsError.value = false;
    paramsErrorMsg.value = '';
    return true;
  }
  try {
    JSON.parse(paramsJson.value);
    paramsError.value = false;
    paramsErrorMsg.value = '';
    return true;
  } catch (e) {
    paramsError.value = true;
    paramsErrorMsg.value = t('agent.tools.tester.invalidJson');
    return false;
  }
}

function formatParams() {
  try {
    const parsed = JSON.parse(paramsJson.value);
    paramsJson.value = JSON.stringify(parsed, null, 2);
    paramsError.value = false;
    paramsErrorMsg.value = '';
  } catch (e) {
    // keep as is
  }
}

function resetParams() {
  if (props.tool?.parameters) {
    const values: Record<string, any> = {};
    for (const [key, param] of Object.entries(props.tool.parameters)) {
      const p = param as any;
      if (p.default !== undefined) {
        values[key] = p.default;
      } else if (p.type === 'boolean' || p.type === 'bool') {
        values[key] = false;
      } else if (p.type === 'number' || p.type === 'integer' || p.type === 'int') {
        values[key] = 0;
      } else {
        values[key] = '';
      }
    }
    paramValues.value = values;
  } else {
    paramValues.value = {};
    paramsJson.value = '{}';
  }
  result.value = null;
  success.value = false;
}

async function executeTest() {
  if (!validateParams()) return;

  executing.value = true;
  result.value = null;

  try {
    const params = JSON.parse(paramsJson.value);
    const response = await axios.post('/api/plug/agent/tools/test', {
      name: props.tool.name,
      params: params,
    });

    if (response.data.status === 'ok') {
      success.value = true;
      result.value = response.data.data;
    } else {
      success.value = false;
      result.value = response.data.message || t('agent.tools.tester.unknownError');
    }
  } catch (error: any) {
    success.value = false;
    result.value = error.response?.data?.message || error.message || t('agent.tools.tester.requestFailed');
  } finally {
    executing.value = false;
  }
}

function copyResult() {
  if (resultText.value) {
    navigator.clipboard.writeText(resultText.value);
  }
}
</script>

<style scoped>
.result-text {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.05);
  padding: 12px;
  border-radius: 8px;
  font-family: monospace;
  font-size: 13px;
  margin: 0;
}
</style>
