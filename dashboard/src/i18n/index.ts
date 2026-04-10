/**
 * Vue I18n Configuration
 * 为 agent 模块提供 vue-i18n 支持
 */

import { createI18n } from 'vue-i18n';
import { getExtensionI18n } from '../extensions';

// 导入静态翻译文件（agent 模块）
import zhCNAgentSkills from './locales/zh-CN/features/agent-skills.json';
import zhCNAgentTools from './locales/zh-CN/features/agent-tools.json';
import zhCNAgentAgents from './locales/zh-CN/features/agent-agents.json';
import enUSAgentSkills from './locales/en-US/features/agent-skills.json';
import enUSAgentTools from './locales/en-US/features/agent-tools.json';
import enUSAgentAgents from './locales/en-US/features/agent-agents.json';
import ruRUAgentSkills from './locales/ru-RU/features/agent-skills.json';
import ruRUAgentTools from './locales/ru-RU/features/agent-tools.json';
import ruRUAgentAgents from './locales/ru-RU/features/agent-agents.json';

// 创建 i18n 实例（初始为空消息）
export const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: 'zh-CN', // 默认语言
  fallbackLocale: 'zh-CN', // 回退语言
  messages: {
    'zh-CN': {},
    'en-US': {},
    'ru-RU': {},
  },
  missingWarn: false, // 禁用缺失警告
  fallbackWarn: false, // 禁用回退警告
  silentTranslationWarn: true, // 静默翻译警告
});

// 加载 i18n 消息的函数 - 在扩展注册后调用
export function loadI18nMessages() {
  // 加载静态翻译（agent 模块）
  // 注意：需要保持 agent 命名空间，因为页面使用 $t('agent.skills.xxx')
  const staticTranslations = {
    'zh-CN': {
      agent: {
        ...(zhCNAgentSkills as any).agent,
        ...(zhCNAgentTools as any).agent,
        ...(zhCNAgentAgents as any).agent,
      }
    },
    'en-US': {
      agent: {
        ...(enUSAgentSkills as any).agent,
        ...(enUSAgentTools as any).agent,
        ...(enUSAgentAgents as any).agent,
      }
    },
    'ru-RU': {
      agent: {
        ...(ruRUAgentSkills as any).agent,
        ...(ruRUAgentTools as any).agent,
        ...(ruRUAgentAgents as any).agent,
      }
    }
  };

  console.log('[Vue I18n] Loading static translations:', staticTranslations);

  // 先加载静态翻译
  (['zh-CN', 'en-US', 'ru-RU'] as const).forEach((locale) => {
    const localeData = staticTranslations[locale];
    if (localeData) {
      const currentMessages = i18n.global.getLocaleMessage(locale) || {};
      const mergedMessages = deepMerge(currentMessages, localeData);
      i18n.global.setLocaleMessage(locale, mergedMessages);
    }
  });

  // 再加载扩展 i18n（覆盖静态翻译）
  const extI18n: any = getExtensionI18n();
  console.log('[Vue I18n] Loading messages from extension:', extI18n);
  
  if (extI18n) {
    ['zh-CN', 'en-US', 'ru-RU'].forEach((locale) => {
      const localeData = extI18n[locale];
      if (localeData) {
        const currentMessages = i18n.global.getLocaleMessage(locale) || {};
        const mergedMessages = deepMerge(currentMessages, localeData);
        i18n.global.setLocaleMessage(locale, mergedMessages);
        console.log(`[Vue I18n] Loaded messages for ${locale}`, mergedMessages);
      }
    });
  }
}

// 深度合并对象
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

// 立即尝试加载（如果扩展已注册）
loadI18nMessages();

export default i18n;
