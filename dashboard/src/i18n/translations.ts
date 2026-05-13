// 静态导入所有翻译文件
// 这种方式确保构建时所有翻译都会被正确打包

// 中文翻译
import zhCNCommon from './locales/zh-CN/core/common.json';
import zhCNActions from './locales/zh-CN/core/actions.json';
import zhCNStatus from './locales/zh-CN/core/status.json';
import zhCNNavigation from './locales/zh-CN/core/navigation.json';
import zhCNHeader from './locales/zh-CN/core/header.json';
import zhCNShared from './locales/zh-CN/core/shared.json';

import zhCNChat from './locales/zh-CN/features/chat.json';
import zhCNExtension from './locales/zh-CN/features/extension.json';
import zhCNConversation from './locales/zh-CN/features/conversation.json';
import zhCNSessionManagement from './locales/zh-CN/features/session-management.json';
import zhCNToolUse from './locales/zh-CN/features/tool-use.json';
import zhCNProvider from './locales/zh-CN/features/provider.json';
import zhCNPlatform from './locales/zh-CN/features/platform.json';
import zhCNConfig from './locales/zh-CN/features/config.json';
import zhCNConfigMetadata from './locales/zh-CN/features/config-metadata.json';
import zhCNConsole from './locales/zh-CN/features/console.json';
import zhCNTrace from './locales/zh-CN/features/trace.json';
import zhCNSettings from './locales/zh-CN/features/settings.json';
import zhCNAuth from './locales/zh-CN/features/auth.json';
import zhCNChart from './locales/zh-CN/features/chart.json';
import zhCNDashboard from './locales/zh-CN/features/dashboard.json';
import zhCNCron from './locales/zh-CN/features/cron.json';
import zhCNStats from './locales/zh-CN/features/stats.json';
import zhCNKnowledgeBaseIndex from './locales/zh-CN/features/knowledge-base/index.json';
import zhCNKnowledgeBaseDetail from './locales/zh-CN/features/knowledge-base/detail.json';
import zhCNKnowledgeBaseDocument from './locales/zh-CN/features/knowledge-base/document.json';
import zhCNPersona from './locales/zh-CN/features/persona.json';
import zhCNMigration from './locales/zh-CN/features/migration.json';
import zhCNCommand from './locales/zh-CN/features/command.json';
import zhCNSubagent from './locales/zh-CN/features/subagent.json';
import zhCNAgentSkills from './locales/zh-CN/features/agent-skills.json';
import zhCNAgentTools from './locales/zh-CN/features/agent-tools.json';
import zhCNToolProvider from './locales/zh-CN/features/tool-provider.json';
import zhCNMemoryManagement from './locales/zh-CN/features/memory-management.json';
import zhCNEvolutionCenter from './locales/zh-CN/features/evolution-center.json';
import zhCNWorkConfig from './locales/zh-CN/features/work-config.json';
import zhCNNicebotNavigation from './locales/zh-CN/features/nicebot-navigation.json';

import zhCNAgentNavigation from './locales/zh-CN/agent/navigation.json';
import zhCNAgentExpertTeam from './locales/zh-CN/agent/expert-team.json';
import zhCNAgentKnowledge from './locales/zh-CN/agent/knowledge.json';
import zhCNAgentAgents from './locales/zh-CN/agent/agents.json';
import zhCNAgentToolsModule from './locales/zh-CN/agent/tools.json';
import zhCNAgentSkillsModule from './locales/zh-CN/agent/skills.json';
import zhCNAgentCrews from './locales/zh-CN/agent/crews.json';
import zhCNAgentFlows from './locales/zh-CN/agent/flows.json';

import zhCNErrors from './locales/zh-CN/messages/errors.json';
import zhCNSuccess from './locales/zh-CN/messages/success.json';
import zhCNValidation from './locales/zh-CN/messages/validation.json';

// English translation
import enUSCommon from './locales/en-US/core/common.json';
import enUSActions from './locales/en-US/core/actions.json';
import enUSStatus from './locales/en-US/core/status.json';
import enUSNavigation from './locales/en-US/core/navigation.json';
import enUSHeader from './locales/en-US/core/header.json';
import enUSShared from './locales/en-US/core/shared.json';

import enUSChat from './locales/en-US/features/chat.json';
import enUSExtension from './locales/en-US/features/extension.json';
import enUSConversation from './locales/en-US/features/conversation.json';
import enUSSessionManagement from './locales/en-US/features/session-management.json';
import enUSToolUse from './locales/en-US/features/tool-use.json';
import enUSProvider from './locales/en-US/features/provider.json';
import enUSPlatform from './locales/en-US/features/platform.json';
import enUSConfig from './locales/en-US/features/config.json';
import enUSConfigMetadata from './locales/en-US/features/config-metadata.json';
import enUSConsole from './locales/en-US/features/console.json';
import enUSTrace from './locales/en-US/features/trace.json';
import enUSSettings from './locales/en-US/features/settings.json';
import enUSAuth from './locales/en-US/features/auth.json';
import enUSChart from './locales/en-US/features/chart.json';
import enUSDashboard from './locales/en-US/features/dashboard.json';
import enUSCron from './locales/en-US/features/cron.json';
import enUSStats from './locales/en-US/features/stats.json';
import enUSKnowledgeBaseIndex from './locales/en-US/features/knowledge-base/index.json';
import enUSKnowledgeBaseDetail from './locales/en-US/features/knowledge-base/detail.json';
import enUSKnowledgeBaseDocument from './locales/en-US/features/knowledge-base/document.json';
import enUSPersona from './locales/en-US/features/persona.json';
import enUSMigration from './locales/en-US/features/migration.json';
import enUSCommand from './locales/en-US/features/command.json';
import enUSSubagent from './locales/en-US/features/subagent.json';
import enUSAgentSkills from './locales/en-US/features/agent-skills.json';
import enUSAgentTools from './locales/en-US/features/agent-tools.json';
import enUSToolProvider from './locales/en-US/features/tool-provider.json';
import enUSMemoryManagement from './locales/en-US/features/memory-management.json';
import enUSEvolutionCenter from './locales/en-US/features/evolution-center.json';
import enUSWorkConfig from './locales/en-US/features/work-config.json';
import enUSNicebotNavigation from './locales/en-US/features/nicebot-navigation.json';

import enUSAgentNavigation from './locales/en-US/agent/navigation.json';
import enUSAgentExpertTeam from './locales/en-US/agent/expert-team.json';
import enUSAgentKnowledge from './locales/en-US/agent/knowledge.json';
import enUSAgentAgents from './locales/en-US/agent/agents.json';
import enUSAgentToolsModule from './locales/en-US/agent/tools.json';
import enUSAgentSkillsModule from './locales/en-US/agent/skills.json';
import enUSAgentCrews from './locales/en-US/agent/crews.json';
import enUSAgentFlows from './locales/en-US/agent/flows.json';

import enUSErrors from './locales/en-US/messages/errors.json';
import enUSSuccess from './locales/en-US/messages/success.json';
import enUSValidation from './locales/en-US/messages/validation.json';

// Russian translation
import ruRUCommon from './locales/ru-RU/core/common.json';
import ruRUActions from './locales/ru-RU/core/actions.json';
import ruRUStatus from './locales/ru-RU/core/status.json';
import ruRUNavigation from './locales/ru-RU/core/navigation.json';
import ruRUHeader from './locales/ru-RU/core/header.json';
import ruRUShared from './locales/ru-RU/core/shared.json';

import ruRUChat from './locales/ru-RU/features/chat.json';
import ruRUExtension from './locales/ru-RU/features/extension.json';
import ruRUConversation from './locales/ru-RU/features/conversation.json';
import ruRUSessionManagement from './locales/ru-RU/features/session-management.json';
import ruRUToolUse from './locales/ru-RU/features/tool-use.json';
import ruRUProvider from './locales/ru-RU/features/provider.json';
import ruRUPlatform from './locales/ru-RU/features/platform.json';
import ruRUConfig from './locales/ru-RU/features/config.json';
import ruRUConfigMetadata from './locales/ru-RU/features/config-metadata.json';
import ruRUConsole from './locales/ru-RU/features/console.json';
import ruRUTrace from './locales/ru-RU/features/trace.json';
import ruRUSettings from './locales/ru-RU/features/settings.json';
import ruRUAuth from './locales/ru-RU/features/auth.json';
import ruRUChart from './locales/ru-RU/features/chart.json';
import ruRUDashboard from './locales/ru-RU/features/dashboard.json';
import ruRUCron from './locales/ru-RU/features/cron.json';
import ruRUStats from './locales/ru-RU/features/stats.json';
import ruRUKnowledgeBaseIndex from './locales/ru-RU/features/knowledge-base/index.json';
import ruRUKnowledgeBaseDetail from './locales/ru-RU/features/knowledge-base/detail.json';
import ruRUKnowledgeBaseDocument from './locales/ru-RU/features/knowledge-base/document.json';
import ruRUPersona from './locales/ru-RU/features/persona.json';
import ruRUMigration from './locales/ru-RU/features/migration.json';
import ruRUCommand from './locales/ru-RU/features/command.json';
import ruRUSubagent from './locales/ru-RU/features/subagent.json';
import ruRUAgentSkills from './locales/ru-RU/features/agent-skills.json';
import ruRUAgentTools from './locales/ru-RU/features/agent-tools.json';
import ruRUToolProvider from './locales/ru-RU/features/tool-provider.json';
import ruRUMemoryManagement from './locales/ru-RU/features/memory-management.json';
import ruRUEvolutionCenter from './locales/ru-RU/features/evolution-center.json';
import ruRUWorkConfig from './locales/ru-RU/features/work-config.json';
import ruRUNicebotNavigation from './locales/ru-RU/features/nicebot-navigation.json';

import ruRUAgentNavigation from './locales/ru-RU/agent/navigation.json';
import ruRUAgentExpertTeam from './locales/ru-RU/agent/expert-team.json';
import ruRUAgentKnowledge from './locales/ru-RU/agent/knowledge.json';
import ruRUAgentAgents from './locales/ru-RU/agent/agents.json';
import ruRUAgentToolsModule from './locales/ru-RU/agent/tools.json';
import ruRUAgentSkillsModule from './locales/ru-RU/agent/skills.json';
import ruRUAgentCrews from './locales/ru-RU/agent/crews.json';
import ruRUAgentFlows from './locales/ru-RU/agent/flows.json';

import ruRUErrors from './locales/ru-RU/messages/errors.json';
import ruRUSuccess from './locales/ru-RU/messages/success.json';
import ruRUValidation from './locales/ru-RU/messages/validation.json';

// 组装翻译对象
export const translations = {
  'zh-CN': {
    core: {
      common: zhCNCommon,
      actions: zhCNActions,
      status: zhCNStatus,
      navigation: zhCNNavigation,
      header: zhCNHeader,
      shared: zhCNShared
    },
    features: {
      chat: zhCNChat,
      extension: zhCNExtension,
      conversation: zhCNConversation,
      'session-management': zhCNSessionManagement,
      tooluse: zhCNToolUse,
      provider: zhCNProvider,
      platform: zhCNPlatform,
      config: zhCNConfig,
      'config-metadata': zhCNConfigMetadata,
      console: zhCNConsole,
      trace: zhCNTrace,
      settings: zhCNSettings,
      auth: zhCNAuth,
      chart: zhCNChart,
      dashboard: zhCNDashboard,
      cron: zhCNCron,
      stats: zhCNStats,
      'knowledge-base': {
        index: zhCNKnowledgeBaseIndex,
        detail: zhCNKnowledgeBaseDetail,
        document: zhCNKnowledgeBaseDocument
      },
      persona: zhCNPersona,
      migration: zhCNMigration,
      command: zhCNCommand,
      subagent: zhCNSubagent,
      'tool-provider': zhCNToolProvider,
      'memory-management': zhCNMemoryManagement,
      'evolution-center': zhCNEvolutionCenter,
      'work-config': zhCNWorkConfig
    },
    nicebot: {
      navigation: zhCNNicebotNavigation,
      evolution_center: zhCNEvolutionCenter,
      memory_management: zhCNMemoryManagement
    },
    messages: {
      errors: zhCNErrors,
      success: zhCNSuccess,
      validation: zhCNValidation
    },
    agent: {
      ...(zhCNAgentSkills as any).agent,
      ...(zhCNAgentTools as any).agent,
      navigation: zhCNAgentNavigation,
      expertTeam: zhCNAgentExpertTeam,
      knowledge: zhCNAgentKnowledge,
      agents: zhCNAgentAgents,
      tools: zhCNAgentToolsModule,
      skills: zhCNAgentSkillsModule,
      crews: zhCNAgentCrews,
      flows: zhCNAgentFlows
    }
  },
  'en-US': {
    core: {
      common: enUSCommon,
      actions: enUSActions,
      status: enUSStatus,
      navigation: enUSNavigation,
      header: enUSHeader,
      shared: enUSShared
    },
    features: {
      chat: enUSChat,
      extension: enUSExtension,
      conversation: enUSConversation,
      'session-management': enUSSessionManagement,
      tooluse: enUSToolUse,
      provider: enUSProvider,
      platform: enUSPlatform,
      config: enUSConfig,
      'config-metadata': enUSConfigMetadata,
      console: enUSConsole,
      trace: enUSTrace,
      settings: enUSSettings,
      auth: enUSAuth,
      chart: enUSChart,
      dashboard: enUSDashboard,
      cron: enUSCron,
      stats: enUSStats,
      'knowledge-base': {
        index: enUSKnowledgeBaseIndex,
        detail: enUSKnowledgeBaseDetail,
        document: enUSKnowledgeBaseDocument
      },
      persona: enUSPersona,
      migration: enUSMigration,
      command: enUSCommand,
      subagent: enUSSubagent,
      'tool-provider': enUSToolProvider,
      'memory-management': enUSMemoryManagement,
      'evolution-center': enUSEvolutionCenter,
      'work-config': enUSWorkConfig
    },
    nicebot: {
      navigation: enUSNicebotNavigation,
      evolution_center: enUSEvolutionCenter,
      memory_management: enUSMemoryManagement
    },
    messages: {
      errors: enUSErrors,
      success: enUSSuccess,
      validation: enUSValidation
    },
    agent: {
      ...(enUSAgentSkills as any).agent,
      ...(enUSAgentTools as any).agent,
      navigation: enUSAgentNavigation,
      expertTeam: enUSAgentExpertTeam,
      knowledge: enUSAgentKnowledge,
      agents: enUSAgentAgents,
      tools: enUSAgentToolsModule,
      skills: enUSAgentSkillsModule,
      crews: enUSAgentCrews,
      flows: enUSAgentFlows
    }
  },
  'ru-RU': {
    core: {
      common: ruRUCommon,
      actions: ruRUActions,
      status: ruRUStatus,
      navigation: ruRUNavigation,
      header: ruRUHeader,
      shared: ruRUShared
    },
    features: {
      chat: ruRUChat,
      extension: ruRUExtension,
      conversation: ruRUConversation,
      'session-management': ruRUSessionManagement,
      tooluse: ruRUToolUse,
      provider: ruRUProvider,
      platform: ruRUPlatform,
      config: ruRUConfig,
      'config-metadata': ruRUConfigMetadata,
      console: ruRUConsole,
      trace: ruRUTrace,
      settings: ruRUSettings,
      auth: ruRUAuth,
      chart: ruRUChart,
      dashboard: ruRUDashboard,
      cron: ruRUCron,
      stats: ruRUStats,
      'knowledge-base': {
        index: ruRUKnowledgeBaseIndex,
        detail: ruRUKnowledgeBaseDetail,
        document: ruRUKnowledgeBaseDocument
      },
      persona: ruRUPersona,
      migration: ruRUMigration,
      command: ruRUCommand,
      subagent: ruRUSubagent,
      'tool-provider': ruRUToolProvider,
      'memory-management': ruRUMemoryManagement,
      'evolution-center': ruRUEvolutionCenter,
      'work-config': ruRUWorkConfig
    },
    nicebot: {
      navigation: ruRUNicebotNavigation,
      evolution_center: ruRUEvolutionCenter,
      memory_management: ruRUMemoryManagement
    },
    messages: {
      errors: ruRUErrors,
      success: ruRUSuccess,
      validation: ruRUValidation
    },
    agent: {
      ...(ruRUAgentSkills as any).agent,
      ...(ruRUAgentTools as any).agent,
      navigation: ruRUAgentNavigation,
      expertTeam: ruRUAgentExpertTeam,
      knowledge: ruRUAgentKnowledge,
      agents: ruRUAgentAgents,
      tools: ruRUAgentToolsModule,
      skills: ruRUAgentSkillsModule,
      crews: ruRUAgentCrews,
      flows: ruRUAgentFlows
    }
  }
};

export type TranslationData = typeof translations; 
