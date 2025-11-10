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


from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import structlog
from pydantic_ai import RunContext
from pydantic_ai.ag_ui import StateDeps
from pydantic_ai.exceptions import ModelRetry

from orchestrator.search.core.types import ActionType

if TYPE_CHECKING:
    from orchestrator.search.agent.state import SearchState

logger = structlog.get_logger(__name__)


def require_action(*allowed_actions: ActionType) -> Callable:
    """Validate that the current search action is one of the allowed types.

    This decorator is in preparation for a future finite state machine implementation
    where we explicitly define which actions are valid in which states.

    Example:
        @search_toolset.tool
        @require_action(ActionType.SELECT)
        async def run_search(ctx, ...):
            # Only callable when action is SELECT
            ...

    Args:
        allowed_actions: One or more ActionType values that are valid for this tool.

    Returns:
        Decorated function that validates action before execution.

    Raises:
        ModelRetry: If current action is not in allowed_actions.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(ctx: "RunContext[StateDeps[SearchState]]", *args: Any, **kwargs: Any) -> Any:
            if ctx.deps.state.action is None or ctx.deps.state.query is None:
                logger.warning(f"Action validation failed for {func.__name__}: action or query is None")
                raise ModelRetry("Search action and query are not initialized. Call start_new_search first.")

            current_action = ctx.deps.state.action

            if current_action not in allowed_actions:
                allowed_names = ", ".join(a.value for a in allowed_actions)
                logger.warning(
                    "Invalid action for tool",
                    tool=func.__name__,
                    allowed_actions=allowed_names,
                    current_action=current_action.value,
                )
                raise ModelRetry(
                    f"{func.__name__} is only available for {allowed_names} action(s). "
                    f"Current action is '{current_action.value}'."
                )

            return await func(ctx, *args, **kwargs)

        return wrapper

    return decorator
