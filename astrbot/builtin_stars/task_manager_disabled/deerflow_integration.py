import asyncio
import json
from typing import Any, AsyncGenerator
from astrbot import logger


class DeerFlowHTTPClient:
    def __init__(
        self,
        base_url: str = "http://localhost:2026",
        api_key: str = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import httpx
            self._session = httpx.AsyncClient(
                timeout=300,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            )
        return self._session

    async def close(self):
        if self._session:
            await self._session.aclose()
            self._session = None

    async def chat(self, message: str, thread_id: str = None, **kwargs) -> dict:
        session = await self._get_session()
        payload = {
            "message": message,
            **kwargs
        }
        if thread_id:
            payload["thread_id"] = thread_id

        try:
            response = await session.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"DeerFlow chat error: {e}")
            raise

    async def stream(
        self,
        message: str,
        thread_id: str = None,
        **kwargs
    ) -> AsyncGenerator[dict[str, Any], None]:
        session = await self._get_session()
        payload = {
            "message": message,
            **kwargs
        }
        if thread_id:
            payload["thread_id"] = thread_id

        try:
            async with session.stream("POST", f"{self.base_url}/api/chat/stream", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip():
                            try:
                                yield json.loads(data)
                            except json.JSONDecodeError:
                                pass
                    elif line.startswith("event: "):
                        event_type = line[7:].strip()
                        yield {"type": event_type}
        except Exception as e:
            logger.error(f"DeerFlow stream error: {e}")
            raise

    async def list_models(self) -> list[dict]:
        session = await self._get_session()
        try:
            response = await session.get(f"{self.base_url}/api/models")
            response.raise_for_status()
            return response.json().get("models", [])
        except Exception as e:
            logger.error(f"DeerFlow list_models error: {e}")
            return []

    async def list_skills(self) -> list[dict]:
        session = await self._get_session()
        try:
            response = await session.get(f"{self.base_url}/api/skills")
            response.raise_for_status()
            return response.json().get("skills", [])
        except Exception as e:
            logger.error(f"DeerFlow list_skills error: {e}")
            return []

    async def get_thread(self, thread_id: str) -> dict:
        session = await self._get_session()
        try:
            response = await session.get(f"{self.base_url}/api/threads/{thread_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"DeerFlow get_thread error: {e}")
            return {}

    async def delete_thread(self, thread_id: str) -> bool:
        session = await self._get_session()
        try:
            response = await session.delete(f"{self.base_url}/api/threads/{thread_id}")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"DeerFlow delete_thread error: {e}")
            return False


class DeerFlowIntegration:
    def __init__(
        self,
        base_url: str = "http://localhost:2026",
        api_key: str = None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self._client = None
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        try:
            self._client = DeerFlowHTTPClient(
                base_url=self.base_url,
                api_key=self.api_key,
            )
            models = await self._client.list_models()
            if models:
                logger.info(f"DeerFlow connected, available models: {[m.get('name') for m in models]}")
            else:
                logger.warning("DeerFlow connected but no models available")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to connect to DeerFlow: {e}")
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._client is not None

    async def create_task(
        self,
        query: str,
        thread_id: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        tools: list[str] | None = None,
        subagent_enabled: bool = True,
        max_concurrent_subagents: int = 3,
        thinking_enabled: bool = True,
        plan_mode: bool = False,
        custom_plan: dict | None = None,
    ) -> str:
        if not self._initialized:
            await self.initialize()
        if not self._client:
            raise RuntimeError("DeerFlow client not available")

        effective_thread_id = thread_id or f"task-{asyncio.get_event_loop().time()}"

        try:
            async for event in self.stream(
                query=query,
                thread_id=effective_thread_id,
                model=model,
                skills=skills,
                tools=tools,
                subagent_enabled=subagent_enabled,
                max_concurrent_subagents=max_concurrent_subagents,
                thinking_enabled=thinking_enabled,
                plan_mode=plan_mode,
            ):
                pass
            return effective_thread_id
        except Exception as e:
            logger.error(f"Failed to create DeerFlow task: {e}")
            raise

    async def stream(
        self,
        query: str,
        thread_id: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        tools: list[str] | None = None,
        subagent_enabled: bool = True,
        max_concurrent_subagents: int = 3,
        thinking_enabled: bool = True,
        plan_mode: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if not self._initialized:
            await self.initialize()
        if not self._client:
            raise RuntimeError("DeerFlow client not available")

        kwargs = {
            "model": model,
            "skills": skills,
            "tools": tools,
            "subagent_enabled": subagent_enabled,
            "max_concurrent_subagents": max_concurrent_subagents,
            "thinking_enabled": thinking_enabled,
            "is_plan_mode": plan_mode,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        async for event in self._client.stream(query, thread_id, **kwargs):
            yield event

    async def get_task_status(self, thread_id: str) -> dict[str, Any]:
        if not self._client:
            return {"status": "unavailable"}
        try:
            return await self._client.get_thread(thread_id)
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return {"thread_id": thread_id, "status": "error", "error": str(e)}

    async def cancel_task(self, thread_id: str) -> bool:
        if not self._client:
            return False
        try:
            logger.info(f"Cancelling task: {thread_id}")
            return await self._client.delete_thread(thread_id)
        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        if not self._client:
            return []
        try:
            return await self._client.list_models()
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def list_skills(self) -> list[dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        if not self._client:
            return []
        try:
            return await self._client.list_skills()
        except Exception as e:
            logger.error(f"Failed to list skills: {e}")
            return []

    async def close(self):
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing DeerFlow client: {e}")
            self._client = None
            self._initialized = False
