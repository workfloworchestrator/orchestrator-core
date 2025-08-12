import json
import structlog
from textwrap import dedent

from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps


from .state import SearchState
from orchestrator.search.retrieval.validation import get_structured_filter_schema

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
    When you call `add_filter`, the `path` argument MUST be a valid path according to this schema.
    The chosen filter must be appropiate for the type according to the schema.
    ```
{schema_info}
    ```

    **Your Process (MUST be followed in order):**
    1.  Start by calling `set_search_parameters` to define the main entity being searched.
    2.  Next, call `add_filter` **one time for each filter** required by the user's query, using valid paths from the schema above.
    3.  Finally, when all filters have been added, call `execute_search` to get the results.

    **Example for "Find active subscriptions for customer Surf":**
    1. Call `set_search_parameters(entity_type="SUBSCRIPTION")`
    2. Call `add_filter(path="subscription.status", op="eq", value="active")`
    3. Call `add_filter(path="subscription.customer_id", op="eq", value="Surf")`
    4. Call `execute_search()`

    After `execute_search` is complete, your final response must be a brief summary or answer to the users' query.
    """
    )


async def get_dynamic_instructions(ctx: RunContext[StateDeps[SearchState]]) -> str:
    """Dynamically generate the system prompt for the agent."""
    param_state = json.dumps(ctx.deps.state.parameters, indent=2, default=str) if ctx.deps.state.parameters else "{}"

    return dedent(
        f"""
        Current search parameters state:
        {param_state}
        """
    )
