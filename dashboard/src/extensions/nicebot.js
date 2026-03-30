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
    },
    {
      path: 'task-management',
      name: 'TaskManagement',
      component: () => import('@/views/extensions/TaskManagementPage.vue'),
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
    },
    {
      title: 'nicebot.navigation.task_management',
      icon: 'mdi-clipboard-list-outline',
      to: '/main/task-management'
    }
  ],

  sidebarInsert: {
    after: 'core.navigation.providers',
    items: ['nicebot.navigation.tool_provider', 'nicebot.navigation.task_management']
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
          tool_provider: '工具管理',
          task_management: '任务管理'
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
      },
      'features/task-management': {
        tabs: {
          simple: '简单任务',
          deep: '深度任务',
          deerflow: 'DeerFlow 任务'
        },
        simple: {
          title: '未来任务',
          beta: 'Beta',
          subtitle: '查看给 AstrBot 布置的未来任务。AstrBot 将会被自动唤醒、执行任务，然后将结果告知任务布置方。需要先在配置文件中启用"主动型能力"。',
          proactive: {
            supported: '支持主动消息的平台: {platforms}。',
            unsupported: '当前没有支持主动消息的平台。'
          },
          actions: {
            create: '创建任务',
            refresh: '刷新',
            delete: '删除',
            cancel: '取消',
            submit: '提交'
          },
          table: {
            title: '任务列表',
            empty: '暂无任务',
            notAvailable: '无',
            timezoneLocal: '本地时区',
            headers: {
              name: '任务名称',
              type: '类型',
              cron: '执行时间',
              session: '会话',
              nextRun: '下次执行',
              lastRun: '上次执行',
              note: '备注',
              actions: '操作'
            },
            type: {
              once: '一次性',
              activeAgent: '主动 Agent',
              workflow: '工作流',
              unknown: '未知 ({type})'
            }
          },
          form: {
            title: '创建新任务',
            chatHint: '任务将在指定时间自动执行，结果会发送到指定会话。',
            runOnce: '一次性任务',
            name: '任务名称',
            note: '任务内容',
            cron: 'Cron 表达式',
            cronPlaceholder: '例如: 0 9 * * * (每天 9:00)',
            runAt: '执行时间',
            session: '会话 ID',
            timezone: '时区 (可选)',
            enabled: '启用'
          },
          messages: {
            loadFailed: '加载任务失败',
            updateFailed: '更新任务失败',
            deleteSuccess: '删除成功',
            deleteFailed: '删除失败',
            createSuccess: '创建成功',
            createFailed: '创建失败',
            sessionRequired: '请填写会话 ID',
            noteRequired: '请填写任务内容',
            cronRequired: '请填写 Cron 表达式',
            runAtRequired: '请选择执行时间'
          }
        },
        deep: {
          comingSoon: '功能开发中',
          description: '深度任务功能即将上线，敬请期待...'
        },
        deerflow: {
          title: 'DeerFlow 任务管理',
          description: '创建和管理 DeerFlow 异步复杂任务，支持任务拆解、人工审批和进度追踪',
          actions: {
            create: '创建任务',
            refresh: '刷新',
            start: '启动',
            pause: '暂停',
            cancel: '取消',
            approve: '批准计划',
            modify: '修改计划',
            retry: '重试',
            skip: '跳过',
            delete: '删除'
          },
          table: {
            title: '任务列表',
            empty: '暂无任务',
            headers: {
              title: '任务标题',
              status: '状态',
              model: '模型',
              progress: '进度',
              created: '创建时间',
              actions: '操作'
            }
          },
          status: {
            pending: '待执行',
            planning: '规划中',
            waiting_approval: '等待审批',
            executing: '执行中',
            paused: '已暂停',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消'
          },
          todoStatus: {
            pending: '待执行',
            in_progress: '执行中',
            completed: '已完成',
            failed: '失败',
            skipped: '已跳过'
          },
          form: {
            title: '创建新任务',
            taskTitle: '任务标题',
            taskDescription: '任务描述',
            taskDescriptionPlaceholder: '请详细描述您希望完成的任务...',
            model: '当前模型',
            modelHint: '模型在插件配置页面设置',
            planMode: '计划模式',
            planModeHint: '启用后，系统会先拆解任务计划，等待您审批后再执行'
          },
          plan: {
            title: '任务计划',
            approveHint: '请审核以下任务计划，确认后将开始执行',
            modifyHint: '您可以修改任务计划后再批准',
            noPlan: '暂无任务计划'
          },
          progress: {
            title: '执行进度',
            total: '总计',
            completed: '已完成',
            failed: '失败',
            skipped: '已跳过',
            inProgress: '进行中',
            pending: '待执行'
          },
          config: {
            title: 'DeerFlow 配置',
            provider: 'LLM 提供者',
            model: '模型',
            thinking: '思考模式',
            planMode: '计划模式',
            subagent: '子代理',
            selectProvider: '选择提供者',
            selectModel: '选择模型',
            noProviderHint: '请先在插件配置页面选择 LLM 提供者',
            goToConfig: '前往配置'
          },
          messages: {
            loadFailed: '加载失败',
            createSuccess: '任务创建成功',
            createFailed: '任务创建失败',
            startSuccess: '任务已启动',
            startFailed: '启动失败',
            pauseSuccess: '任务已暂停',
            pauseFailed: '暂停失败',
            cancelSuccess: '任务已取消',
            cancelFailed: '取消失败',
            approveSuccess: '计划已批准',
            approveFailed: '批准失败',
            modifySuccess: '计划已修改',
            modifyFailed: '修改失败',
            deleteSuccess: '任务已删除',
            deleteFailed: '删除失败',
            configSaved: '配置已保存',
            configFailed: '配置保存失败'
          }
        }
      }
    },
    'en-US': {
      nicebot: {
        navigation: {
          tool_provider: 'Tool Provider',
          task_management: 'Task Management'
        },
        tool_provider: {
          title: 'Tool Provider',
          description: 'Manage MCP tools and API wrappers',
          add_tool: 'Add Tool',
          no_tools: 'No tools yet, please add a new tool',
          coming_soon: 'Feature under development, coming soon...'
        }
      },
      'features/task-management': {
        tabs: {
          simple: 'Simple Tasks',
          deep: 'Deep Tasks',
          deerflow: 'DeerFlow Tasks'
        },
        simple: {
          title: 'Future Tasks',
          beta: 'Beta',
          subtitle: 'View scheduled tasks for AstrBot. AstrBot will be automatically awakened to execute tasks and report results. Enable "Proactive Capabilities" in config first.',
          proactive: {
            supported: 'Platforms supporting proactive messages: {platforms}.',
            unsupported: 'No platforms supporting proactive messages currently.'
          },
          actions: {
            create: 'Create Task',
            refresh: 'Refresh',
            delete: 'Delete',
            cancel: 'Cancel',
            submit: 'Submit'
          },
          table: {
            title: 'Task List',
            empty: 'No tasks yet',
            notAvailable: 'N/A',
            timezoneLocal: 'Local Timezone',
            headers: {
              name: 'Task Name',
              type: 'Type',
              cron: 'Schedule',
              session: 'Session',
              nextRun: 'Next Run',
              lastRun: 'Last Run',
              note: 'Note',
              actions: 'Actions'
            },
            type: {
              once: 'One-time',
              activeAgent: 'Active Agent',
              workflow: 'Workflow',
              unknown: 'Unknown ({type})'
            }
          },
          form: {
            title: 'Create New Task',
            chatHint: 'Tasks will be executed at the scheduled time and results sent to the specified session.',
            runOnce: 'One-time Task',
            name: 'Task Name',
            note: 'Task Content',
            cron: 'Cron Expression',
            cronPlaceholder: 'e.g., 0 9 * * * (daily at 9:00)',
            runAt: 'Execution Time',
            session: 'Session ID',
            timezone: 'Timezone (optional)',
            enabled: 'Enabled'
          },
          messages: {
            loadFailed: 'Failed to load tasks',
            updateFailed: 'Failed to update task',
            deleteSuccess: 'Deleted successfully',
            deleteFailed: 'Failed to delete',
            createSuccess: 'Created successfully',
            createFailed: 'Failed to create',
            sessionRequired: 'Please enter session ID',
            noteRequired: 'Please enter task content',
            cronRequired: 'Please enter cron expression',
            runAtRequired: 'Please select execution time'
          }
        },
        deep: {
          comingSoon: 'Coming Soon',
          description: 'Deep task feature is under development, stay tuned...'
        },
        deerflow: {
          title: 'DeerFlow Task Management',
          description: 'Create and manage DeerFlow async complex tasks with task decomposition, manual approval and progress tracking',
          actions: {
            create: 'Create Task',
            refresh: 'Refresh',
            start: 'Start',
            pause: 'Pause',
            cancel: 'Cancel',
            approve: 'Approve Plan',
            modify: 'Modify Plan',
            retry: 'Retry',
            skip: 'Skip',
            delete: 'Delete'
          },
          table: {
            title: 'Task List',
            empty: 'No tasks yet',
            headers: {
              title: 'Task Title',
              status: 'Status',
              model: 'Model',
              progress: 'Progress',
              created: 'Created',
              actions: 'Actions'
            }
          },
          status: {
            pending: 'Pending',
            planning: 'Planning',
            waiting_approval: 'Waiting Approval',
            executing: 'Executing',
            paused: 'Paused',
            completed: 'Completed',
            failed: 'Failed',
            cancelled: 'Cancelled'
          },
          todoStatus: {
            pending: 'Pending',
            in_progress: 'In Progress',
            completed: 'Completed',
            failed: 'Failed',
            skipped: 'Skipped'
          },
          form: {
            title: 'Create New Task',
            taskTitle: 'Task Title',
            taskDescription: 'Task Description',
            taskDescriptionPlaceholder: 'Describe the task you want to accomplish...',
            model: 'Current Model',
            modelHint: 'Model is set in plugin config page',
            planMode: 'Plan Mode',
            planModeHint: 'When enabled, the system will decompose the task first and wait for your approval before execution'
          },
          plan: {
            title: 'Task Plan',
            approveHint: 'Review the task plan below, it will be executed after approval',
            modifyHint: 'You can modify the plan before approval',
            noPlan: 'No task plan yet'
          },
          progress: {
            title: 'Execution Progress',
            total: 'Total',
            completed: 'Completed',
            failed: 'Failed',
            skipped: 'Skipped',
            inProgress: 'In Progress',
            pending: 'Pending'
          },
          config: {
            title: 'DeerFlow Configuration',
            provider: 'LLM Provider',
            model: 'Model',
            thinking: 'Thinking Mode',
            planMode: 'Plan Mode',
            subagent: 'Sub-agent',
            selectProvider: 'Select Provider',
            selectModel: 'Select Model',
            noProviderHint: 'Please select an LLM provider in plugin config page first',
            goToConfig: 'Go to Config'
          },
          messages: {
            loadFailed: 'Failed to load',
            createSuccess: 'Task created successfully',
            createFailed: 'Failed to create task',
            startSuccess: 'Task started',
            startFailed: 'Failed to start',
            pauseSuccess: 'Task paused',
            pauseFailed: 'Failed to pause',
            cancelSuccess: 'Task cancelled',
            cancelFailed: 'Failed to cancel',
            approveSuccess: 'Plan approved',
            approveFailed: 'Failed to approve',
            modifySuccess: 'Plan modified',
            modifyFailed: 'Failed to modify',
            deleteSuccess: 'Task deleted',
            deleteFailed: 'Failed to delete',
            configSaved: 'Configuration saved',
            configFailed: 'Failed to save configuration'
          }
        }
      }
    }
  }
};
