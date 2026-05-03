<template>
  <v-container fluid class="pa-6">
    <v-card class="mb-4">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-toolbox" class="mr-2" />
        工具技能
      </v-card-title>
      <v-card-subtitle>
        统一管理工具管理、智能体技能、MCP 服务器、技能包和指令函数
      </v-card-subtitle>
    </v-card>

    <v-card>
      <v-tabs v-model="activeTab" color="primary" class="border-b">
        <v-tab value="agent-tools">工具管理</v-tab>
        <v-tab value="agent-skills">智能体技能</v-tab>
        <v-tab value="mcp">MCP 服务器</v-tab>
        <v-tab value="skill-packs">技能包</v-tab>
        <v-tab value="components">指令与函数</v-tab>
      </v-tabs>

      <v-window v-model="activeTab">
        <v-window-item value="agent-tools">
          <AgentToolsTab />
        </v-window-item>
        <v-window-item value="agent-skills">
          <AgentSkillsTab />
        </v-window-item>
        <v-window-item value="mcp">
          <McpServersSection />
        </v-window-item>
        <v-window-item value="skill-packs">
          <SkillsSection />
        </v-window-item>
        <v-window-item value="components">
          <ComponentPanel />
        </v-window-item>
      </v-window>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AgentToolsTab from './tool-skills/AgentToolsTab.vue'
import AgentSkillsTab from './tool-skills/AgentSkillsTab.vue'
import McpServersSection from '@/components/extension/McpServersSection.vue'
import SkillsSection from '@/components/extension/SkillsSection.vue'
import ComponentPanel from '@/components/extension/componentPanel/index.vue'

const activeTab = ref('agent-tools')
</script>
