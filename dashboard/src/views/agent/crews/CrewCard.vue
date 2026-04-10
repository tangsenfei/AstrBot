<template>


  <v-card


    class="crew-card"


    hover


  >


    <v-card-text class="pb-2">


      <!-- 标题和 Process 类型 -->


      <div class="d-flex align-start justify-space-between mb-2">


        <div class="flex-grow-1">


          <div class="text-h6 text-truncate" :title="crew.name">


            {{ crew.name }}


          </div>


          <v-chip


            :color="processColor"


            size="x-small"


            class="mt-1"


          >


            {{ processLabel }}


          </v-chip>


        </div>


      </div>





      <!-- 描述 -->


      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">


        {{ crew.description || $t('agent.crews.card.noDescription') }}


      </p>





      <!-- Agent 成员列表 -->


      <div v-if="crew.agents && crew.agents.length > 0" class="mb-3">


        <div class="text-caption text-grey mb-1">


          {{ $t('agent.crews.card.agents') }}


        </div>


        <div class="d-flex align-center flex-wrap" style="gap: 4px;">


          <v-tooltip


            v-for="(agent, index) in crew.agents.slice(0, 5)"


            :key="index"


            location="top"


          >


            <template v-slot:activator="{ props }">


              <v-avatar


                size="32"


                color="primary"


                variant="tonal"


                v-bind="props"


                class="agent-avatar"


              >


                <v-icon icon="mdi-robot" size="small" />


              </v-avatar>


            </template>


            {{ typeof agent === 'string'  ? agent : agent.name || agent.role }}


          </v-tooltip>


          <v-chip


            v-if="crew.agents.length > 5"


            size="x-small"


            variant="outlined"


          >


            +{{ crew.agents.length - 5 }}


          </v-chip>


        </div>


      </div>





      <!-- 统计信息 -->


      <div class="d-flex align-center flex-wrap" style="gap: 8px;">


        <v-chip size="x-small" color="primary" variant="flat">


          <v-icon icon="mdi-robot" start size="small" />


          {{ crew.agents?.length || 0 }}


        </v-chip>





        <v-chip size="x-small" color="success" variant="flat">


          <v-icon icon="mdi-clipboard-list" start size="small" />


          {{ crew.tasks?.length || 0 }}


        </v-chip>





        <v-chip


          v-if="crew.memory?.enabled"


          size="x-small"


          variant="outlined"


          color="purple"


        >


          <v-icon icon="mdi-brain" start size="small" />


          {{ $t('agent.crews.card.memory') }}


        </v-chip>





        <v-chip


          v-if="crew.cache?.enabled"


          size="x-small"


          variant="outlined"


          color="info"


        >


          <v-icon icon="mdi-database" start size="small" />


          {{ $t('agent.crews.card.cache') }}


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


        color="success"


        @click="$emit('execute', crew)"


        :title="$t('agent.crews.card.execute')"


      >


        <v-icon icon="mdi-play" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="primary"


        @click="$emit('edit', crew)"


        :title="$t('agent.crews.card.edit')"


      >


        <v-icon icon="mdi-pencil" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="default"


        @click="$emit('copy', crew)"


        :title="$t('agent.crews.card.copy')"


      >


        <v-icon icon="mdi-content-copy" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="error"


        @click="$emit('delete', crew)"


        :title="$t('agent.crews.card.delete')"


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


  crew: any;


}>();





const emit = defineEmits<{


  (e: 'execute', crew: any): void;


  (e: 'edit', crew: any): void;


  (e: 'copy', crew: any): void;


  (e: 'delete', crew: any): void;


}>();





const { t } = useI18n();





// 计算属性


const processColor = computed(() => {


  return props.crew.process === 'hierarchical' ? 'warning' : 'primary';


});





const processLabel = computed(() => {
  return props.crew.process === 'hierarchical'
    ? t('agent.crews.process.hierarchical')
    : t('agent.crews.process.sequential');
});


</script>





<style scoped>


.crew-card {


  height: 100%;


  display: flex;


  flex-direction: column;


  transition: all 0.3s ease;


}





.crew-card:hover {


  transform: translateY(-2px);


  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);


}





.description-text {


  display: -webkit-box;


  -webkit-line-clamp: 2;


  -webkit-box-orient: vertical;


  overflow: hidden;


  min-height: 40px;


}





.agent-avatar {


  cursor: pointer;


  transition: transform 0.2s ease;


}





.agent-avatar:hover {


  transform: scale(1.1);


}





.v-card-actions {


  margin-top: auto;


}


</style>


