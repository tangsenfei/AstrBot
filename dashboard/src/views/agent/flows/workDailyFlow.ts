export const BUILTIN_DAILY_WORK_FLOW_ID = 'builtin_nicebot_daily_work_flow';

type FlowNode = Record<string, any>;
type FlowEdge = Record<string, any>;

const dailyWorkNodes: FlowNode[] = [
  {
    id: 'daily_start',
    name: '开始',
    type: 'start',
    position: { x: 80, y: 220 },
    config: {},
    summary: '接收 Work 日常任务输入并建立任务上下文。',
  },
  {
    id: 'daily_clarify',
    name: '需求明确',
    type: 'hitl',
    position: { x: 420, y: 220 },
    config: {
      builtin_stage: 'clarification',
      work_stage: '需求明确',
      agent_id: 'agent_nicebot_work_assistant',
      template_id: 'builtin_work_requirement_clarification',
      repeat_until_clear: true,
      content_provider_type: 'agent',
      content_provider_agent_id: 'agent_nicebot_work_assistant',
      content_system_prompt: '你是 NiceBot Work 任务助手，负责根据用户任务目标生成精准、可操作的需求确认项。你必须只返回合法 JSON，不要输出解释、Markdown 或代码块。',
      content_prompt: `请为 Work 任务生成 2-5 个需求确认项。

任务名称：{task_name}
任务描述：{task_desc}

工作上下文：
{work_context}

请只返回如下 JSON 对象，不要包含 markdown 代码块：
{
  "confirmation_items": [
    {
      "key": "字段英文key",
      "label": "字段中文标签",
      "description": "为什么需要确认这个信息",
      "field_type": "select 或 multiselect 或 textarea",
      "required": true,
      "recommended": "推荐：结合任务内容给出的默认值",
      "options": ["推荐：选项A", "选项B", "选项C"],
      "allow_custom": true,
      "custom_placeholder": "用户选择自定义时的填写提示"
    }
  ]
}

生成要求：
1. 确认项必须贴合任务，不要使用泛化的固定字段。
2. 优先确认会影响交付质量的信息，例如目标对象、范围边界、偏好、约束、交付格式、完成标准。
3. 有明确互斥选项时用 select；可多选维度用 multiselect；需要用户自由描述时用 textarea。
4. select/multiselect 必须提供 3-6 个 options，且至少一个选项以「推荐：」开头。
5. 每个 select/multiselect 都必须设置 allow_custom 为 true。
6. key 使用稳定英文小写蛇形命名。`,
    },
    summary: '用 HITL 模板向用户补齐目标、约束、交付格式和上下文。',
  },
  {
    id: 'daily_plan',
    name: '任务规划',
    type: 'agent_task',
    position: { x: 1100, y: 220 },
    config: {
      builtin_stage: 'plan',
      work_stage: '任务规划',
      agent_id: 'agent_nicebot_work_assistant',
      max_depth: 2,
      output: 'resource_aware_execution_tree',
      system_prompt: '你是 NiceBot Work 的资源感知规划智能体。你需要同时完成任务拆解、依赖设计和执行资源分配，并输出可校验的执行树。',
      prompt: `请根据 Work 规划协议输出可审批、可直接落地的执行树。

## 任务目标
- 名称：{task_name}
- 描述：{task_desc}

## 已确认需求
{clarification}

## 工作上下文
{work_context}

## 规划要求
- 你必须在规划阶段完成执行资源分配；分配与拆解、依赖设计是一体的。
- 按当前任务模式选择执行粒度，不要先写计划再补执行者。
- 每个执行步骤必须同时给出依赖、执行者、审查者、交付物、验收标准和资源选择理由。
- 依赖只能引用本计划中已经存在的 step_id，不能形成环。
- 输出必须能被系统校验并在人工审批通过后原样执行。

{feedback_text}`,
      task_mode_strategy: {
        quick: '单执行单元，快速形成可交付结果。',
        normal: '按一级步骤规划执行，二级内容作为检查项或说明。',
        deep: '按叶子步骤细粒度规划，允许研究、审查、汇报等资源分工。',
      },
    },
    summary: '根据任务模式生成依赖任务树、执行顺序和验收标准。',
  },
  {
    id: 'daily_plan_approval',
    name: '计划审批',
    type: 'hitl',
    position: { x: 1440, y: 220 },
    config: {
      builtin_stage: 'plan_hitl',
      work_stage: '计划审批',
      template_id: 'builtin_work_plan_approval',
      optional_config_key: 'plan_config.enabled',
      default_enabled: true,
    },
    summary: '在执行前给用户确认计划、修改优先级或跳过审批。',
  },
  {
    id: 'daily_execute',
    name: '依赖执行',
    type: 'agent_task',
    position: { x: 1780, y: 220 },
    config: {
      builtin_stage: 'execute_dag',
      work_stage: '依赖执行',
      default_agent_id: 'agent_nicebot_work_executor',
      research_agent_id: 'agent_nicebot_research_expert',
      task_mode_strategy: {
        quick: '直接执行主路径任务，减少分支探索。',
        normal: '按依赖 DAG 分派并汇总中间产物。',
        deep: '引入研究专家和更细粒度分派。',
      },
    },
    summary: '按依赖 DAG 调度执行，深度模式可引入研究和分派 Agent。',
  },
  {
    id: 'daily_review',
    name: '执行审查',
    type: 'review',
    position: { x: 2460, y: 120 },
    config: {
      builtin_stage: 'review',
      work_stage: '执行审查',
      reviewer_id: 'agent_nicebot_work_reviewer',
      optional_config_key: 'review_config.enabled',
      default_enabled: false,
      max_rework_config_key: 'review_config.max_rework',
      default_max_rework: 3,
    },
    summary: '按需审查执行结果并触发有限返工。',
  },
  {
    id: 'daily_deliver',
    name: '验收与交付',
    type: 'deliverable',
    position: { x: 3480, y: 120 },
    config: {
      builtin_stage: 'deliverable',
      work_stage: '验收与交付',
      assistant_id: 'agent_nicebot_work_assistant',
      reporter_id: 'agent_nicebot_report_expert',
      artifact_type: 'markdown',
    },
    summary: '整理验收结论、交付物和最终工作记录。',
  },
];

const dailyWorkEdges: FlowEdge[] = [
  {
    id: 'edge_daily_start_clarify',
    source: 'daily_start',
    target: 'daily_clarify',
    condition: { label: '进入需求明确' },
  },
  {
    id: 'edge_daily_clarify_plan',
    source: 'daily_clarify',
    target: 'daily_plan',
    condition: { label: '需求已明确' },
  },
  {
    id: 'edge_daily_plan_approval',
    source: 'daily_plan',
    target: 'daily_plan_approval',
    condition: { label: '规划完成' },
  },
  {
    id: 'edge_daily_approval_execute',
    source: 'daily_plan_approval',
    target: 'daily_execute',
    condition: { label: '计划通过/跳过' },
  },
  {
    id: 'edge_daily_execute_review',
    source: 'daily_execute',
    target: 'daily_review',
    condition: { label: '执行完成' },
  },
  {
    id: 'edge_daily_review_deliver',
    source: 'daily_review',
    target: 'daily_deliver',
    condition: { label: '审查通过/未启用' },
  },
];

export function isBuiltinDailyWorkFlow(flow: any): boolean {
  return Boolean(
    flow?.id === BUILTIN_DAILY_WORK_FLOW_ID ||
    flow?.metadata?.kind === 'work_daily_task' ||
    (flow?.metadata?.is_builtin && flow?.metadata?.locked && String(flow?.name || '').includes('日常任务')),
  );
}

export function normalizeDailyWorkFlow(flow: any): any {
  if (!isBuiltinDailyWorkFlow(flow)) return flow;

  const existingNodes = Array.isArray(flow?.nodes) ? flow.nodes : [];
  const existingEdges = Array.isArray(flow?.edges) ? flow.edges : [];
  const schemaVersion = Number(flow?.metadata?.schema_version || 0);
  const useServerTopology = schemaVersion >= 3 && existingNodes.length >= 10;
  const templateNodes = useServerTopology ? existingNodes : dailyWorkNodes;
  const templateEdges = useServerTopology ? existingEdges : dailyWorkEdges;

  return {
    ...flow,
    id: flow?.id || BUILTIN_DAILY_WORK_FLOW_ID,
    metadata: {
      ...(flow?.metadata || {}),
      is_builtin: true,
      locked: true,
      non_deletable: true,
      resettable: true,
      editable: true,
      kind: 'work_daily_task',
    },
    nodes: templateNodes.map((templateNode: FlowNode) => {
      const existing = useServerTopology ? templateNode : findNodeByBuiltinStage(existingNodes, templateNode);
      const existingConfig = existing?.config || existing?.data?.config || {};
      const mergedConfig = {
        ...(templateNode.config || {}),
        ...existingConfig,
        work_stage: existingConfig.work_stage || templateNode.config?.work_stage || templateNode.name,
      };

      return {
        ...templateNode,
        ...existing,
        id: templateNode.id,
        type: templateNode.type,
        name: existing?.name || existing?.data?.label || templateNode.name,
        position: existing?.position || templateNode.position,
        config: mergedConfig,
        data: {
          ...(existing?.data || {}),
          label: existing?.data?.label || existing?.name || templateNode.name,
          summary: existing?.data?.summary || templateNode.summary || mergedConfig.work_stage || mergedConfig.builtin_stage,
          lockedTopology: true,
          config: mergedConfig,
        },
        draggable: false,
        connectable: false,
        deletable: false,
      };
    }),
    edges: templateEdges.map((templateEdge: FlowEdge) => {
      const existing = useServerTopology ? templateEdge : existingEdges.find((edge: FlowEdge) => edge.id === templateEdge.id);
      const condition = existing?.condition || existing?.data?.condition || templateEdge.condition || {};
      const label = getConditionLabel(condition);

      return {
        ...templateEdge,
        ...existing,
        id: templateEdge.id,
        source: templateEdge.source,
        target: templateEdge.target,
        condition,
        data: {
          ...(existing?.data || {}),
          condition,
        },
        label,
        type: 'smoothstep',
        animated: true,
        updatable: false,
        selectable: false,
        markerEnd: { type: 'arrowclosed', color: '#2563eb' },
        style: { stroke: '#2563eb', strokeWidth: 2 },
        labelStyle: { fill: '#1e3a8a', fontSize: 12, fontWeight: 600 },
        labelBgStyle: { fill: '#eff6ff', fillOpacity: 0.95 },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
      };
    }),
  };
}

function findNodeByBuiltinStage(nodes: FlowNode[], templateNode: FlowNode): FlowNode | undefined {
  return nodes.find((node) => node.id === templateNode.id) ||
    nodes.find((node) => {
      const config = node.config || node.data?.config || {};
      return config.builtin_stage && config.builtin_stage === templateNode.config?.builtin_stage;
    });
}

function getConditionLabel(condition: any): string {
  if (!condition || typeof condition !== 'object') return '';
  return condition.label || condition.name || condition.expression || condition.when || '';
}
