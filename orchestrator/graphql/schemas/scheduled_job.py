import strawberry

from orchestrator.schedules.scheduler import ScheduledJob


@strawberry.experimental.pydantic.type(model=ScheduledJob, all_fields=True)
class ScheduledJobGraphql:
    pass
