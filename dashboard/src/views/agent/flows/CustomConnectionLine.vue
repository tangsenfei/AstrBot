<template>
  <g>
    <path
      :d="`M${sourceX},${sourceY} C${sourceX} ${sourceY + cyOffset},${targetX} ${targetY - cyOffset},${targetX},${targetY}`"
      class="animated-connection-line"
      fill="none"
      stroke="#6366f1"
      stroke-width="2"
      stroke-dasharray="8 4"
    />
    <circle :cx="targetX" :cy="targetY" r="4" fill="#6366f1" class="connection-dot" />
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition: any;
  targetPosition: any;
}>();

const cyOffset = computed(() => {
  return Math.abs(props.targetY - props.sourceY) / 2;
});
</script>

<style scoped>
.animated-connection-line {
  animation: dash 0.5s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -12;
  }
}

.connection-dot {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { r: 4; opacity: 1; }
  50% { r: 6; opacity: 0.7; }
}
</style>
