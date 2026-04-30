# AstrBot/astrbot/core/memory/models.py
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Column, TEXT


# ---- 事件表 ----
class MemoryEvent(SQLModel, table=True):
    __tablename__ = "memory_events"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    agent_id: str = Field(default="main", index=True)
    scene_id: Optional[str] = Field(default=None, index=True)
    type: str = Field(index=True)  # user_message | agent_reply | tool_call | scheduled_task | system_event
    role: Optional[str] = Field(default=None)
    content: str = Field(sa_column=Column(TEXT))
    event_meta: str = Field(default="{}", sa_column=Column("metadata", TEXT))
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    created_by: Optional[str] = Field(default=None)


# ---- 场景表 ----
class MemoryScene(SQLModel, table=True):
    __tablename__ = "memory_scenes"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    agent_id: str = Field(default="main", index=True)
    title: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    status: str = Field(default="open")  # open | sealed | enriched | failed
    event_count: int = Field(default=0)
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = Field(default=None)
    embedding: Optional[str] = Field(default=None, sa_column=Column(TEXT))  # JSON array
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---- 语义记忆表 ----
class MemorySemanticClaim(SQLModel, table=True):
    __tablename__ = "memory_semantic_claims"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    agent_id: str = Field(default="main", index=True)
    claim_type: str = Field(index=True)  # fact | preference | relation | constraint
    l1_category: Optional[str] = Field(default=None)
    l2_category: Optional[str] = Field(default=None)
    subject: str = Field(index=True)
    predicate: str = Field()
    object: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.5)
    evidence: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    source_scene_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="active")  # active | superseded | archived
    supersedes_id: Optional[str] = Field(default=None)
    retrieval_priority: float = Field(default=0.5)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---- 程序性记忆表 ----
class MemoryProceduralRule(SQLModel, table=True):
    __tablename__ = "memory_procedural_rules"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    agent_id: str = Field(default="main", index=True)
    scope: str = Field(index=True)  # global_policy | shared_rule | agent_private | task_playbook
    rule_type: str = Field(default="directive")
    title: str = Field()
    content: str = Field(sa_column=Column(TEXT))
    priority: int = Field(default=0)
    enabled: int = Field(default=1)
    source_scene_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---- 身份记忆表 ----
class MemoryIdentity(SQLModel, table=True):
    __tablename__ = "memory_identity"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    agent_id: str = Field(default="main", index=True)
    key: str = Field()
    value: str = Field(sa_column=Column(TEXT))
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ---- 提示词表 ----
class MemoryPrompt(SQLModel, table=True):
    __tablename__ = "memory_prompts"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    prompt_type: str = Field(index=True)  # extraction | planner | summarization
    version: int = Field()
    content: str = Field(sa_column=Column(TEXT))
    description: Optional[str] = Field(default=None)
    is_active: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)
    activated_at: Optional[datetime] = Field(default=None)


# ---- 审计日志表 ----
class MemoryAuditLog(SQLModel, table=True):
    __tablename__ = "memory_audit_logs"

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)
    owner_id: str = Field(default="default", index=True)
    actor: str = Field()
    action: str = Field()  # create | update | delete | activate | read
    target_type: str = Field()  # event | scene | claim | rule | identity | prompt
    target_id: Optional[str] = Field(default=None)
    details: str = Field(default="{}", sa_column=Column(TEXT))
    created_at: datetime = Field(default_factory=datetime.now, index=True)
