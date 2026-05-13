<template>
  <div class="agent-status-bar">
    <div class="status-left">
      <v-chip size="small" :color="connected ? 'success' : 'default'" variant="tonal">
        <v-icon start size="14">{{ connected ? 'mdi-check-circle-outline' : 'mdi-circle-outline' }}</v-icon>
        {{ connected ? '在线' : '未连接' }}
      </v-chip>
      <span class="status-meta">{{ clientName }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  connected: boolean;
  clientName: string;
}>();
</script>

<style scoped>
.agent-status-bar {
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px max(24px, calc((100% - 980px) / 2));
  border-bottom: 1px solid rgba(var(--v-border-color), 0.12);
  background: rgb(var(--v-theme-surface));
}

.status-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.status-meta {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 13px;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .agent-status-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
