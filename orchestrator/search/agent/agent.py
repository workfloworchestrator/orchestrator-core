# Copyright 2019-2025 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any, Mapping
from langfuse import get_client

import json
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic_ai.ag_ui import StateDeps, handle_ag_ui_request
from pydantic_ai.agent import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from starlette.responses import Response
from langfuse import observe

from llm_guard import scan_output, scan_prompt
from llm_guard.input_scanners import Anonymize, PromptInjection, TokenLimit, Toxicity
from llm_guard.output_scanners import Deanonymize, NoRefusal, Relevance, Sensitive

from orchestrator.search.agent.prompts import get_base_instructions, get_dynamic_instructions
from orchestrator.search.agent.state import SearchState
from orchestrator.search.agent.tools import search_toolset

logger = structlog.get_logger(__name__)
client = get_client()


def _collect_texts(payload: Any) -> list[str]:
    # Recursively collect strings from arbitrary JSON-like data
    texts: list[str] = []
    if isinstance(payload, str):
        texts.append(payload)
    elif isinstance(payload, dict):
        for v in payload.values():
            texts.extend(_collect_texts(v))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            texts.extend(_collect_texts(item))
    return texts


def _any_failed(results: list[dict[str, Any]] | Any) -> bool:
    # Results shape varies by validator; treat any explicit failure as a block.
    try:
        # Common pattern: list of dicts with "valid" or "passed" (True/False)
        if isinstance(results, list):
            for r in results:
                if isinstance(r, dict):
                    if r.get("valid") is False or r.get("passed") is False:
                        return True
        return False
    except Exception:
        # Be conservative if results format is unexpected
        return True

@observe(name="agent_endpoint")
def build_agent_router(model: str | OpenAIModel, toolsets: list[FunctionToolset[Any]] | None = None) -> APIRouter:
    router = APIRouter()

    try:
        toolsets = toolsets + [search_toolset] if toolsets else [search_toolset]

        # Set up LLM-Guard scanners (adjust validators as needed)
        input_scanner =[
                Toxicity(), TokenLimit(),
                PromptInjection()
            ]

        output_scanner = [
                Toxicity(),
            ]

        agent = Agent(
            model=model,
            deps_type=StateDeps[SearchState],
            model_settings=ModelSettings(
                parallel_tool_calls=False,
            ),
            toolsets=toolsets,
            instrument=True,
        )
        agent.instructions(get_base_instructions)
        agent.instructions(get_dynamic_instructions)

        @router.post("/")
        async def agent_endpoint(request: Request) -> Response:
            # Read and cache body once; Starlette caches it for subsequent reads
            raw_body = await request.body()
            body: Any
            try:
                body = json.loads(raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body))
            except Exception:
                body = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body)

            # Collect all input text fragments and scan with LLM-Guard
            input_text = "\n".join(_collect_texts(body))
            try:
                _, sanitized_input, input_results = scan_prompt(scanners=input_scanner,prompt=input_text)
            except Exception as e:
                logger.error("LLM-Guard input scan failed", error=str(e))
                raise HTTPException(status_code=502, detail="Input security scan failed")

            if _any_failed(input_results):
                raise HTTPException(status_code=400, detail={"error": "Blocked by LLM-Guard input policy", "details": input_results})

            # Proceed to agent
            response: Response = await handle_ag_ui_request(agent, request, deps=StateDeps(SearchState()))

            # Scan response body (if available) with LLM-Guard
            try:
                resp_bytes = getattr(response, "body", None)
                if resp_bytes:
                    resp_text = resp_bytes.decode("utf-8") if isinstance(resp_bytes, (bytes, bytearray)) else str(resp_bytes)
                    _, _, output_results = scan_output(scanners=output_scanner,prompt=input_text,output=resp_text)

                    if _any_failed(output_results):
                        # Block or redact; here we block to be safe
                        raise HTTPException(
                            status_code=406,
                            detail={"error": "Blocked by LLM-Guard output policy", "details": output_results},
                        )
            except HTTPException:
                raise
            except Exception as e:
                logger.error("LLM-Guard output scan failed", error=str(e))
                # Fail closed or log-only; here we fail closed to be safe
                raise HTTPException(status_code=502, detail="Output security scan failed")

            return response

        return router
    except Exception as e:
        logger.error("Agent init failed; serving disabled stub.", error=str(e))
        error_msg = f"Agent disabled: {str(e)}"

        @observe(name="agent_endpoint")
        @router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
        async def _disabled(path: str) -> None:
            raise HTTPException(status_code=503, detail=error_msg)

        return router