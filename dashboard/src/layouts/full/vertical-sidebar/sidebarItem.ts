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

const sidebarItems: menu[] = [
  {
    title: 'core.navigation.dashboard',
    icon: 'mdi-view-dashboard',
    to: '/dashboard/default',
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
    title: 'nicebot.navigation.tool_provider',
    icon: 'mdi-toolbox',
    to: '/tool-provider'
  },
  {
    title: 'agent.navigation.title',
    icon: 'mdi-robot-outline',
    children: [
      {
        title: 'agent.navigation.agent_management',
        icon: 'mdi-robot',
        to: '/agents'
      },
      {
        title: 'agent.navigation.roundtables',
        icon: 'mdi-table-chair',
        to: '/roundtables'
      },
      {
        title: 'agent.navigation.tools',
        icon: 'mdi-tools',
        to: '/agent/tools'
      },
      {
        title: 'agent.navigation.skills',
        icon: 'mdi-lightning-bolt',
        to: '/agent/skills'
      },
      {
        title: 'agent.navigation.knowledge',
        icon: 'mdi-database',
        to: '/knowledge'
      },
      {
        title: 'agent.navigation.crews',
        icon: 'mdi-account-group',
        to: '/crews'
      },
      {
        title: 'agent.navigation.flows',
        icon: 'mdi-graph',
        to: '/flows'
      },
      {
        title: 'agent.navigation.tasks',
        icon: 'mdi-clipboard-list-outline',
        to: '/agent/tasks'
      }
    ]
  },
  {
    title: 'nicebot.navigation.task_management',
    icon: 'mdi-clipboard-list-outline',
    to: '/task-management'
  },
  {
    title: 'nicebot.navigation.memory_management',
    icon: 'mdi-brain',
    to: '/memory-management'
  },
  {
    title: 'nicebot.navigation.evolution_center',
    icon: 'mdi-rocket-launch',
    to: '/evolution-center'
  },
  {
    title: 'core.navigation.groups.more',
    icon: 'mdi-dots-horizontal',
    children: [
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
        title: 'core.navigation.welcome',
        icon: 'mdi-hand-wave-outline',
        to: '/welcome'
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
        title: 'core.navigation.persona',
        icon: 'mdi-heart',
        to: '/persona'
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
];

export default sidebarItems;
