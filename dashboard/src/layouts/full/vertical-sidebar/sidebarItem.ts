export interface menu {
  header?: string;
  title?: string;
  icon?: string;
  to?: string;
  divider?: boolean;
  chip?: string;
  chipColor?: string;
  chipVariant?: string;
  chipIcon?: string;
  children?: menu[];
  disabled?: boolean;
  type?: string;
  subCaption?: string;
}

import { getExtensionSidebarItems, getSidebarInsert, getSidebarInserts } from '../../../extensions';

// 注意：这个文件现在包含i18n键值而不是直接的文本
// 在组件中使用时需要通过t()函数进行翻译
// 所有键名都使用 core.navigation.* 格式
const baseSidebarItem: menu[] = [
  {
    title: 'core.navigation.welcome',
    icon: 'mdi-hand-wave-outline',
    to: '/welcome',
  },
  {
    title: 'core.navigation.platforms',
    icon: 'mdi-robot',
    to: '/platforms',
  },
  {
    title: 'core.navigation.providers',
    icon: 'mdi-creation',
    to: '/providers',
  },
  {
    title: 'core.navigation.config',
    icon: 'mdi-cog',
    to: '/config#normal',
    children: [
      {
        title: 'core.navigation.configTabs.normal',
        icon: 'mdi-cog',
        to: '/config#normal'
      },
      {
        title: 'core.navigation.configTabs.system',
        icon: 'mdi-cog-outline',
        to: '/config#system'
      }
    ]
  },
  {
    title: 'core.navigation.extension',
    icon: 'mdi-puzzle',
    to: '/extension#installed',
    children: [
      {
        title: 'core.navigation.extensionTabs.installed',
        icon: 'mdi-puzzle',
        to: '/extension#installed'
      },
      {
        title: 'core.navigation.extensionTabs.market',
        icon: 'mdi-store',
        to: '/extension#market'
      },
      {
        title: 'core.navigation.extensionTabs.mcp',
        icon: 'mdi-server-network',
        to: '/extension#mcp'
      },
      {
        title: 'core.navigation.extensionTabs.skills',
        icon: 'mdi-lightning-bolt',
        to: '/extension#skills'
      },
      {
        title: 'core.navigation.extensionTabs.components',
        icon: 'mdi-wrench',
        to: '/extension#components'
      }
    ]
  },
  {
    title: 'core.navigation.knowledgeBase',
    icon: 'mdi-book-open-variant',
    to: '/knowledge-base',
  },
  {
    title: 'core.navigation.persona',
    icon: 'mdi-heart',
    to: '/persona'
  },
  {
    title: 'core.navigation.groups.more',
    icon: 'mdi-dots-horizontal',
    children: [
      {
        title: 'core.navigation.conversation',
        icon: 'mdi-database',
        to: '/conversation'
      },
      {
        title: 'core.navigation.sessionManagement',
        icon: 'mdi-pencil-ruler',
        to: '/session-management'
      },
      {
        title: 'core.navigation.cron',
        icon: 'mdi-clock-outline',
        to: '/cron'
      },
      {
        title: 'core.navigation.subagent',
        icon: 'mdi-vector-link',
        to: '/subagent'
      },
      {
        title: 'core.navigation.dashboard',
        icon: 'mdi-view-dashboard',
        to: '/dashboard/default'
      },
      {
        title: 'core.navigation.console',
        icon: 'mdi-console',
        to: '/console'
      },
      {
        title: 'core.navigation.trace',
        icon: 'mdi-timeline-text-outline',
        to: '/trace'
      },
    ]
  }
  // {
  //   title: 'Project ATRI',
  //   icon: 'mdi-grain',
  //   to: '/project-atri'
  // },
];

// 合并扩展侧边栏项（支持多个插入点）
function mergeExtensionSidebarItems(baseItems: menu[], extensionItems: menu[], inserts?: { after: string; items: string[] }[]): menu[] {
  if (!extensionItems || extensionItems.length === 0) {
    return baseItems;
  }

  // 如果没有插入配置，直接追加到末尾
  if (!inserts || inserts.length === 0) {
    return [...baseItems, ...extensionItems];
  }

  const result: menu[] = [];
  const insertedItems = new Set<string>();

  // 创建插入点映射
  const insertMap = new Map<string, string[]>();
  for (const insert of inserts) {
    insertMap.set(insert.after, insert.items);
  }

  for (const item of baseItems) {
    result.push(item);
    
    // 检查是否有插入点匹配当前项
    const itemsToInsert = insertMap.get(item.title || '');
    if (itemsToInsert) {
      for (const extItem of extensionItems) {
        if (itemsToInsert.includes(extItem.title || '') && !insertedItems.has(extItem.title || '')) {
          result.push(extItem);
          insertedItems.add(extItem.title || '');
        }
      }
    }
  }

  // 将未插入的扩展项追加到末尾
  for (const extItem of extensionItems) {
    if (!insertedItems.has(extItem.title || '')) {
      result.push(extItem);
    }
  }

  return result;
}

export function getSidebarItems(): menu[] {
  // 合并单个 sidebarInsert 和多个 sidebarInserts
  const singleInsert = getSidebarInsert();
  const multipleInserts = getSidebarInserts();
  
  const allInserts: { after: string; items: string[] }[] = [];
  
  if (singleInsert) {
    allInserts.push(singleInsert);
  }
  
  if (multipleInserts && multipleInserts.length > 0) {
    allInserts.push(...multipleInserts);
  }
  
  return mergeExtensionSidebarItems(
    baseSidebarItem,
    getExtensionSidebarItems(),
    allInserts.length > 0 ? allInserts : undefined
  );
}

export default baseSidebarItem;
