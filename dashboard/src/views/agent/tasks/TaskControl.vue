<template>

  <v-card>

    <v-card-title>

      <v-icon icon="mdi-cog" class="mr-2" />

      {{ $t('agent.tasks.control.title') }}

    </v-card-title>

    <v-card-text>

      <!-- 运行中状-->

      <div v-if="task.status === 'running'" class="d-flex flex-column ga-2">

        <v-btn

          color="warning"

          variant="outlined"

          block

          @click="$emit('pause')"

        >

          <v-icon start icon="mdi-pause" />

          {{ $t('agent.tasks.control.pause') }}

        </v-btn>

        <v-btn

          color="error"

          variant="outlined"

          block

          @click="$emit('cancel')"

        >

          <v-icon start icon="mdi-stop" />

          {{ $t('agent.tasks.control.cancel') }}

        </v-btn>

      </div>



      <!-- 已暂停状-->

      <div v-else-if="task.status === 'paused'" class="d-flex flex-column ga-2">

        <v-btn

          color="success"

          variant="outlined"

          block

          @click="$emit('resume')"

        >

          <v-icon start icon="mdi-play" />

          {{ $t('agent.tasks.control.resume') }}

        </v-btn>

        <v-btn

          color="error"

          variant="outlined"

          block

          @click="$emit('cancel')"

        >

          <v-icon start icon="mdi-stop" />

          {{ $t('agent.tasks.control.cancel') }}

        </v-btn>

      </div>



      <!-- 等待反馈状-->

      <div v-else-if="task.status === 'waiting_feedback'" class="d-flex flex-column ga-2">

        <v-btn

          color="primary"

          variant="outlined"

          block

          @click="$emit('feedback')"

        >

          <v-icon start icon="mdi-message-reply" />

          {{ $t('agent.tasks.control.provideFeedback') }}

        </v-btn>

        <v-btn

          color="error"

          variant="outlined"

          block

          @click="$emit('cancel')"

        >

          <v-icon start icon="mdi-stop" />

          {{ $t('agent.tasks.control.cancel') }}

        </v-btn>

      </div>



      <!-- 失败状-->

      <div v-else-if="task.status === 'failed'" class="d-flex flex-column ga-2">

        <v-btn

          color="info"

          variant="outlined"

          block

          @click="$emit('retry')"

        >

          <v-icon start icon="mdi-refresh" />

          {{ $t('agent.tasks.control.retry') }}

        </v-btn>

      </div>



      <!-- 已取消状-->

      <div v-else-if="task.status === 'cancelled'" class="d-flex flex-column ga-2">

        <v-btn

          color="info"

          variant="outlined"

          block

          @click="$emit('retry')"

        >

          <v-icon start icon="mdi-refresh" />

          {{ $t('agent.tasks.control.retry') }}

        </v-btn>

      </div>



      <!-- 待执行状-->

      <div v-else-if="task.status === 'pending'" class="d-flex flex-column ga-2">

        <v-alert type="info" variant="tonal" density="compact">

          {{ $t('agent.tasks.control.pendingHint') }}

        </v-alert>

      </div>



      <!-- 已完成状-->

      <div v-else-if="task.status === 'completed'" class="d-flex flex-column ga-2">

        <v-alert type="success" variant="tonal" density="compact">

          {{ $t('agent.tasks.control.completedHint') }}

        </v-alert>

      </div>



      <!-- 未知状-->

      <div v-else class="d-flex flex-column ga-2">

        <v-alert type="warning" variant="tonal" density="compact">

          {{ $t('agent.tasks.control.unknownStatus') }}

        </v-alert>

      </div>

    </v-card-text>

  </v-card>

</template>



<script setup lang="ts">

defineProps<{

  task: {

    id: string;

    status: string;

  };

}>();



defineEmits<{

  pause: [];

  resume: [];

  cancel: [];

  retry: [];

  feedback: [];

}>();

</script>



<style scoped>

.v-card {

  border-radius: 12px;

}

</style>

