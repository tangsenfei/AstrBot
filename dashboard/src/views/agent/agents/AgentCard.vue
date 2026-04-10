<template>


  <v-card


    class="agent-card"


    :class="{ 'agent-disabled': !agent.enabled }"


    hover


  >


    <v-card-text class="pb-2">


      <!-- 标题和状态-->


      <div class="d-flex align-start justify-space-between mb-2">


        <div class="flex-grow-1">


          <div class="text-h6 text-truncate" :title="agent.name">


            {{ agent.name }}


          </div>


          <v-chip


            :color="statusColor"


            size="x-small"


            class="mt-1"


          >


            {{ statusLabel }}


          </v-chip>


        </div>


        <v-switch


          v-model="agent.enabled"


          color="success"


          hide-details


          density="compact"


          class="ml-2 mt-0"


          @change="handleToggle"


        />


      </div>





      <!-- 角色描述 -->


      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">


        {{ agent.role || $t('agent.agents.card.noRole') }}


      </p>





      <!-- 模型信息 -->


      <div v-if="agent.model" class="d-flex align-center mb-2">


        <v-icon icon="mdi-robot" size="small" class="mr-1" />


        <span class="text-caption text-grey">


          {{ agent.model.provider }} / {{ agent.model.name }}


        </span>


      </div>





      <!-- 能力图标 -->


      <div class="d-flex align-center mb-2 flex-wrap" style="gap: 8px;">


        <v-tooltip v-if="agent.tools && agent.tools.length > 0" location="top">


          <template v-slot:activator="{ props }">


            <v-chip size="x-small" color="primary" variant="flat" v-bind="props">


              <v-icon icon="mdi-tools" start size="small" />


              {{ agent.tools.length }}


            </v-chip>


          </template>


          {{ $t('agent.agents.card.tools', { count: agent.tools.length }) }}


        </v-tooltip>





        <v-tooltip v-if="agent.skills && agent.skills.length > 0" location="top">


          <template v-slot:activator="{ props }">


            <v-chip size="x-small" color="success" variant="flat" v-bind="props">


              <v-icon icon="mdi-lightning-bolt" start size="small" />


              {{ agent.skills.length }}


            </v-chip>


          </template>


          {{ $t('agent.agents.card.skills', { count: agent.skills.length }) }}


        </v-tooltip>





        <v-tooltip v-if="agent.knowledgeBases && agent.knowledgeBases.length > 0" location="top">


          <template v-slot:activator="{ props }">


            <v-chip size="x-small" color="info" variant="flat" v-bind="props">


              <v-icon icon="mdi-database" start size="small" />


              {{ agent.knowledgeBases.length }}


            </v-chip>


          </template>


          {{ $t('agent.agents.card.knowledgeBases', { count: agent.knowledgeBases.length }) }}


        </v-tooltip>


      </div>





      <!-- Planning Memory 状-->


      <div class="d-flex align-center flex-wrap" style="gap: 8px;">


        <v-chip


          v-if="agent.planning && agent.planning.enabled"


          size="x-small"


          variant="outlined"


          color="warning"


        >


          <v-icon icon="mdi-head-lightbulb" start size="small" />


          {{ $t('agent.agents.card.planning') }}


        </v-chip>





        <v-chip


          v-if="agent.memory && agent.memory.enabled"


          size="x-small"


          variant="outlined"


          color="purple"


        >


          <v-icon icon="mdi-brain" start size="small" />


          {{ $t('agent.agents.card.memory') }}


        </v-chip>


      </div>


    </v-card-text>





    <v-divider />





    <!-- 操作按钮 -->


    <v-card-actions class="pa-2">


      <v-btn


        icon


        size="small"


        variant="text"


        color="info"


        @click="$emit('test', agent)"


        :title="$t('agent.agents.card.test')"


      >


        <v-icon icon="mdi-message-text" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="primary"


        @click="$emit('edit', agent)"


        :title="$t('agent.agents.card.edit')"


      >


        <v-icon icon="mdi-pencil" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="default"


        @click="$emit('copy', agent)"


        :title="$t('agent.agents.card.copy')"


      >


        <v-icon icon="mdi-content-copy" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="error"


        @click="$emit('delete', agent)"


        :title="$t('agent.agents.card.delete')"


      >


        <v-icon icon="mdi-delete" />


      </v-btn>


    </v-card-actions>


  </v-card>


</template>





<script setup lang="ts">


import { computed } from 'vue';


import { useI18n } from 'vue-i18n';





const props = defineProps<{


  agent: any;


}>();





const emit = defineEmits<{


  (e: 'edit', agent: any): void;


  (e: 'test', agent: any): void;


  (e: 'copy', agent: any): void;


  (e: 'delete', agent: any): void;


  (e: 'toggle', agent: any): void;


}>();





const { t } = useI18n();





// 计算属性


const statusColor = computed(() => {


  return props.agent.enabled ? 'success' : 'grey';


});





const statusLabel = computed(() => {
  return props.agent.enabled
    ? t('agent.agents.status.enabled')
    : t('agent.agents.status.disabled');
});





// 方法


function handleToggle() {


  emit('toggle', props.agent);


}


</script>





<style scoped>


.agent-card {


  height: 100%;


  display: flex;


  flex-direction: column;


  transition: all 0.3s ease;


}





.agent-card:hover {


  transform: translateY(-2px);


  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);


}





.agent-disabled {


  opacity: 0.7;


}





.description-text {


  display: -webkit-box;


  -webkit-line-clamp: 2;


  -webkit-box-orient: vertical;


  overflow: hidden;


  min-height: 40px;


}





.v-card-actions {


  margin-top: auto;


}


</style>


