from __future__ import annotations
import os, sys, re, asyncio
from typing import Any, Dict, List
from urllib.parse import urljoin, urlsplit, parse_qsl

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP, Context

load_dotenv()

API_BASE_URL = os.getenv("SHOP_VIRGE_BACKEND_URL", "").rstrip("/")
API_TOKEN = os.getenv("SHOP_VIRGE_TOKEN", "")
OPENAPI_PATH = "URL HERE/openapi.json"
TIMEOUT = 30.0

_all_get_paths: list[str] = []
mcp = FastMCP("OpenAPI-GET-Resources")
_param_re = re.compile(r"{([^}/]+)}")


def _extract_path_params(path: str) -> List[str]:
    return _param_re.findall(path or "")


def _format_path(path: str, params: Dict[str, Any]) -> str:
    # replace {param} with value from params
    def _sub(match):
        name = match.group(1)
        if name not in params:
            raise ValueError(f"Missing required path parameter: {name}")
        return str(params[name])

    return _param_re.sub(_sub, path)


def _auth_headers() -> Dict[str, str]:
    if API_TOKEN:
        return {"Authorization": f"Bearer {API_TOKEN}"}
    return {}


async def _http_get(relative_path: str, query: Dict[str, Any] | None = None) -> httpx.Response:
    if not API_BASE_URL:
        raise RuntimeError("API_BASE_URL is not set")
    url = urljoin(API_BASE_URL + "/", relative_path.lstrip("/"))
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        return await client.get(url, params=query or {}, headers=_auth_headers())


async def _register_openapi_get_templates() -> None:
    try:
        schema = await _get_openapi()
    except Exception as e:
        sys.stderr.write(f"[OpenAPI] Failed to load schema: {e}\n")
        return

    paths = schema.get("paths") or {}
    for raw_path, methods in paths.items():
        if not isinstance(methods, dict) or "get" not in methods:
            continue

        _all_get_paths.append(raw_path)
        path_params = _extract_path_params(raw_path)

        if not path_params:
            continue

        uri_template = f"api://{raw_path.lstrip('/')}"
        get_meta = methods.get("get") or {}
        summary = get_meta.get("summary") or f"GET {raw_path}"
        description = get_meta.get("description") or "GET resource from FastAPI"

        async def _reader(ctx: Context, **kwargs):
            # Separate path vs query kwargs
            path_kwargs = {k: v for k, v in kwargs.items() if k in path_params}
            query_kwargs = {k: v for k, v in kwargs.items() if k not in path_params}

            # Merge any querystring in the requested URI
            requested_uri = getattr(ctx, "resource_uri", None) or getattr(ctx, "requested_uri", None) or None
            if isinstance(requested_uri, str):
                parts = urlsplit(requested_uri)
                if parts.query:
                    query_kwargs.update(dict(parse_qsl(parts.query)))

            rel = _format_path(raw_path, path_kwargs)
            resp = await _http_get(rel, query_kwargs or None)
            try:
                return resp.json()
            except Exception:
                return resp.text

        mcp.resource(
            uri_template,
            name=summary,
            description=description,
            mime_type="application/json",
        )(_reader)


async def _get_openapi() -> dict:
    if not API_BASE_URL:
        raise RuntimeError("API_BASE_URL is not set")
    url = urljoin(API_BASE_URL + "/", OPENAPI_PATH.lstrip("/"))
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(url, headers=_auth_headers())
    r.raise_for_status()
    return r.json()


@mcp.resource(
    "api://openapi",
    name="OpenAPI Schema",
    description="Raw OpenAPI schema from the FastAPI server",
    mime_type="application/json",
)
async def get_openapi() -> dict:
    return await _get_openapi()


@mcp.resource(
    "api://{path*}",
    name="HTTP GET (catch-all)",
    description="Perform GET against the API base using the given path; querystring supported.",
    mime_type="application/json",
)
async def get_generic(path: str, ctx: Context) -> Any:
    requested_uri = getattr(ctx, "resource_uri", None) or getattr(ctx, "requested_uri", None) or None
    query: Dict[str, Any] = {}
    if isinstance(requested_uri, str):
        parts = urlsplit(requested_uri)
        if parts.query:
            query = dict(parse_qsl(parts.query))
    resp = await _http_get(path, query)
    try:
        return resp.json()
    except Exception:
        return resp.text


@mcp.resource(
    "api://index",
    name="GET endpoints index",
    description="List of all GET paths discovered from OpenAPI",
    mime_type="application/json",
)
async def get_index() -> dict:
    return {"base_url": API_BASE_URL, "get_paths": _all_get_paths}


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    try:
        asyncio.run(_register_openapi_get_templates())
    except Exception as e:
        sys.stderr.write(f"[OpenAPI] preload failed: {e}\n")
    mcp.run()
