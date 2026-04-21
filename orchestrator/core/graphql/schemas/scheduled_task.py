import strawberry

from orchestrator.core.schedules.scheduler import ScheduledTask


@strawberry.experimental.pydantic.type(model=ScheduledTask, all_fields=True)
class ScheduledTaskGraphql:
    pass
