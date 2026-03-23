import json
import re
import os
from typing import Optional, List, Any

import httpx

from .registry import ToolRegistry, ToolSource


class APIWrapperAdapter:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.http_client = httpx.AsyncClient()
        self._auth_cache: dict = {}

    async def add_tool(self, config: dict, persist: bool = True) -> str:
        name = config.get("name")
        if not name:
            raise ValueError("Tool name is required")

        handler = self._create_handler(config)
        parameters = self._build_parameters(config)
        description = config.get("description", "")

        if persist:
            await self.registry.register_tool(
                name=name,
                handler=handler,
                parameters=parameters,
                description=description,
                source=ToolSource.API_WRAPPER,
                config=config,
            )
        else:
            # 使用内部方法，不获取锁，不持久化
            await self.registry._register_tool_internal(
                name=name,
                handler=handler,
                parameters=parameters,
                description=description,
                source=ToolSource.API_WRAPPER,
                config=config,
                persist=False,
            )

        return name

    def _create_handler(self, config: dict):
        async def handler(context, **kwargs) -> str:
            url_template = config.get("url", "")
            method = config.get("method", "GET").upper()
            headers = config.get("headers", {}).copy()
            timeout = config.get("timeout", 30)

            try:
                url = self._format_url(url_template, kwargs)
            except KeyError as e:
                return f"Error: Missing required parameter {e}"

            auth_config = config.get("auth", {})
            if auth_config:
                auth_type = auth_config.get("type")
                auth_key = auth_config.get("key")
                auth_header = auth_config.get("header", "Authorization")

                if auth_type and auth_key:
                    auth_value = await self._get_auth(auth_key)
                    if auth_value:
                        if auth_type == "bearer":
                            headers[auth_header] = f"Bearer {auth_value}"
                        elif auth_type == "api_key":
                            headers[auth_header] = auth_value
                        elif auth_type == "basic":
                            import base64
                            encoded = base64.b64encode(auth_value.encode()).decode()
                            headers[auth_header] = f"Basic {encoded}"

            body_template = config.get("body")
            params_template = config.get("params")

            try:
                if method == "GET":
                    params = self._build_params(params_template, kwargs) if params_template else kwargs
                    response = await self.http_client.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=timeout,
                    )
                else:
                    body = self._build_body(body_template, kwargs) if body_template else kwargs
                    response = await self.http_client.request(
                        method=method,
                        url=url,
                        json=body,
                        headers=headers,
                        timeout=timeout,
                    )

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    result = response.json()
                    response_path = config.get("response_path")
                    if response_path:
                        result = self._extract_path(result, response_path)
                    return json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    return response.text

            except httpx.HTTPStatusError as e:
                return f"API Error: HTTP {e.response.status_code} - {e.response.text[:500]}"
            except httpx.TimeoutException:
                return f"API Error: Request timed out after {timeout}s"
            except Exception as e:
                return f"API Error: {str(e)}"

        return handler

    def _format_url(self, template: str, params: dict) -> str:
        return template.format(**params)

    def _build_params(self, template: dict, kwargs: dict) -> dict:
        params = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                param_name = value[1:-1]
                if param_name in kwargs:
                    params[key] = kwargs[param_name]
            else:
                params[key] = value
        return params

    def _build_body(self, template: dict, kwargs: dict) -> dict:
        def replace_values(obj):
            if isinstance(obj, dict):
                return {k: replace_values(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_values(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("{") and obj.endswith("}"):
                param_name = obj[1:-1]
                return kwargs.get(param_name, obj)
            return obj

        return replace_values(template)

    def _build_parameters(self, config: dict) -> dict:
        params = config.get("parameters")
        if params and isinstance(params, dict) and "properties" in params:
            return params

        params_schema = config.get("params_schema", [])
        result = {"type": "object", "properties": {}, "required": []}

        for param in params_schema:
            name = param.get("name")
            if not name:
                continue
            result["properties"][name] = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
            if param.get("required", False):
                result["required"].append(name)

        url_template = config.get("url", "")
        url_params = re.findall(r'\{(\w+)\}', url_template)
        for param in url_params:
            if param not in result["properties"]:
                result["properties"][param] = {
                    "type": "string",
                    "description": f"URL parameter: {param}",
                }
            if param not in result["required"]:
                result["required"].append(param)

        return result

    def _extract_path(self, data: Any, path: str) -> Any:
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            else:
                return None
        return data

    async def _get_auth(self, auth_key: str) -> str:
        if auth_key in self._auth_cache:
            return self._auth_cache[auth_key]

        env_value = os.environ.get(auth_key, "")
        if env_value:
            self._auth_cache[auth_key] = env_value
            return env_value

        return ""

    async def update_tool(self, name: str, config: dict) -> bool:
        if name not in self.registry._tools:
            return False

        await self.registry.unregister_tool(name)
        await self.add_tool(config)
        return True

    async def test_tool(self, config: dict, test_params: dict = None) -> dict:
        handler = self._create_handler(config)
        params = test_params or {}

        try:
            result = await handler(None, **params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        await self.http_client.aclose()
