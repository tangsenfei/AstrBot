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
      path: '/tool-provider',
      name: 'ToolProvider',
      component: () => import('@/views/extensions/ToolProviderPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/task-management',
      name: 'TaskManagement',
      component: () => import('@/views/extensions/TaskManagementPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/memory-management',
      name: 'MemoryManagement',
      component: () => import('@/views/extensions/MemoryManagementPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/evolution-center',
      name: 'EvolutionCenter',
      component: () => import('@/views/extensions/EvolutionCenterPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/knowledge',
      name: 'Knowledge',
      component: () => import('@/views/agent/knowledge/KnowledgePage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/agents',
      name: 'Agents',
      component: () => import('@/views/agent/agents/AgentsPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/crews',
      name: 'Crews',
      component: () => import('@/views/agent/crews/CrewsPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/agent/tasks',
      name: 'AgentTasks',
      component: () => import('@/views/agent/tasks/TasksPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/agent/tasks/:id',
      name: 'AgentTaskDetail',
      component: () => import('@/views/agent/tasks/TaskDetail.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/flows',
      name: 'Flows',
      component: () => import('@/views/agent/flows/FlowsPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/agent/tools',
      name: 'AgentTools',
      component: () => import('@/views/agent/tools/ToolsPage.vue'),
      meta: {
        requiresAuth: true
      }
    },
    {
      path: '/agent/skills',
      name: 'AgentSkills',
      component: () => import('@/views/agent/skills/SkillsPage.vue'),
      meta: {
        requiresAuth: true
      }
    }
  ],

  sidebarItems: [
    {
      title: 'nicebot.navigation.tool_provider',
      icon: 'mdi-toolbox',
      to: '/tool-provider'
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
      title: 'agent.navigation.title',
      icon: 'mdi-robot-outline',
      children: [
        {
          title: 'agent.navigation.agent_management',
          icon: 'mdi-robot',
          to: '/agents'
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
    }
  ],

  sidebarInserts: [
    {
      after: 'core.navigation.providers',
      items: [
        'nicebot.navigation.tool_provider',
        'agent.navigation.title',
        'nicebot.navigation.task_management',
        'nicebot.navigation.memory_management',
        'nicebot.navigation.evolution_center'
      ]
    }
  ],

  i18n: {
    'zh-CN': {
      // 大写命名空间（保留兼容）
      Common: {
        Cancel: '取消',
        Save: '保存',
        Confirm: '确认',
        Delete: '删除',
        Edit: '编辑',
        Add: '添加',
        Create: '创建',
        Close: '关闭',
        Submit: '提交',
        Refresh: '刷新',
        Loading: '加载中...',
        Success: '成功',
        Error: '错误',
        Warning: '警告',
        Info: '提示'
      },
      // 小写命名空间（页面使用）
      common: {
        cancel: '取消',
        save: '保存',
        confirm: '确认',
        delete: '删除',
        edit: '编辑',
        add: '添加',
        create: '创建',
        close: '关闭',
        submit: '提交',
        refresh: '刷新',
        loading: '加载中...',
        success: '成功',
        error: '错误',
        warning: '警告',
        info: '提示'
      },
      core: {
        navigation: {
          chat: '智能对话',
          dashboard: '数据看板',
          knowledgeBase: '知识库 (核心)'
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
        },
        'task-management': {
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
              supported: '支持主动消息的平台: {platforms} 。',
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
                unknown: '未知 ( {type} )'
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
      nicebot: {
        navigation: {
          tool_provider: '工具管理',
          task_management: '任务管理',
          memory_management: '记忆管理',
          evolution_center: '进化中心'
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
        },
        memory_management: {
          title: '记忆管理',
          description: '管理 AI 助手的短期和长期记忆',
          tabs: {
            overview: '概览',
            short_term: '短期记忆',
            long_term: '长期记忆',
            settings: '设置'
          },
          stats: {
            short_term: '短期记忆条目',
            long_term: '长期记忆条目',
            users: '用户数量'
          },
          short_term: {
            title: '短期记忆',
            hint: '短期记忆用于存储当前对话上下文中的临时信息，会在一定时间后自动清理。'
          },
          long_term: {
            title: '长期记忆',
            hint: '长期记忆用于持久化存储重要信息，可跨会话使用。'
          },
          settings: {
            title: '记忆设置',
            enabled: '启用记忆功能',
            max_short_term: '短期记忆最大条目数',
            max_long_term: '长期记忆最大条目数',
            retention_days: '记忆保留天数'
          },
          table: {
            user: '用户',
            content: '内容',
            category: '分类',
            created: '创建时间',
            actions: '操作'
          },
          actions: {
            refresh: '刷新',
            export: '导出',
            import: '导入',
            save: '保存'
          }
        },
        evolution_center: {
          title: '进化中心',
          description: 'AI 助手自我学习和能力进化管理',
          evolution_tasks: {
            title: '进化任务',
            empty: '暂无进化任务，点击上方按钮创建新任务'
          },
          capabilities: {
            title: '能力开关'
          },
          stats: {
            title: '统计数据',
            total_tasks: '总任务数',
            completed: '已完成',
            improvements: '改进数'
          },
          status: {
            pending: '待执行',
            running: '执行中',
            completed: '已完成',
            failed: '失败'
          },
          actions: {
            create_task: '创建进化任务',
            view_detail: '查看详情',
            cancel: '取消'
          }
        }
      },
      agent: {
        navigation: {
          title: '智能体',
          agent_management: '智能体管理',
          tools: '工具管理',
          skills: '技能管理',
          knowledge: '知识库',
          crews: '团队管理',
          flows: '流程编排',
          tasks: '任务管理'
        },
        knowledge: {
          title: '知识库',
          subtitle: '管理 AI 助手的知识库，支持多种知识源导入',
          buttons: {
            add: '添加知识库',
            refresh: '刷新'
          },
          search: {
            placeholder: '搜索知识库...'
          },
          stats: {
            total: '共 {count} 个知识库'
          },
          empty: '暂无知识库，请点击上方按钮创建',
          status: {
            active: '已激活',
            empty: '空知识库'
          },
          sources: {
            text: '文本知识',
            file: '文件知识',
            url: 'URL 知识',
            database: '数据库知识'
          },
          card: {
            noDescription: '暂无描述',
            sources: '{count} 个知识源',
            noModel: '未配置嵌入模型',
            addSource: '添加知识源',
            test: '检索测试',
            edit: '编辑',
            delete: '删除'
          },
          editor: {
            addTitle: '添加知识库',
            editTitle: '编辑知识库',
            basicInfo: '基本信息',
            name: '知识库名称',
            nameHint: '为知识库设置一个易于识别的名称',
            description: '描述',
            descriptionHint: '描述知识库的用途和内容',
            embeddingConfig: '嵌入模型配置',
            provider: '嵌入模型提供商',
            model: '嵌入模型',
            collectionName: '向量集合名称',
            collectionNameHint: '用于存储向量数据的集合名称，可自动生成',
            knowledgeSources: '知识源管理',
            textContent: '文本内容',
            textContentPlaceholder: '请输入要添加的文本内容...',
            addTextSource: '添加文本',
            selectFiles: '选择文件',
            fileHint: '支持 PDF、Markdown、TXT、Word 等格式',
            uploadFiles: '上传文件',
            url: 'URL 地址',
            urlPlaceholder: 'https://example.com/article',
            selector: '内容选择器',
            selectorPlaceholder: '#content 或 .article-body',
            selectorHint: '可选，用于提取页面特定区域的内容',
            fetchUrl: '抓取内容',
            dbType: '数据库类型',
            connectionString: '连接字符串',
            connectionStringPlaceholder: 'postgresql://user:pass@host:port/db',
            query: '查询语句',
            queryPlaceholder: 'SELECT content FROM documents',
            importFromDb: '从数据库导入',
            addedSources: '已添加的知识源',
            validation: {
              required: '此字段为必填项'
            }
          },
          retrieval: {
            title: '检索测试',
            query: '查询内容',
            queryPlaceholder: '输入要检索的内容...',
            topK: '返回数量',
            search: '搜索',
            results: '检索结果',
            score: '相似度',
            noResults: '未找到相关内容'
          },
          delete: {
            title: '删除知识库',
            confirm: '确定要删除知识库 "{name}" 吗？ 此操作不可恢复。'
          },
          messages: {
            deleteError: '删除失败',
            retrievalError: '检索失败',
            uploadError: '文件上传失败',
            fetchError: 'URL 抓取失败',
            dbImportError: '数据库导入失败'
          }
        },
        agents: {
          title: '智能体管理',
          subtitle: '创建和管理 AI 智能体，配置角色、能力和模型',
          buttons: {
            add: '添加智能体',
            refresh: '刷新',
            more: '更多',
            templates: '从模板创建',
            import: '导入',
            export: '导出'
          },
          templates: {
            title: '选择模板',
            assistant: {
              name: '通用助手',
              description: '一个通用的 AI 助手，可以回答各种问题',
              role: '助手',
              goal: '帮助用户完成各种任务，回答他们的问题',
              backstory: '我是一个智能助手，擅长理解和回答各种问题。'
            },
            researcher: {
              name: '研究员',
              description: '擅长研究和分析的研究员智能体',
              role: '研究员',
              goal: '深入研究各种主题，提供详细的分析报告',
              backstory: '我是一个专业的研究员，擅长收集和分析信息。'
            },
            coder: {
              name: '程序员',
              description: '擅长编程和代码审查的程序员智能体',
              role: '程序员',
              goal: '编写高质量的代码，解决技术问题',
              backstory: '我是一个经验丰富的程序员，精通多种编程语言。'
            }
          },
          search: {
            placeholder: '搜索智能体...'
          },
          tabs: {
            all: '全部',
            enabled: '已启用',
            disabled: '已禁用'
          },
          empty: '暂无智能体，请点击上方按钮创建',
          status: {
            enabled: '已启用',
            disabled: '已禁用'
          },
          card: {
            noRole: '暂无角色描述',
            tools: '{count} 个工具',
            skills: '{count} 个技能',
            knowledgeBases: '{count} 个知识库',
            planning: 'Planning',
            memory: 'Memory',
            test: '测试',
            edit: '编辑',
            copy: '复制',
            delete: '删除'
          },
          editor: {
            addTitle: '添加智能体',
            editTitle: '编辑智能体',
            tabs: {
              basic: '基本信息',
              abilities: '能力配置',
              model: '模型配置',
              advanced: '高级配置'
            },
            basic: {
              name: '智能体名称',
              nameHint: '为智能体设置一个易于识别的名称',
              role: '角色',
              roleHint: '定义智能体的角色定位，如"助手"、"研究员"等',
              goal: '目标',
              goalHint: '描述智能体的主要目标和任务',
              backstory: '背景故事',
              backstoryHint: '为智能体设置背景故事，增强角色感'
            },
            abilities: {
              tools: '工具选择',
              toolsHint: '选择智能体可以使用的工具',
              selectTools: '选择工具',
              skills: '技能选择',
              skillsHint: '选择智能体具备的技能',
              selectSkills: '选择技能',
              knowledgeBases: '知识库选择',
              knowledgeBasesHint: '选择智能体可以访问的知识库',
              selectKnowledgeBases: '选择知识库'
            },
            model: {
              provider: 'LLM 提供商',
              providerHint: '选择用于智能体的语言模型提供商',
              selectProvider: '选择提供商',
              model: '模型',
              modelHint: '选择具体的模型',
              selectModel: '选择模型',
              parameters: '模型参数',
              temperature: '温度',
              temperatureHint: '控制输出的随机性，0 为确定性，1 为最大随机性',
              maxTokens: '最大 Token 数',
              maxTokensHint: '限制单次响应的最大 Token 数量',
              topP: 'Top P',
              topPHint: '控制输出的多样性，0.1 表示只考虑前 10% 概率的词汇'
            },
            advanced: {
              planning: '启用 Planning',
              planningHint: '让智能体自动规划任务步骤',
              enablePlanning: '启用自动规划',
              memory: '启用记忆',
              memoryHint: '让智能体具备记忆能力',
              enableMemory: '启用记忆功能',
              maxSteps: '最大步骤数',
              maxStepsHint: '规划的最大步骤数',
              memoryType: '记忆类型',
              maxMessages: '最大消息数',
              maxMessagesHint: '记忆保留的最大消息数量',
              behavior: '行为配置',
              maxRetries: '最大重试次数',
              maxRetriesHint: '任务失败时的最大重试次数',
              timeout: '超时时间',
              seconds: '秒',
              verbose: '详细模式',
              verboseHint: '输出详细的执行日志',
              memoryTypes: {
                shortTerm: '短期记忆',
                longTerm: '长期记忆'
              }
            },
            validation: {
              required: '此项为必填'
            }
          },
          tester: {
            title: '智能体测试',
            input: '输入内容',
            inputPlaceholder: '输入测试内容...',
            execute: '执行',
            executing: '执行中...',
            result: '执行结果',
            noResult: '暂无结果'
          },
          delete: {
            title: '删除智能体',
            confirm: '确定要删除智能体 "{name}" 吗？ '
          },
          import: {
            title: '导入智能体',
            selectFile: '选择文件',
            hint: '支持导入 JSON 格式的智能体定义文件',
            button: '导入'
          },
          messages: {
            loadFailed: '加载失败',
            saveSuccess: '保存成功',
            saveFailed: '保存失败',
            deleteSuccess: '删除成功',
            deleteFailed: '删除失败',
            copySuccess: '复制成功',
            copyFailed: '复制失败',
            copyError: '复制失败',
            importError: '导入失败'
          }
        },
        tools: {
          title: '工具管理',
          subtitle: '管理和配置智能体可用的工具',
          buttons: {
            add: '添加工具',
            refresh: '刷新',
            more: '更多',
            import: '导入',
            export: '导出'
          },
          search: {
            placeholder: '搜索工具...'
          },
          tabs: {
            all: '全部',
            builtin: '内置',
            mcp: 'MCP',
            custom: '自定义',
            apiWrapper: 'API 包装器'
          },
          empty: '暂无工具，请点击上方按钮添加',
          sources: {
            builtin: '内置',
            mcp: 'MCP',
            custom: '自定义',
            apiWrapper: 'API 包装器'
          },
          card: {
            noDescription: '暂无描述',
            params: '{count} 个参数',
            test: '测试',
            edit: '编辑',
            delete: '删除',
            parameters: '参数',
            metadata: '元数据'
          },
          editor: {
            addTitle: '添加工具',
            editTitle: '编辑工具',
            basicInfo: '基本信息',
            name: '工具名称',
            nameHint: '工具的唯一标识，只能包含小写字母、数字和下划线',
            description: '描述',
            descriptionHint: '工具的用途描述',
            source: '来源',
            returnType: '返回类型',
            returnTypeHint: '工具返回的数据类型',
            parameters: '参数定义',
            parametersHint: '定义工具的输入参数',
            parametersJson: '参数 JSON',
            formatJson: '格式化 JSON',
            metadata: '元数据',
            metadataJson: '元数据 JSON',
            tags: '标签',
            tagsLabel: '标签（用逗号分隔）',
            tagsHint: '为工具添加标签以便分类',
            validation: {
              required: '此项为必填',
              nameFormat: '名称只能以小写字母开头，包含小写字母、数字和下划线',
              invalidJson: '无效的 JSON 格式'
            }
          },
          tester: {
            title: '工具测试',
            inputParams: '输入参数',
            paramsJson: '参数 JSON',
            formatJson: '格式化 JSON',
            reset: '重置',
            result: '测试结果',
            executing: '执行中...',
            success: '执行成功',
            failed: '执行失败',
            noResult: '暂无结果',
            clickToTest: '点击测试按钮开始测试',
            execute: '执行测试',
            invalidJson: '无效的 JSON 格式',
            unknownError: '未知错误',
            requestFailed: '请求失败'
          },
          import: {
            title: '导入工具',
            selectFile: '选择文件',
            hint: '支持导入 JSON 格式的工具定义文件',
            button: '导入'
          },
          delete: {
            title: '删除工具',
            confirm: '确定要删除工具 "{name}" 吗？ '
          },
          messages: {
            deleteError: '删除失败',
            importError: '导入失败'
          }
        },
        tasks: {
          title: '任务管理',
          subtitle: '查看和管理智能体执行的任务',
          buttons: {
            refresh: '刷新'
          },
          stats: {
            total: '总任务数',
            running: '运行中',
            completed: '已完成',
            todayTokens: '今日 Token'
          },
          tabs: {
            all: '全部',
            pending: '待执行',
            running: '运行中',
            paused: '已暂停',
            waiting_feedback: '等待反馈',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消',
            execution: '执行日志',
            planning: '执行计划',
            tokens: 'Token 统计',
            output: '输出结果'
          },
          filter: {
            crew: '筛选团队',
            timeRange: '时间范围',
            timeRanges: {
              all: '全部',
              today: '今天',
              week: '本周',
              month: '本月'
            }
          },
          actions: {
            view: '查看详情',
            pause: '暂停',
            resume: '恢复',
            cancel: '取消',
            retry: '重试',
            delete: '删除',
            back: '返回列表'
          },
          tokens: {
            totalTokens: '总 Token 数',
            promptTokens: 'Prompt Token',
            completionTokens: 'Completion Token',
            byAgent: '按智能体统计',
            byTime: '按时间统计',
            noData: '暂无数据'
          },
          table: {
            name: '任务名称',
            type: '类型',
            status: '状态',
            progress: '进度',
            tokenUsage: 'Token 使用',
            createdAt: '创建时间',
            actions: '操作'
          },
          types: {
            chat: '对话任务',
            skill: '技能任务',
            flow: '流程任务',
            crew: '团队任务'
          },
          status: {
            pending: '待执行',
            running: '运行中',
            paused: '已暂停',
            waiting_feedback: '等待反馈',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消'
          },
          empty: '暂无任务',
          notFound: '任务不存在或已被删除',
          delete: {
            title: '删除任务',
            confirm: '确定要删除任务 "{name}" 吗？此操作不可恢复。'
          },
          detail: {
            subtitle: '任务详情 - ID: {id}',
            basicInfo: '基本信息',
            type: '任务类型',
            crew: '所属团队',
            createdAt: '创建时间',
            updatedAt: '更新时间',
            input: '任务输入',
            progress: '执行进度',
            totalSteps: '总步骤',
            completedSteps: '已完成步骤',
            tokenUsage: 'Token 使用情况',
            totalTokens: '总 Token',
            promptTokens: 'Prompt Token',
            completionTokens: 'Completion Token'
          },
          planning: {
            title: '执行计划',
            step: '步骤 {index}',
            empty: '暂无执行计划'
          },
          output: {
            copy: '复制结果',
            empty: '暂无输出结果'
          },
          feedback: {
            title: '提供反馈',
            label: '您的反馈',
            placeholder: '请输入您对任务执行的反馈...',
            submit: '提交反馈'
          },
          control: {
            title: '任务控制',
            pause: '暂停任务',
            resume: '恢复任务',
            cancel: '取消任务',
            retry: '重试任务',
            provideFeedback: '提供反馈',
            pendingHint: '任务正在等待执行',
            completedHint: '任务已完成',
            unknownStatus: '未知状态'
          },
          messages: {
            pauseError: '暂停任务失败',
            resumeError: '恢复任务失败',
            cancelError: '取消任务失败',
            retryError: '重试任务失败',
            deleteError: '删除任务失败',
            feedbackError: '提交反馈失败'
          }
        },
        skills: {
          title: '技能管理',
          subtitle: '创建和管理智能体技能，配置工作流',
          buttons: {
            add: '添加技能',
            refresh: '刷新',
            more: '更多',
            import: '导入',
            export: '导出',
            market: '技能市场'
          },
          search: {
            placeholder: '搜索技能...'
          },
          tabs: {
            all: '全部',
            enabled: '已启用',
            disabled: '已禁用',
            general: '通用',
            programming: '编程',
            analysis: '分析',
            creative: '创意',
            other: '其他'
          },
          empty: '暂无技能，请点击上方按钮创建',
          status: {
            enabled: '已启用',
            disabled: '已禁用'
          },
          card: {
            noDescription: '暂无描述',
            steps: '{count} 个步骤',
            edit: '编辑',
            delete: '删除',
            test: '测试'
          },
          editor: {
            addTitle: '添加技能',
            editTitle: '编辑技能',
            basic: {
              name: '技能名称',
              nameHint: '为技能设置一个易于识别的名称',
              description: '描述',
              descriptionHint: '描述技能的用途和功能'
            },
            workflow: {
              title: '工作流配置',
              addStep: '添加步骤',
              stepType: '步骤类型',
              stepName: '步骤名称',
              stepDescription: '步骤描述',
              stepConfig: '步骤配置'
            },
            validation: {
              required: '此项为必填',
              stepRequired: '至少需要添加一个步骤'
            }
          },
          import: {
            title: '导入技能',
            selectFile: '选择文件',
            hint: '支持导入 JSON 格式的技能定义文件',
            button: '导入'
          },
          delete: {
            title: '删除技能',
            confirm: '确定要删除技能 "{name}" 吗？ '
          },
          messages: {
            loadFailed: '加载失败',
            saveSuccess: '保存成功',
            saveFailed: '保存失败',
            deleteSuccess: '删除成功',
            deleteFailed: '删除失败',
            deleteError: '删除失败',
            importError: '导入失败'
          }
        },
        crews: {
          title: '团队管理',
          subtitle: '创建和管理智能体团队，配置协作流程',
          buttons: {
            add: '添加团队',
            refresh: '刷新',
            more: '更多',
            import: '导入',
            export: '导出'
          },
          search: {
            placeholder: '搜索团队...'
          },
          tabs: {
            all: '全部',
            sequential: '顺序执行',
            hierarchical: '层级管理'
          },
          empty: '暂无团队，请点击上方按钮创建',
          status: {
            enabled: '已启用',
            disabled: '已禁用'
          },
          executor: {
            title: '执行团队',
            hint: '输入任务内容，团队 "{name}" 将开始执行',
            input: '任务输入',
            execute: '开始执行'
          },
          import: {
            title: '导入团队',
            selectFile: '选择文件',
            hint: '支持导入 JSON 格式的团队定义文件',
            button: '导入'
          },
          card: {
            noDescription: '暂无描述',
            agents: '{count} 个智能体',
            tasks: '{count} 个任务',
            process: '执行模式',
            sequential: '顺序执行',
            hierarchical: '层级管理',
            edit: '编辑',
            copy: '复制',
            execute: '执行',
            delete: '删除',
            memory: '启用记忆',
            cache: '启用缓存'
          },
          process: {
            sequential: '顺序执行',
            hierarchical: '层级管理'
          },
          editor: {
            addTitle: '添加团队',
            editTitle: '编辑团队',
            basicInfo: '基本信息',
            basic: {
              name: '团队名称',
              nameHint: '为团队设置一个易于识别的名称',
              description: '描述',
              descriptionHint: '描述团队的用途和目标'
            },
            process: {
              title: '执行模式',
              sequential: '顺序执行',
              sequentialHint: '任务按顺序依次执行',
              hierarchical: '层级管理',
              hierarchicalHint: '由管理者智能体分配任务',
              managerLLM: '管理者 LLM',
              managerLLMHint: '选择管理者智能体使用的语言模型'
            },
            agents: {
              title: '智能体选择',
              hint: '选择团队中的智能体成员',
              add: '添加智能体',
              selectAgent: '选择智能体',
              noAgents: '暂无智能体，请先添加智能体'
            },
            tasks: {
              title: '任务配置',
              hint: '配置团队要执行的任务',
              add: '添加任务',
              untitled: '未命名任务',
              taskName: '任务名称',
              taskDescription: '任务描述',
              expectedOutput: '预期输出',
              assignAgent: '分配智能体',
              selectTools: '选择工具',
              dependencies: '任务依赖',
              dependenciesHint: '选择此任务依赖的其他任务',
              noTasks: '暂无任务，请点击上方按钮添加'
            },
            advanced: {
              title: '高级配置',
              enableMemory: '启用记忆',
              maxMessages: '最大消息数',
              enableCache: '启用缓存',
              maxRPM: '最大 RPM',
              maxRPMHint: '每分钟最大请求数',
              shareOutput: '共享输出',
              shareOutputHint: '允许智能体之间共享任务输出'
            },
            validation: {
              required: '此项为必填项'
            }
          },
          delete: {
            title: '删除团队',
            confirm: '确定要删除团队 "{name}" 吗？ '
          },
          messages: {
            loadFailed: '加载失败',
            saveSuccess: '保存成功',
            saveFailed: '保存失败',
            deleteSuccess: '删除成功',
            deleteFailed: '删除失败',
            deleteError: '删除失败',
            executeError: '执行失败',
            copyError: '复制失败',
            importError: '导入失败'
          }
        },
        flows: {
          title: '流程编排',
          subtitle: '可视化编排智能体工作流',
          buttons: {
            add: '新建流程',
            refresh: '刷新',
            save: '保存',
            run: '运行',
            more: '更多',
            import: '导入',
            export: '导出'
          },
          search: {
            placeholder: '搜索流程...'
          },
          empty: '暂无流程，请点击上方按钮创建',
          status: {
            draft: '草稿',
            active: '已激活',
            archived: '已归档',
            enabled: '已启用',
            disabled: '已禁用'
          },
          tabs: {
            all: '全部',
            enabled: '已启用',
            disabled: '已禁用'
          },
          card: {
            noDescription: '暂无描述',
            nodes: '节点',
            edges: '连接',
            edit: '编辑',
            execute: '执行',
            copy: '复制',
            enable: '启用',
            disable: '禁用',
            delete: '删除'
          },
          import: {
            title: '导入流程',
            selectFile: '选择文件',
            hint: '支持导入 JSON 格式的流程定义文件',
            button: '导入'
          },
          execute: {
            title: '执行流程',
            hint: '输入初始数据，流程 "{name}" 将开始执行',
            input: '初始输入',
            button: '开始执行'
          },
          canvas: {
            title: '流程画布',
            zoomIn: '放大',
            zoomOut: '缩小',
            fitView: '适应视图',
            reset: '重置'
          },
          nodes: {
            start: '开始',
            crew: '团队执行',
            router: '条件路由',
            human: '人工审批',
            listen: '监听事件',
            and: '与门',
            or: '或门'
          },
          palette: {
            title: '节点面板',
            dragHint: '拖拽节点到画布',
            search: '搜索节点...',
            categories: {
              start: '开始节点',
              listen: '监听节点',
              router: '路由节点',
              parallel: '并行节点',
              crew: '团队节点',
              human: '人工节点'
            },
            nodes: {
              start: {
                label: '开始',
                description: '流程的起点'
              },
              listen: {
                label: '监听',
                description: '监听消息或事件'
              },
              router: {
                label: '路由',
                description: '条件路由分支'
              },
              and: {
                label: '与门',
                description: '等待所有分支完成'
              },
              or: {
                label: '或门',
                description: '等待任一分支完成'
              },
              crew: {
                label: '团队',
                description: '执行团队任务'
              },
              human: {
                label: '人工',
                description: '等待人工审批'
              }
            }
          },
          properties: {
            title: '属性配置',
            noSelection: '请选择节点以配置属性',
            basic: '基础配置',
            nodeName: '节点名称',
            startHint: '开始节点是流程的起点',
            listenConfig: '监听配置',
            eventType: '事件类型',
            condition: '条件表达式',
            conditionHint: '输入条件表达式，返回 true 或 false',
            routerConfig: '路由配置',
            routerHint: '配置条件分支',
            branches: '分支列表',
            addBranch: '添加分支',
            branch: '分支',
            branchName: '分支名称',
            branchCondition: '分支条件',
            andHint: '与门：等待所有输入分支完成',
            orHint: '或门：等待任一分支完成',
            crewConfig: '团队配置',
            selectCrew: '选择团队',
            inputMapping: '输入映射',
            inputMappingHint: '配置输入参数映射',
            humanConfig: '人工配置',
            prompt: '提示语',
            promptHint: '向用户显示的提示信息',
            options: '选项列表',
            optionsHint: '可选选项，每行一个',
            timeout: '超时时间',
            seconds: '秒',
            deleteNode: '删除节点',
            eventTypes: {
              message: '消息事件',
              command: '命令事件',
              schedule: '定时事件'
            }
          },
          editor: {
            addTitle: '新建流程',
            editTitle: '编辑流程',
            flowName: '流程名称',
            validate: '验证',
            simulate: '模拟运行',
            nodes: '节点数',
            edges: '连接数',
            validation: {
              noStart: '流程必须有一个开始节点',
              multipleStart: '流程只能有一个开始节点',
              invalidEdge: '存在无效的连接'
            }
          },
          delete: {
            title: '删除流程',
            confirm: '确定要删除流程 "{name}" 吗？ '
          },
          messages: {
            loadFailed: '加载失败',
            saveSuccess: '保存成功',
            saveFailed: '保存失败',
            deleteSuccess: '删除成功',
            deleteFailed: '删除失败',
            runSuccess: '流程已启动',
            copyError: '复制失败',
            executeError: '执行失败',
            importError: '导入失败',
            runFailed: '启动失败'
          }
        }
      }
    }
  }
};
