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
from time import time_ns

# Set of tool names whose results should be included in A2A artifacts
a2a_result_tools: set[str] = set()


def a2a_result(func):
    """Mark a tool function's output as relevant for A2A artifacts.

    Tools decorated with @a2a_result will have their return values included
    in the A2A task artifact. Tools without this marker (e.g. filter discovery,
    operator validation) are considered intermediate and their results are omitted.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    a2a_result_tools.add(func.__name__)
    return wrapper


def current_timestamp_ms() -> int:
    """Get current timestamp in milliseconds."""
    return time_ns() // 1_000_000


def log_execution_plan(plan) -> None:
    """Print the execution plan for debugging.

    Args:
        plan: ExecutionPlan instance to print
    """
    if not plan:
        print("\n[EXECUTION PLAN] None")  # noqa: T201
        return

    print(f"\n{'='*80}")  # noqa: T201
    print("[EXECUTION PLAN]")  # noqa: T201
    print(f"{'='*80}")  # noqa: T201
    print(f"Current Index: {plan.current_index}/{len(plan.tasks)}")  # noqa: T201
    print(f"Complete: {plan.is_complete}")  # noqa: T201
    print(f"Failed: {plan.failed}")  # noqa: T201
    print(f"\nTasks ({len(plan.tasks)}):")  # noqa: T201

    for i, task in enumerate(plan.tasks):
        marker = "→" if i == plan.current_index else " "
        print(f"\n{marker} [{i+1}] {task.status.value.upper()}")  # noqa: T201
        print(f"    Action: {task.action_type.value}")  # noqa: T201
        print(f"    Reasoning: {task.reasoning}")  # noqa: T201

    print(f"\n{'='*80}\n")  # noqa: T201


def log_agent_request(node_name: str, instructions: str, message_history: list) -> None:
    """Log the complete request being sent to the LLM for debugging.

    Args:
        node_name: Name of the node making the request
        instructions: System instructions/prompt
        message_history: List of ModelRequest/ModelResponse messages
    """
    print(f"\n{'='*80}")  # noqa: T201
    print(f"[{node_name}] LLM Request")  # noqa: T201
    print(f"{'='*80}")  # noqa: T201

    # Print system instructions
    print("\n[INSTRUCTIONS]")  # noqa: T201
    print(instructions)  # noqa: T201

    # Print message history
    if message_history:
        print(f"\n[MESSAGE HISTORY] ({len(message_history)} messages)")  # noqa: T201
        for i, msg in enumerate(message_history, 1):
            print(f"\n--- Message {i} [{msg.kind}] ---")  # noqa: T201
            for part in msg.parts:
                part_type = part.__class__.__name__
                if hasattr(part, "content"):
                    print(f"[{part_type}] {part.content}")  # noqa: T201
                else:
                    print(f"[{part_type}] {part}")  # noqa: T201
    else:
        print("\n[MESSAGE HISTORY] (empty)")  # noqa: T201

    print(f"\n{'='*80}\n")  # noqa: T201
