<template>


  <v-card


    class="skill-card"


    hover


  >


    <v-card-text class="pb-2">


      <!-- 标题和版-->


      <div class="d-flex align-start justify-space-between mb-2">


        <div class="flex-grow-1">


          <div class="text-h6 text-truncate" :title="skill.name">


            {{ skill.name }}


          </div>


          <div class="d-flex align-center mt-1">


            <v-chip


              :color="categoryColor"


              size="x-small"


              class="mr-2"


            >


              {{ categoryLabel }}


            </v-chip>


            <v-chip


              v-if="skill.version"


              size="x-small"


              variant="outlined"


            >


              v{{ skill.version }}


            </v-chip>


          </div>


        </div>


        <v-icon


          :icon="disclosureIcon"


          :color="disclosureColor"


          size="small"


          class="ml-2"


        />


      </div>





      <!-- 描述 -->


      <p class="text-body-2 text-grey-darken-1 mb-3 description-text">


        {{ skill.description || $t('agent.skills.card.noDescription') }}


      </p>





      <!-- 渐进式披露级-->


      <div class="d-flex align-center mb-2">


        <v-icon icon="mdi-eye" size="small" class="mr-1" />


        <span class="text-caption text-grey">


          {{ $t('agent.skills.card.disclosureLevel') }}: {{ disclosureLabel }}


        </span>


      </div>





      <!-- 预批准工具数-->


      <div v-if="preapprovedToolsCount > 0" class="d-flex align-center mb-2">


        <v-icon icon="mdi-check-circle" size="small" class="mr-1" color="success" />


        <span class="text-caption text-grey">


          {{ $t('agent.skills.card.preapprovedTools', { count: preapprovedToolsCount }) }}


        </span>


      </div>





      <!-- 工作流步骤数 -->


      <div v-if="workflowStepsCount > 0" class="d-flex align-center mb-2">


        <v-icon icon="mdi-flowchart" size="small" class="mr-1" color="info" />


        <span class="text-caption text-grey">


          {{ $t('agent.skills.card.workflow') }}: {{ workflowStepsCount }} {{ $t('agent.workflow.steps') }}


        </span>


      </div>





      <!-- 标签 -->


      <div v-if="skill.tags && skill.tags.length > 0" class="mb-3">


        <v-chip


          v-for="tag in skill.tags.slice(0, 3)"


          :key="tag"


          size="x-small"


          variant="outlined"


          class="mr-1 mb-1"


        >


          {{ tag }}


        </v-chip>


        <v-chip


          v-if="skill.tags.length > 3"


          size="x-small"


          variant="outlined"


          class="mr-1 mb-1"


        >


          +{{ skill.tags.length - 3 }}


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


        @click="$emit('test', skill)"


        :title="$t('agent.skills.card.test')"


      >


        <v-icon icon="mdi-bug-play" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="primary"


        @click="$emit('edit', skill)"


        :title="$t('agent.skills.card.edit')"


      >


        <v-icon icon="mdi-pencil" />


      </v-btn>


      <v-btn


        icon


        size="small"


        variant="text"


        color="error"


        @click="$emit('delete', skill)"


        :title="$t('agent.skills.card.delete')"


      >


        <v-icon icon="mdi-delete" />


      </v-btn>


      <v-spacer />


      <v-btn


        icon


        size="small"


        variant="text"


        @click="showDetails = !showDetails"


      >


        <v-icon :icon="showDetails ? 'mdi-chevron-up' : 'mdi-chevron-down'" />


      </v-btn>


    </v-card-actions>





    <!-- 详情展开 -->


    <v-expand-transition>


      <div v-show="showDetails">


        <v-divider />


        <v-card-text class="pt-2">


          <!-- 预批准工具列-->


          <div v-if="skill.preapproved_tools && skill.preapproved_tools.length > 0">


            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.editor.preapprovedTools') }}</div>


            <v-list density="compact" class="bg-grey-lighten-4 rounded">


              <v-list-item


                v-for="tool in skill.preapproved_tools"


                :key="tool"


                class="px-2"


              >


                <template v-slot:prepend>


                  <v-icon icon="mdi-check" color="success" size="small" class="mr-2" />


                </template>


                <v-list-item-title class="text-body-2">{{ tool }}</v-list-item-title>


              </v-list-item>


            </v-list>


          </div>





          <!-- 工作流步-->


          <div v-if="skill.workflow && skill.workflow.steps && skill.workflow.steps.length > 0" class="mt-3">


            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.card.workflow') }}</div>


            <v-timeline density="compact" side="end">


              <v-timeline-item


                v-for="(step, index) in skill.workflow.steps"


                :key="index"


                size="small"


              >


                <template v-slot:opposite>


                  <span class="text-caption text-grey">{{ index + 1 }}</span>


                </template>


                <div class="text-body-2">{{ step.name }}</div>


                <div v-if="step.description" class="text-caption text-grey">


                  {{ step.description }}


                </div>


              </v-timeline-item>


            </v-timeline>


          </div>





          <!-- 元数据-->


          <div v-if="skill.metadata && Object.keys(skill.metadata).length > 0" class="mt-3">


            <div class="text-subtitle-2 mb-2">{{ $t('agent.skills.editor.metadata') }}</div>


            <v-list density="compact" class="bg-grey-lighten-4 rounded">


              <v-list-item


                v-for="(value, key) in skill.metadata"


                :key="key"


                class="px-2"


              >


                <v-list-item-title class="text-body-2">{{ key }}</v-list-item-title>


                <v-list-item-subtitle class="text-caption">{{ value }}</v-list-item-subtitle>


              </v-list-item>


            </v-list>


          </div>


        </v-card-text>


      </div>


    </v-expand-transition>


  </v-card>


</template>





<script setup lang="ts">


import { ref, computed } from 'vue';


import { useI18n } from 'vue-i18n';





const props = defineProps<{


  skill: any;


}>();





const emit = defineEmits<{


  (e: 'edit', skill: any): void;


  (e: 'test', skill: any): void;


  (e: 'delete', skill: any): void;


}>();





const { t } = useI18n();


const showDetails = ref(false);





// 计算属性


const categoryColor = computed(() => {


  switch (props.skill.category) {


    case 'general':


      return 'primary';


    case 'programming':


      return 'success';


    case 'analysis':


      return 'warning';


    case 'creative':


      return 'purple';


    case 'other':


    default:


      return 'grey';


  }


});





const categoryLabel = computed(() => {


  return t(`agent.skills.categories.${props.skill.category}`) || props.skill.category;


});





const disclosureColor = computed(() => {


  switch (props.skill.disclosure_level) {


    case 'metadata':


      return 'grey';


    case 'instructions':


      return 'warning';


    case 'resources':


      return 'success';


    default:


      return 'grey';


  }


});





const disclosureIcon = computed(() => {


  switch (props.skill.disclosure_level) {


    case 'metadata':


      return 'mdi-database';


    case 'instructions':


      return 'mdi-file-document';


    case 'resources':


      return 'mdi-folder-open';


    default:


      return 'mdi-help-circle';


  }


});





const disclosureLabel = computed(() => {


  return t(`agent.skills.disclosureLevels.${props.skill.disclosure_level}`) || props.skill.disclosure_level;


});





const preapprovedToolsCount = computed(() => {


  return props.skill.preapproved_tools?.length || 0;


});





const workflowStepsCount = computed(() => {


  return props.skill.workflow?.steps?.length || 0;


});


</script>





<style scoped>


.skill-card {


  height: 100%;


  display: flex;


  flex-direction: column;


  transition: all 0.3s ease;


}





.skill-card:hover {


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





.v-card-actions {


  margin-top: auto;


}


</style>


