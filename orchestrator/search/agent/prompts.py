import json
from textwrap import dedent

import structlog
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps

from orchestrator.search.retrieval.validation import get_structured_filter_schema

from .state import SearchState

logger = structlog.get_logger(__name__)


async def get_base_instructions() -> str:

    try:
        schema_dict = get_structured_filter_schema()
        if schema_dict:
            schema_info = "\n".join([f"    {path}: {field_type}" for path, field_type in schema_dict.items()])
        else:
            schema_info = "    No filterable fields available"
    except Exception as e:
        logger.warning(f"Failed to load schema for prompt: {e}")
        schema_info = "    Schema temporarily unavailable"
    logger.error(f"Generated schema for agent prompt:\n{schema_info}")

    return dedent(
        f"""
    You are a helpful assistant for building and running database queries.

    **Available Data Schema:**
    Use the following schema to understand the available fields.
    When you build filters, each `path` MUST be a valid path from this schema,
    and the operator/value MUST match that path's type.
    ```
{schema_info}
    ```
    **Workflow (do in order):**
    1) `set_search_parameters`  to define the main entity being searched.
    2) Build a complete `FilterTree` (AND at root unless the user asks for OR).
    3) `set_filter_tree(filters=<FilterTree or null>)`.
    4) `execute_search()`.
    5) Summarize the results for the user.
    """
    )


async def get_dynamic_instructions(ctx: RunContext[StateDeps[SearchState]]) -> str:
    """Dynamically generate the system prompt for the agent."""
    param_state = json.dumps(ctx.deps.state.parameters, indent=2, default=str) if ctx.deps.state.parameters else "{}"

    return dedent(
        f"""
        Current search parameters state:
        {param_state}

        Remember:
        - If filters are missing or incomplete, construct a full FilterTree and call `set_filter_tree`.
        - Then call `execute_search`.
        """
    )
