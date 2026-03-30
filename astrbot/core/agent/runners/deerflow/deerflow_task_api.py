"""
DeerFlow Task Tracker API - 任务追踪 API 端点

提供 REST API 接口用于任务追踪和人工介入
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from astrbot.core.agent.runners.deerflow.deerflow_task_tracker import (
    DeerFlowTaskTracker,
    TaskInterventionManager,
    TaskStatus,
)


router = APIRouter(prefix="/deerflow/tasks", tags=["deerflow", "tasks"])

_task_tracker: DeerFlowTaskTracker | None = None
_intervention_manager: TaskInterventionManager | None = None


def init_task_tracker(task_tracker: DeerFlowTaskTracker) -> None:
    """初始化任务追踪器"""
    global _task_tracker, _intervention_manager
    _task_tracker = task_tracker
    _intervention_manager = TaskInterventionManager(task_tracker)


def get_task_tracker() -> DeerFlowTaskTracker:
    """获取任务追踪器"""
    if _task_tracker is None:
        raise HTTPException(status_code=500, detail="Task tracker not initialized")
    return _task_tracker


def get_intervention_manager() -> TaskInterventionManager:
    """获取人工介入管理器"""
    if _intervention_manager is None:
        raise HTTPException(status_code=500, detail="Intervention manager not initialized")
    return _intervention_manager


# ============================================================================
# Request/Response Models
# ============================================================================

class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    content: str = Field(..., description="任务内容")
    position: int | None = Field(None, description="插入位置")


class TaskStatusUpdateRequest(BaseModel):
    """更新任务状态请求"""
    status: TaskStatus = Field(..., description="新状态")
    error_message: str | None = Field(None, description="错误信息")


class TaskModifyRequest(BaseModel):
    """修改任务内容请求"""
    content: str = Field(..., description="新内容")


class TaskSplitRequest(BaseModel):
    """拆分任务请求"""
    subtasks: list[str] = Field(..., description="子任务列表")


class TaskMergeRequest(BaseModel):
    """合并任务请求"""
    task_indices: list[int] = Field(..., description="要合并的任务索引")
    merged_content: str = Field(..., description="合并后的内容")


class TaskReorderRequest(BaseModel):
    """重排序任务请求"""
    new_order: list[int] = Field(..., description="新的索引顺序")


class InterventionApproveRequest(BaseModel):
    """审批介入请求"""
    approved: bool = Field(..., description="是否批准")
    modifications: dict | None = Field(None, description="修改内容")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/{thread_id}")
async def get_task_plan(thread_id: str):
    """获取任务计划"""
    tracker = get_task_tracker()
    plan = await tracker.get_task_plan(thread_id)
    
    if plan is None:
        plan = await tracker.fetch_tasks_from_deerflow(thread_id)
    
    return plan.to_dict() if plan else {"error": "Task plan not found"}


@router.get("/{thread_id}/progress")
async def get_task_progress(thread_id: str):
    """获取任务进度报告"""
    tracker = get_task_tracker()
    return await tracker.get_progress_report(thread_id)


@router.post("/{thread_id}/fetch")
async def fetch_tasks_from_deerflow(thread_id: str):
    """从 DeerFlow 刷新任务列表"""
    tracker = get_task_tracker()
    plan = await tracker.fetch_tasks_from_deerflow(thread_id)
    return plan.to_dict()


@router.post("/{thread_id}/tasks")
async def add_task(thread_id: str, request: TaskCreateRequest):
    """添加新任务"""
    tracker = get_task_tracker()
    task = await tracker.add_task(
        thread_id=thread_id,
        content=request.content,
        position=request.position,
    )
    return {"success": True, "task": task.to_dict()}


@router.patch("/{thread_id}/tasks/{task_index}")
async def update_task_status(thread_id: str, task_index: int, request: TaskStatusUpdateRequest):
    """更新任务状态"""
    tracker = get_task_tracker()
    task = await tracker.update_task_status(
        thread_id=thread_id,
        task_index=task_index,
        new_status=request.status,
        error_message=request.error_message,
    )
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"success": True, "task": task.to_dict()}


@router.put("/{thread_id}/tasks/{task_index}")
async def modify_task_content(thread_id: str, task_index: int, request: TaskModifyRequest):
    """修改任务内容"""
    manager = get_intervention_manager()
    success = await manager.modify_task_content(
        thread_id=thread_id,
        task_index=task_index,
        new_content=request.content,
    )
    return {"success": success}


@router.delete("/{thread_id}/tasks/{task_index}")
async def remove_task(thread_id: str, task_index: int):
    """删除任务"""
    tracker = get_task_tracker()
    success = await tracker.remove_task(thread_id, task_index)
    return {"success": success}


@router.post("/{thread_id}/tasks/{task_index}/split")
async def split_task(thread_id: str, task_index: int, request: TaskSplitRequest):
    """拆分任务"""
    manager = get_intervention_manager()
    success = await manager.split_task(
        thread_id=thread_id,
        task_index=task_index,
        subtasks=request.subtasks,
    )
    return {"success": success}


@router.post("/{thread_id}/tasks/merge")
async def merge_tasks(thread_id: str, request: TaskMergeRequest):
    """合并任务"""
    manager = get_intervention_manager()
    success = await manager.merge_tasks(
        thread_id=thread_id,
        task_indices=request.task_indices,
        merged_content=request.merged_content,
    )
    return {"success": success}


@router.post("/{thread_id}/reorder")
async def reorder_tasks(thread_id: str, request: TaskReorderRequest):
    """重新排序任务"""
    tracker = get_task_tracker()
    success = await tracker.reorder_tasks(
        thread_id=thread_id,
        new_order=request.new_order,
    )
    return {"success": success}


@router.post("/{thread_id}/sync")
async def sync_tasks_to_deerflow(thread_id: str):
    """将任务同步回 DeerFlow"""
    tracker = get_task_tracker()
    success = await tracker.sync_tasks_to_deerflow(thread_id)
    return {"success": success}


# ============================================================================
# Intervention API
# ============================================================================

@router.get("/interventions/pending")
async def get_pending_interventions():
    """获取待处理的人工介入请求"""
    manager = get_intervention_manager()
    interventions = await manager.get_pending_interventions()
    return {"interventions": interventions}


@router.post("/interventions/{request_id}/approve")
async def approve_intervention(request_id: str, request: InterventionApproveRequest):
    """审批人工介入请求"""
    manager = get_intervention_manager()
    success = await manager.approve_intervention(
        request_id=request_id,
        approved=request.approved,
        modifications=request.modifications,
    )
    return {"success": success}
