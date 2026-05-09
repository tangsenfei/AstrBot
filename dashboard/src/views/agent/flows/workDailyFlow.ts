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
      output: 'task_tree_with_dependencies',
      task_mode_strategy: {
        quick: '轻量拆解，尽快形成可执行清单。',
        normal: '生成依赖任务树并控制规划深度。',
        deep: '扩展研究、风险和验收标准。',
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
      deep_mode_assigner_id: 'agent_nicebot_work_assistant',
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
