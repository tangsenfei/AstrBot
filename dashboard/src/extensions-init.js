/**
 * AstrBot 扩展初始化入口
 */

import { registerExtension, getBranding } from './extensions';

// 导入 NiceBot 扩展
import nicebotExtension from './extensions/nicebot';

// 导入扩展页面组件（确保被 Vite 识别）
import ToolProviderPage from '@/views/extensions/ToolProviderPage.vue';
import TaskManagementPage from '@/views/extensions/TaskManagementPage.vue';
import MemoryManagementPage from '@/views/extensions/MemoryManagementPage.vue';
import EvolutionCenterPage from '@/views/extensions/EvolutionCenterPage.vue';

// 导入智能体模块页面组件
import KnowledgePage from '@/views/agent/knowledge/KnowledgePage.vue';
import AgentsPage from '@/views/agent/agents/AgentsPage.vue';
import CrewsPage from '@/views/agent/crews/CrewsPage.vue';
import TasksPage from '@/views/agent/tasks/TasksPage.vue';
import TaskDetail from '@/views/agent/tasks/TaskDetail.vue';
import FlowsPage from '@/views/agent/flows/FlowsPage.vue';
import ToolsPage from '@/views/agent/tools/ToolsPage.vue';
import SkillsPage from '@/views/agent/skills/SkillsPage.vue';

// 注册扩展
registerExtension(nicebotExtension);

// 注册扩展路由（直接导入组件，避免 Vite tree-shaking）
import { getExtensionRoutes } from './extensions';
const extensionRoutes = getExtensionRoutes();
extensionRoutes.forEach(route => {
  if (route.name === 'ToolProvider') {
    route.component = ToolProviderPage;
  } else if (route.name === 'TaskManagement') {
    route.component = TaskManagementPage;
  } else if (route.name === 'MemoryManagement') {
    route.component = MemoryManagementPage;
  } else if (route.name === 'EvolutionCenter') {
    route.component = EvolutionCenterPage;
  } else if (route.name === 'Knowledge') {
    route.component = KnowledgePage;
  } else if (route.name === 'Agents') {
    route.component = AgentsPage;
  } else if (route.name === 'Crews') {
    route.component = CrewsPage;
  } else if (route.name === 'AgentTasks') {
    route.component = TasksPage;
  } else if (route.name === 'AgentTaskDetail') {
    route.component = TaskDetail;
  } else if (route.name === 'Flows') {
    route.component = FlowsPage;
  } else if (route.name === 'AgentTools') {
    route.component = ToolsPage;
  } else if (route.name === 'AgentSkills') {
    route.component = SkillsPage;
  }
});

// 应用品牌定制
const branding = getBranding();
if (branding.title) {
  document.title = branding.title;
}

export { registerExtension, getBranding };
