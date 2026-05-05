# CLI Agent Chat Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first CLI Agent foundation for NiceBot: backend data model/API plus frontend management and Chat entry points.

**Architecture:** Add CLI Agent as a facade under the existing `agent_system` plugin, following the current Work mode route/service/database pattern. Phase 1 stores clients, workspaces, sessions, messages, events, and permissions, exposes CRUD/check APIs, and adds a dashboard management page and Chat left-nav entries without yet launching real Claude/Codex subprocesses.

**Tech Stack:** Python 3.11, Quart plugin routes, SQLite via `agent_system.database.Database`, Vue 3, Vuetify, Axios, existing dashboard router.

---

## File Structure

Backend:

- Modify `astrbot/builtin_stars/agent_system/database.py`: create CLI Agent tables and indexes.
- Create `astrbot/builtin_stars/agent_system/services/cli_agent_service.py`: client/workspace/session CRUD and local command availability checks.
- Create `astrbot/builtin_stars/agent_system/routes/cli_agents.py`: `/api/plug/cli-agents/*` facade routes.
- Modify `astrbot/builtin_stars/agent_system/routes/__init__.py`: export `register_cli_agent_routes`.
- Modify `astrbot/builtin_stars/agent_system/main.py`: register CLI Agent routes.
- Add `tests/test_cli_agent_mode.py`: backend service and route-adjacent behavior tests.

Frontend:

- Create `dashboard/src/views/CliAgentsPage.vue`: Bot-side CLI Agent management page.
- Modify `dashboard/src/router/MainRoutes.ts`: add `/cli-agents` route.
- Modify `dashboard/src/components/chat/Chat.vue`: load enabled CLI clients and render entries below NiceBot.

## Task 1: Backend Tables

**Files:**

- Modify: `D:\allcode\aicode\nicebot\AstrBot\astrbot\builtin_stars\agent_system\database.py`
- Test: `D:\allcode\aicode\nicebot\AstrBot\tests\test_cli_agent_mode.py`

- [ ] **Step 1: Write failing table creation test**

Create a test that initializes `Database(tmp_path / "agent.db")`, calls `create_tables()`, and asserts all CLI Agent tables exist:

```python
def test_cli_agent_tables_are_created(tmp_path):
    from astrbot.builtin_stars.agent_system.database import Database

    db = Database(tmp_path / "agent.db")
    db.create_tables()
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert {
        "cli_agent_clients",
        "cli_agent_workspaces",
        "cli_agent_sessions",
        "cli_agent_messages",
        "cli_agent_events",
        "cli_agent_permissions",
    }.issubset(names)
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest .\tests\test_cli_agent_mode.py::test_cli_agent_tables_are_created -q
```

Expected: fail because the tables do not exist.

- [ ] **Step 3: Add tables and indexes**

Add the six tables defined in the system design to `Database.create_tables()` and add indexes in `_create_indexes()` for client kind/enabled, workspace status, sessions by client/workspace/status, events by session, permissions by session/status.

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest .\tests\test_cli_agent_mode.py::test_cli_agent_tables_are_created -q
```

Expected: pass.

## Task 2: CliAgentService

**Files:**

- Create: `D:\allcode\aicode\nicebot\AstrBot\astrbot\builtin_stars\agent_system\services\cli_agent_service.py`
- Test: `D:\allcode\aicode\nicebot\AstrBot\tests\test_cli_agent_mode.py`

- [ ] **Step 1: Write failing CRUD tests**

Add tests for:

1. Creating a local Claude client stores JSON args/env and returns normalized dicts.
2. Creating a workspace stores path/location.
3. Creating a session requires an existing client and workspace.
4. `check_client()` reports unavailable for a missing local command without raising.

- [ ] **Step 2: Run red tests**

Run:

```powershell
python -m pytest .\tests\test_cli_agent_mode.py -q
```

Expected: fail because `CliAgentService` does not exist.

- [ ] **Step 3: Implement service**

Implement focused methods:

```python
class CliAgentService:
    def list_clients(self, include_disabled: bool = False) -> list[dict]: ...
    def create_client(self, data: dict) -> dict: ...
    def update_client(self, client_id: str, data: dict) -> dict: ...
    def delete_client(self, client_id: str) -> bool: ...
    def check_client(self, client_id: str) -> dict: ...
    def list_workspaces(self) -> list[dict]: ...
    def create_workspace(self, data: dict) -> dict: ...
    def list_sessions(self, client_id: str | None = None, workspace_id: str | None = None) -> list[dict]: ...
    def create_session(self, data: dict) -> dict: ...
```

Keep Phase 1 behavior conservative: no subprocess launch, only command availability check.

- [ ] **Step 4: Run green tests**

Run:

```powershell
python -m pytest .\tests\test_cli_agent_mode.py -q
```

Expected: pass.

## Task 3: Backend Routes

**Files:**

- Create: `D:\allcode\aicode\nicebot\AstrBot\astrbot\builtin_stars\agent_system\routes\cli_agents.py`
- Modify: `D:\allcode\aicode\nicebot\AstrBot\astrbot\builtin_stars\agent_system\routes\__init__.py`
- Modify: `D:\allcode\aicode\nicebot\AstrBot\astrbot\builtin_stars\agent_system\main.py`

- [ ] **Step 1: Register facade routes**

Add route handlers matching the design:

```text
/cli-agents/clients
/cli-agents/clients/<client_id>
/cli-agents/clients/<client_id>/check
/cli-agents/workspaces
/cli-agents/workspaces/<workspace_id>
/cli-agents/sessions
/cli-agents/sessions/<session_id>
```

- [ ] **Step 2: Keep route responses aligned with existing plugin routes**

Use `astrbot.dashboard.routes.route.Response` and return `{status, message, data}` just like Work mode.

- [ ] **Step 3: Compile check**

Run:

```powershell
python -m py_compile .\astrbot\builtin_stars\agent_system\routes\cli_agents.py .\astrbot\builtin_stars\agent_system\services\cli_agent_service.py
```

Expected: no output.

## Task 4: Frontend Management Page

**Files:**

- Create: `D:\allcode\aicode\nicebot\AstrBot\dashboard\src\views\CliAgentsPage.vue`
- Modify: `D:\allcode\aicode\nicebot\AstrBot\dashboard\src\router\MainRoutes.ts`

- [ ] **Step 1: Add route**

Add route:

```ts
{
  name: 'CliAgents',
  path: '/cli-agents',
  component: () => import('@/views/CliAgentsPage.vue'),
  meta: { requiresAuth: true }
}
```

- [ ] **Step 2: Create management page**

The page should list clients, create/edit clients, show local/remote badge, and call check API. Keep it utilitarian and consistent with existing dashboard pages.

- [ ] **Step 3: Build check**

Run:

```powershell
npm run build
```

Expected: `vue-tsc --noEmit && vite build` completes.

## Task 5: Chat Left Navigation Entries

**Files:**

- Modify: `D:\allcode\aicode\nicebot\AstrBot\dashboard\src\components\chat\Chat.vue`

- [ ] **Step 1: Load enabled CLI clients**

On mount, GET `/api/plug/cli-agents/clients` and keep enabled clients in local state.

- [ ] **Step 2: Render entries below NiceBot**

Add compact entries under the NiceBot button with agent name and `本地` / `远程` badge. Clicking Phase 1 entries should select a placeholder CLI Agent workspace state rather than sending messages through the default NiceBot chat.

- [ ] **Step 3: Build check**

Run:

```powershell
npm run build
```

Expected: build succeeds.

## Task 6: Verification

- [ ] Run backend tests:

```powershell
python -m pytest .\tests\test_cli_agent_mode.py -q
```

- [ ] Run Work regression tests:

```powershell
python -m pytest .\tests\test_work_mode.py -q
```

- [ ] Run frontend build:

```powershell
npm run build
```

- [ ] Review changed files:

```powershell
git status --short
git diff --stat
```

## Self-Review Notes

This Phase 1 plan intentionally does not launch real Claude/Codex subprocesses. It creates the stable foundation needed for a safe runtime adapter in Phase 2. This keeps the first implementation testable, avoids unsafe process execution before permission UX exists, and lets the Chat UI start showing configured entries without pretending the runtime is complete.
