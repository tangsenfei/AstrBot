/**
 * NiceBot 扩展配置
 */

export default {
  branding: {
    title: 'NiceBot - 智能助手平台',
    appName: 'NiceBot',
    welcomeTitle: '欢迎使用 NiceBot',
    welcomeSubtitle: '您的专属 AI 助手'
  },

  routes: [
    {
      path: 'tool-provider',
      name: 'ToolProvider',
      component: () => import('@/views/extensions/ToolProviderPage.vue'),
      meta: {
        requiresAuth: true
      }
    }
  ],

  sidebarItems: [
    {
      title: 'nicebot.navigation.tool_provider',
      icon: 'mdi-toolbox',
      to: '/main/tool-provider'
    }
  ],

  sidebarInsert: {
    after: 'core.navigation.providers',
    items: ['nicebot.navigation.tool_provider']
  },

  i18n: {
    'zh-CN': {
      core: {
        navigation: {
          chat: '智能对话',
          dashboard: '数据看板'
        }
      },
      features: {
        chat: {
          welcome: {
            title: '欢迎使用 NiceBot',
            subtitle: '您的专属 AI 助手'
          }
        },
        auth: {
          logo: {
            title: 'NiceBot 控制台',
            subtitle: '欢迎回来'
          }
        }
      },
      nicebot: {
        navigation: {
          tool_provider: '工具管理'
        },
        tool_provider: {
          title: '工具管理',
          description: '管理 MCP 工具和 API Wrapper',
          add_tool: '添加工具',
          all_tools: '全部工具',
          no_tools: '暂无工具，请添加新工具',
          tool_name: '工具名称',
          tool_description: '描述',
          tool_source: '来源',
          tool_status: '状态',
          actions: '操作',
          confirm_delete: '确定要删除此工具吗？',
          delete_failed: '删除失败',
          add_failed: '添加失败',
          fill_required: '请填写必填字段',
          invalid_json: 'JSON 格式错误',
          api_wrapper: 'API Wrapper',
          mcp_server: 'MCP Server',
          server_name: '服务器名称',
          command: '命令',
          args_json: '参数 (JSON 数组)',
          env_json: '环境变量 (JSON 对象)',
          api_url: 'API URL',
          http_method: 'HTTP 方法',
          timeout_seconds: '超时时间 (秒)',
          cancel: '取消'
        }
      }
    },
    'en-US': {
      nicebot: {
        navigation: {
          tool_provider: 'Tool Provider'
        },
        tool_provider: {
          title: 'Tool Provider',
          description: 'Manage MCP tools and API wrappers',
          add_tool: 'Add Tool',
          no_tools: 'No tools yet, please add a new tool',
          coming_soon: 'Feature under development, coming soon...'
        }
      }
    }
  }
};
