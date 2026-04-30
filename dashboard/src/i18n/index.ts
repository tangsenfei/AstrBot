import { createI18n } from 'vue-i18n';

import zhCNAgentSkills from './locales/zh-CN/features/agent-skills.json';
import zhCNAgentTools from './locales/zh-CN/features/agent-tools.json';
import zhCNAgentAgents from './locales/zh-CN/features/agent-agents.json';
import enUSAgentSkills from './locales/en-US/features/agent-skills.json';
import enUSAgentTools from './locales/en-US/features/agent-tools.json';
import enUSAgentAgents from './locales/en-US/features/agent-agents.json';
import ruRUAgentSkills from './locales/ru-RU/features/agent-skills.json';
import ruRUAgentTools from './locales/ru-RU/features/agent-tools.json';
import ruRUAgentAgents from './locales/ru-RU/features/agent-agents.json';

import zhCNAgentNavigation from './locales/zh-CN/agent/navigation.json';
import zhCNAgentExpertTeam from './locales/zh-CN/agent/expert-team.json';
import zhCNAgentKnowledge from './locales/zh-CN/agent/knowledge.json';
import zhCNAgentAgentsModule from './locales/zh-CN/agent/agents.json';
import zhCNAgentToolsModule from './locales/zh-CN/agent/tools.json';
import zhCNAgentTasks from './locales/zh-CN/agent/tasks.json';
import zhCNAgentSkillsModule from './locales/zh-CN/agent/skills.json';
import zhCNAgentCrews from './locales/zh-CN/agent/crews.json';
import zhCNAgentRoundtables from './locales/zh-CN/agent/roundtables.json';
import zhCNAgentFlows from './locales/zh-CN/agent/flows.json';

import enUSAgentNavigation from './locales/en-US/agent/navigation.json';
import enUSAgentExpertTeam from './locales/en-US/agent/expert-team.json';
import enUSAgentKnowledge from './locales/en-US/agent/knowledge.json';
import enUSAgentAgentsModule from './locales/en-US/agent/agents.json';
import enUSAgentToolsModule from './locales/en-US/agent/tools.json';
import enUSAgentTasks from './locales/en-US/agent/tasks.json';
import enUSAgentSkillsModule from './locales/en-US/agent/skills.json';
import enUSAgentCrews from './locales/en-US/agent/crews.json';
import enUSAgentRoundtables from './locales/en-US/agent/roundtables.json';
import enUSAgentFlows from './locales/en-US/agent/flows.json';

import ruRUAgentNavigation from './locales/ru-RU/agent/navigation.json';
import ruRUAgentExpertTeam from './locales/ru-RU/agent/expert-team.json';
import ruRUAgentKnowledge from './locales/ru-RU/agent/knowledge.json';
import ruRUAgentAgentsModule from './locales/ru-RU/agent/agents.json';
import ruRUAgentToolsModule from './locales/ru-RU/agent/tools.json';
import ruRUAgentTasks from './locales/ru-RU/agent/tasks.json';
import ruRUAgentSkillsModule from './locales/ru-RU/agent/skills.json';
import ruRUAgentCrews from './locales/ru-RU/agent/crews.json';
import ruRUAgentRoundtables from './locales/ru-RU/agent/roundtables.json';
import ruRUAgentFlows from './locales/ru-RU/agent/flows.json';

import zhCNEvolutionCenter from './locales/zh-CN/features/evolution-center.json';
import enUSEvolutionCenter from './locales/en-US/features/evolution-center.json';
import ruRUEvolutionCenter from './locales/ru-RU/features/evolution-center.json';
import zhCNNicebotNavigation from './locales/zh-CN/features/nicebot-navigation.json';
import enUSNicebotNavigation from './locales/en-US/features/nicebot-navigation.json';
import ruRUNicebotNavigation from './locales/ru-RU/features/nicebot-navigation.json';
import zhCNMemoryManagement from './locales/zh-CN/features/memory-management.json';
import enUSMemoryManagement from './locales/en-US/features/memory-management.json';
import ruRUMemoryManagement from './locales/ru-RU/features/memory-management.json';
import zhCNTaskManagement from './locales/zh-CN/features/task-management.json';
import enUSTaskManagement from './locales/en-US/features/task-management.json';
import ruRUTaskManagement from './locales/ru-RU/features/task-management.json';

export const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': {},
    'en-US': {},
    'ru-RU': {},
  },
  missingWarn: false,
  fallbackWarn: false,
  silentTranslationWarn: true,
});

export function loadI18nMessages() {
  const staticTranslations = {
    'zh-CN': {
      agent: {
        ...(zhCNAgentSkills as any).agent,
        ...(zhCNAgentTools as any).agent,
        ...(zhCNAgentAgents as any).agent,
        navigation: zhCNAgentNavigation,
        expertTeam: zhCNAgentExpertTeam,
        knowledge: zhCNAgentKnowledge,
        agents: zhCNAgentAgentsModule,
        tools: zhCNAgentToolsModule,
        tasks: zhCNAgentTasks,
        skills: zhCNAgentSkillsModule,
        crews: zhCNAgentCrews,
        roundtables: zhCNAgentRoundtables,
        flows: zhCNAgentFlows
      },
      nicebot: {
        evolution_center: zhCNEvolutionCenter,
        navigation: zhCNNicebotNavigation,
        memory_management: zhCNMemoryManagement,
        task_management: zhCNTaskManagement
      }
    },
    'en-US': {
      agent: {
        ...(enUSAgentSkills as any).agent,
        ...(enUSAgentTools as any).agent,
        ...(enUSAgentAgents as any).agent,
        navigation: enUSAgentNavigation,
        expertTeam: enUSAgentExpertTeam,
        knowledge: enUSAgentKnowledge,
        agents: enUSAgentAgentsModule,
        tools: enUSAgentToolsModule,
        tasks: enUSAgentTasks,
        skills: enUSAgentSkillsModule,
        crews: enUSAgentCrews,
        roundtables: enUSAgentRoundtables,
        flows: enUSAgentFlows
      },
      nicebot: {
        evolution_center: enUSEvolutionCenter,
        navigation: enUSNicebotNavigation,
        memory_management: enUSMemoryManagement,
        task_management: enUSTaskManagement
      }
    },
    'ru-RU': {
      agent: {
        ...(ruRUAgentSkills as any).agent,
        ...(ruRUAgentTools as any).agent,
        ...(ruRUAgentAgents as any).agent,
        navigation: ruRUAgentNavigation,
        expertTeam: ruRUAgentExpertTeam,
        knowledge: ruRUAgentKnowledge,
        agents: ruRUAgentAgentsModule,
        tools: ruRUAgentToolsModule,
        tasks: ruRUAgentTasks,
        skills: ruRUAgentSkillsModule,
        crews: ruRUAgentCrews,
        roundtables: ruRUAgentRoundtables,
        flows: ruRUAgentFlows
      },
      nicebot: {
        evolution_center: ruRUEvolutionCenter,
        navigation: ruRUNicebotNavigation,
        memory_management: ruRUMemoryManagement,
        task_management: ruRUTaskManagement
      }
    }
  };

  (['zh-CN', 'en-US', 'ru-RU'] as const).forEach((locale) => {
    const localeData = staticTranslations[locale];
    if (localeData) {
      const currentMessages = i18n.global.getLocaleMessage(locale) || {};
      const mergedMessages = deepMerge(currentMessages, localeData);
      i18n.global.setLocaleMessage(locale, mergedMessages);
    }
  });
}

function deepMerge(target: any, source: any): any {
  if (!source) return target;
  if (!target) return source;
  
  const result = { ...target };
  
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(result[key] || {}, source[key]);
    } else {
      result[key] = source[key];
    }
  }
  
  return result;
}

loadI18nMessages();

export default i18n;
