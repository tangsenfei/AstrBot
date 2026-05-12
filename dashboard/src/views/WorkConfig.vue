<template>
    <v-card variant="flat" class="settings-shell">
        <v-tabs v-model="configTab" color="primary" class="mb-3">
            <v-tab value="daily">
                <v-icon start>mdi-calendar-check</v-icon>
                {{ tm('tabs.daily') }}
            </v-tab>
            <v-tab value="meeting">
                <v-icon start>mdi-video-box</v-icon>
                {{ tm('tabs.meeting') }}
            </v-tab>
            <v-tab value="project">
                <v-icon start>mdi-archive</v-icon>
                {{ tm('tabs.project') }}
            </v-tab>
        </v-tabs>

        <v-window v-model="configTab">
            <v-window-item value="daily">
                <div class="work-config-panel">
                    <div class="d-flex align-center justify-space-between flex-wrap mb-4">
                        <div>
                            <div class="text-h6">{{ tm('daily.title') }}</div>
                            <div class="text-body-2 text-medium-emphasis">
                                {{ tm('daily.description') }}
                            </div>
                        </div>
                        <div class="d-flex ga-2">
                            <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="workConfigLoading" @click="loadWorkConfig">
                                {{ tm('daily.refresh') }}
                            </v-btn>
                            <v-btn variant="tonal" color="warning" prepend-icon="mdi-restore" :loading="workConfigSaving" @click="resetWorkConfig">
                                {{ tm('daily.resetToDefault') }}
                            </v-btn>
                            <v-btn color="primary" prepend-icon="mdi-content-save" :loading="workConfigSaving" @click="saveWorkConfig">
                                {{ tm('daily.save') }}
                            </v-btn>
                        </div>
                    </div>

                    <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                        {{ tm('daily.alertText') }}
                    </v-alert>

                    <v-progress-linear v-if="workConfigLoading" indeterminate color="primary" class="mb-4" />

                    <div v-if="workConfig" class="work-config-grid">
                        <section class="work-config-section">
                            <div class="section-title">{{ tm('daily.sections.clarification') }}</div>
                            <v-select v-model="workConfig.daily.clarification.standard.agent_id" :items="workAgentItems" :label="tm('daily.fields.clarificationAgent')" variant="outlined" density="compact" />
                            <v-textarea v-model="workConfig.daily.clarification.standard.system_prompt" :label="tm('daily.fields.systemPrompt')" variant="outlined" rows="3" auto-grow />
                            <v-textarea v-model="workConfig.daily.clarification.standard.prompt" :label="tm('daily.fields.userPrompt')" variant="outlined" rows="8" auto-grow />
                        </section>

                        <section class="work-config-section">
                            <div class="section-title">{{ tm('daily.sections.interrogation') }}</div>
                            <v-select v-model="workConfig.daily.clarification.interrogation.agent_id" :items="workAgentItems" :label="tm('daily.fields.interrogationAgent')" variant="outlined" density="compact" />
                            <v-text-field v-model.number="workConfig.daily.clarification.interrogation.max_rounds" type="number" min="1" max="10" :label="tm('daily.fields.maxRounds')" variant="outlined" density="compact" />
                            <v-textarea v-model="workConfig.daily.clarification.interrogation.system_prompt" :label="tm('daily.fields.systemPrompt')" variant="outlined" rows="3" auto-grow />
                            <v-textarea v-model="workConfig.daily.clarification.interrogation.prompt" :label="tm('daily.fields.userPrompt')" variant="outlined" rows="8" auto-grow />
                        </section>

                        <section class="work-config-section full">
                            <div class="section-title">{{ tm('daily.sections.planning') }}</div>
                            <v-expansion-panels variant="accordion">
                                <v-expansion-panel v-for="mode in planningModes" :key="mode.value">
                                    <v-expansion-panel-title>{{ mode.title }}</v-expansion-panel-title>
                                    <v-expansion-panel-text>
                                        <v-select v-model="workConfig.daily.planning[mode.value].agent_id" :items="workAgentItems" :label="tm('daily.fields.planningAgent')" variant="outlined" density="compact" />
                                        <v-textarea v-model="workConfig.daily.planning[mode.value].system_prompt" :label="tm('daily.fields.systemPrompt')" variant="outlined" rows="3" auto-grow />
                                        <v-textarea v-model="workConfig.daily.planning[mode.value].prompt" :label="tm('daily.fields.userPrompt')" variant="outlined" rows="8" auto-grow />
                                    </v-expansion-panel-text>
                                </v-expansion-panel>
                            </v-expansion-panels>
                        </section>

                        <section class="work-config-section">
                            <div class="section-title">{{ tm('daily.sections.deliverable') }}</div>
                            <v-select v-model="workConfig.daily.deliverable.reporter_agent_id" :items="workAgentItems" :label="tm('daily.fields.reporterAgent')" variant="outlined" density="compact" />
                            <v-select v-model="workConfig.daily.deliverable.artifact_type" :items="artifactTypeOptions" :label="tm('daily.fields.artifactType')" variant="outlined" density="compact" />
                            <v-textarea v-model="workConfig.daily.deliverable.system_prompt" :label="tm('daily.fields.systemPrompt')" variant="outlined" rows="3" auto-grow />
                            <v-textarea v-model="workConfig.daily.deliverable.prompt" :label="tm('daily.fields.userPrompt')" variant="outlined" rows="8" auto-grow />
                        </section>
                    </div>
                </div>
            </v-window-item>

            <v-window-item value="meeting">
                <div class="placeholder-panel">
                    <v-icon size="64" color="grey-lighten-1">mdi-video-box</v-icon>
                    <div class="text-h6 mt-4">{{ tm('meeting.title') }}</div>
                    <div class="text-body-1 text-medium-emphasis mt-2">{{ tm('meeting.placeholder') }}</div>
                </div>
            </v-window-item>

            <v-window-item value="project">
                <div class="placeholder-panel">
                    <v-icon size="64" color="grey-lighten-1">mdi-archive</v-icon>
                    <div class="text-h6 mt-4">{{ tm('project.title') }}</div>
                    <div class="text-body-1 text-medium-emphasis mt-2">{{ tm('project.placeholder') }}</div>
                </div>
            </v-window-item>
        </v-window>
    </v-card>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';
import { useModuleI18n } from '@/i18n/composables';
import { useToastStore } from '@/stores/toast';

const { tm } = useModuleI18n('features/work-config');
const toastStore = useToastStore();
const configTab = ref('daily');
const workConfig = ref(null);
const workConfigLoading = ref(false);
const workConfigSaving = ref(false);
const workAgents = ref([]);
const planningModes = [
    { title: '快速模式', value: 'quick' },
    { title: '常规模式', value: 'normal' },
    { title: '深度模式', value: 'deep' }
];
const artifactTypeOptions = [
    { title: 'Markdown', value: 'markdown' },
    { title: '文件', value: 'file' },
    { title: '结构化 JSON', value: 'json' }
];
const workAgentItems = computed(() =>
    workAgents.value.map((agent) => ({
        title: agent.name ? `${agent.name} (${agent.id})` : agent.id,
        value: agent.id
    }))
);

const showToast = (message, color = 'success') => {
    toastStore.add({
        message,
        color,
        timeout: 3000
    });
};

const defaultWorkConfig = () => ({
    daily: {
        clarification: {
            standard: { agent_id: '', system_prompt: '', prompt: '' },
            interrogation: { agent_id: '', system_prompt: '', prompt: '', max_rounds: 5 }
        },
        planning: {
            quick: { agent_id: '', system_prompt: '', prompt: '' },
            normal: { agent_id: '', system_prompt: '', prompt: '' },
            deep: { agent_id: '', system_prompt: '', prompt: '' }
        },
        deliverable: {
            reporter_agent_id: '',
            system_prompt: '',
            prompt: '',
            artifact_type: 'markdown'
        }
    }
});

const mergeDefaults = (base, override) => {
    Object.entries(override || {}).forEach(([key, value]) => {
        if (value && typeof value === 'object' && !Array.isArray(value) && base[key] && typeof base[key] === 'object') {
            mergeDefaults(base[key], value);
        } else {
            base[key] = value;
        }
    });
    return base;
};

const normalizeWorkConfig = (data) => mergeDefaults(defaultWorkConfig(), data || {});

const loadWorkAgents = async () => {
    try {
        const res = await axios.get('/api/plug/agent/agents');
        if (res.data.status === 'ok') {
            workAgents.value = res.data.data || [];
        }
    } catch (e) {
        showToast(e?.response?.data?.message || 'Failed to load agents', 'error');
    }
};

const loadWorkConfig = async () => {
    workConfigLoading.value = true;
    try {
        await loadWorkAgents();
        const res = await axios.get('/api/plug/work/config');
        if (res.data.status !== 'ok') {
            showToast(res.data.message || 'Failed to load Work config', 'error');
            return;
        }
        workConfig.value = normalizeWorkConfig(res.data.data);
    } catch (e) {
        showToast(e?.response?.data?.message || 'Failed to load Work config', 'error');
    } finally {
        workConfigLoading.value = false;
    }
};

const saveWorkConfig = async () => {
    if (!workConfig.value) return;
    workConfigSaving.value = true;
    try {
        const res = await axios.put('/api/plug/work/config', workConfig.value);
        if (res.data.status !== 'ok') {
            showToast(res.data.message || 'Failed to save Work config', 'error');
            return;
        }
        workConfig.value = normalizeWorkConfig(res.data.data);
        showToast('Work config saved', 'success');
    } catch (e) {
        showToast(e?.response?.data?.message || 'Failed to save Work config', 'error');
    } finally {
        workConfigSaving.value = false;
    }
};

const resetWorkConfig = async () => {
    workConfigSaving.value = true;
    try {
        const res = await axios.post('/api/plug/work/config/reset');
        if (res.data.status !== 'ok') {
            showToast(res.data.message || 'Failed to reset Work config', 'error');
            return;
        }
        workConfig.value = normalizeWorkConfig(res.data.data);
        showToast('Work config reset', 'success');
    } catch (e) {
        showToast(e?.response?.data?.message || 'Failed to reset Work config', 'error');
    } finally {
        workConfigSaving.value = false;
    }
};

onMounted(() => {
    loadWorkConfig();
});
</script>

<style scoped>
.settings-shell {
    padding: 8px;
}

.work-config-panel {
    padding: 16px;
    border-radius: 8px;
    background: rgb(var(--v-theme-surface));
}

.work-config-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(280px, 1fr));
    gap: 16px;
}

.work-config-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border: 1px solid rgba(var(--v-border-color), 0.18);
    border-radius: 8px;
}

.work-config-section.full {
    grid-column: 1 / -1;
}

.section-title {
    font-size: 14px;
    font-weight: 700;
}

.placeholder-panel {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 16px;
    text-align: center;
    border-radius: 8px;
    background: rgb(var(--v-theme-surface));
}

@media (max-width: 900px) {
    .work-config-grid {
        grid-template-columns: 1fr;
    }
}
</style>
