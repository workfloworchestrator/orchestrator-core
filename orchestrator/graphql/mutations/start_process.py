from uuid import UUID

import strawberry
from strawberry.scalars import JSON

from oauth2_lib.strawberry import authenticated_mutation_field
from orchestrator.api.api_v1.endpoints.processes import resolve_user_name
from orchestrator.graphql.types import MutationError, OrchestratorInfo
from orchestrator.services.process_broadcast_thread import graphql_broadcast_process_data
from orchestrator.services.processes import start_process


@strawberry.type(description="Process status")
class ProcessCreated:
    id: UUID


@strawberry.input(description="Payload for process create")
class Payload:
    payload: JSON = strawberry.field(description="Payload")


async def resolve_start_process(
    info: OrchestratorInfo, name: str, payload: Payload, reporter: str | None = None
) -> ProcessCreated | MutationError:
    broadcast_func = graphql_broadcast_process_data(info)

    current_user = None
    if user_resolver := info.context.get_current_user:
        current_user = await user_resolver
    user = resolve_user_name(reporter=reporter, resolved_user=current_user)

    try:
        process_id = start_process(name, user_inputs=payload.payload, user=user, broadcast_func=broadcast_func)
    except Exception as exc:
        return MutationError(message="Could not create process", details=str(exc))

    return ProcessCreated(id=process_id)


@strawberry.type(description="Process mutations")
class ProcessMutation:
    start_process = authenticated_mutation_field(
        resolver=resolve_start_process,
        description="Create a process in the Orchestrator",
    )
