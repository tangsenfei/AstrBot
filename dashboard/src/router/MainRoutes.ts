import { EXTENSION_ROUTE_NAME } from './routeConstants.mjs';

const MainRoutes = {
  path: '/main',
  meta: {
    requiresAuth: true
  },
  redirect: '/welcome',
  component: () => import('@/layouts/full/FullLayout.vue'),
  children: [
    {
      name: 'MainPage',
      path: '/',
      component: () => import('@/views/WelcomePage.vue')
    },
    {
      name: 'Welcome',
      path: '/welcome',
      component: () => import('@/views/WelcomePage.vue')
    },
    {
      name: EXTENSION_ROUTE_NAME,
      path: '/extension',
      component: () => import('@/views/ExtensionPage.vue')
    },
    {
      name: 'ExtensionMarketplace',
      path: '/extension-marketplace',
      component: () => import('@/views/ExtensionPage.vue')
    },
    {
      name: 'Platforms',
      path: '/platforms',
      component: () => import('@/views/PlatformPage.vue')
    },
    {
      name: 'Providers',
      path: '/providers',
      component: () => import('@/views/ProviderPage.vue')
    },
    {
      name: 'ToolProvider',
      path: '/tool-provider',
      component: () => import('@/views/ToolProviderPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'TaskManagement',
      path: '/task-management',
      component: () => import('@/views/TaskManagementPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'MemoryManagement',
      path: '/memory-management',
      component: () => import('@/views/MemoryManagementPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'EvolutionCenter',
      path: '/evolution-center',
      component: () => import('@/views/EvolutionCenterPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Knowledge',
      path: '/knowledge',
      component: () => import('@/views/agent/knowledge/KnowledgePage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Agents',
      path: '/agents',
      component: () => import('@/views/agent/agents/AgentsPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Crews',
      path: '/crews',
      component: () => import('@/views/agent/crews/CrewsPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'AgentTasks',
      path: '/agent/tasks',
      component: () => import('@/views/agent/tasks/TasksPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'AgentTaskDetail',
      path: '/agent/tasks/:id',
      component: () => import('@/views/agent/tasks/TaskDetail.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Flows',
      path: '/flows',
      component: () => import('@/views/agent/flows/FlowsPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'AgentTools',
      path: '/agent/tools',
      component: () => import('@/views/agent/tools/ToolsPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'AgentSkills',
      path: '/agent/skills',
      component: () => import('@/views/agent/skills/SkillsPage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Roundtables',
      path: '/roundtables',
      component: () => import('@/views/agent/roundtables/RoundtablePage.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'RoundtableExecution',
      path: '/roundtables/:id/execution',
      component: () => import('@/views/agent/roundtables/RoundtableExecution.vue'),
      meta: { requiresAuth: true }
    },
    {
      name: 'Configs',
      path: '/config',
      component: () => import('@/views/ConfigPage.vue')
    },
    {
      path: '/normal',
      redirect: '/config#normal'
    },
    {
      path: '/system',
      redirect: '/config#system'
    },
    {
      name: 'Stats',
      path: '/dashboard/default',
      component: () => import('@/views/stats/StatsPage.vue')
    },
    {
      name: 'Conversation',
      path: '/conversation',
      component: () => import('@/views/ConversationPage.vue')
    },
    {
      name: 'SessionManagement',
      path: '/session-management',
      component: () => import('@/views/SessionManagementPage.vue')
    },
    {
      name: 'Persona',
      path: '/persona',
      component: () => import('@/views/PersonaPage.vue')
    },
    {
      name: 'SubAgent',
      path: '/subagent',
      component: () => import('@/views/SubAgentPage.vue')
    },
    {
      name: 'CronJobs',
      path: '/cron',
      component: () => import('@/views/CronJobPage.vue')
    },
    {
      name: 'Console',
      path: '/console',
      component: () => import('@/views/ConsolePage.vue')
    },
    {
      name: 'Trace',
      path: '/trace',
      component: () => import('@/views/TracePage.vue')
    },
    {
      name: 'NativeKnowledgeBase',
      path: '/knowledge-base',
      component: () => import('@/views/knowledge-base/index.vue'),
      children: [
        {
          path: '',
          name: 'NativeKBList',
          component: () => import('@/views/knowledge-base/KBList.vue')
        },
        {
          path: ':kbId',
          name: 'NativeKBDetail',
          component: () => import('@/views/knowledge-base/KBDetail.vue'),
          props: true
        },
        {
          path: ':kbId/document/:docId',
          name: 'NativeDocumentDetail',
          component: () => import('@/views/knowledge-base/DocumentDetail.vue'),
          props: true
        }
      ]
    },
    {
      name: 'KnowledgeBase',
      path: '/alkaid/knowledge-base',
      component: () => import('@/views/alkaid/KnowledgeBase.vue'),
    },
    {
      name: 'Chat',
      path: '/chat',
      component: () => import('@/views/ChatPage.vue'),
      children: [
        {
          path: ':conversationId',
          name: 'ChatDetail',
          component: () => import('@/views/ChatPage.vue'),
          props: true
        }
      ]
    },
    {
      name: 'Settings',
      path: '/settings',
      component: () => import('@/views/Settings.vue')
    },
    {
      name: 'About',
      path: '/about',
      component: () => import('@/views/AboutPage.vue')
    }
  ]
};

export default MainRoutes;
