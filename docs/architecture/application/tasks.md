# Scheduling tasks in the Orchestrator

This document covers the moving parts needed to schedule jobs in the orchestrator.

## The task file

Tasks have a lot in common with regular workflows.

### Task code

The task code modules are located in `orchestrator/orchestrator/server/workflows/tasks/`. Here is a very bare-bones task file:

```python
import time

import structlog

from server.targets import Target
from server.types import State
from server.workflow import StepList, done, init, step, workflow

logger = structlog.get_logger(__name__)


@step("NSO calls")
def nso_calls() -> State:
    logger.info("Start NSO calls", ran_at=time.time())
    time.sleep(5)  # Do stuff
    logger.info("NSO calls finished", done_at=time.time())


@workflow("Nightly sync", target=Target.SYSTEM)
def task_sync_from() -> StepList:
    return init >> nso_calls >> done
```

Basically just a workflow with `target=Target.SYSTEM` - and like a workflow it will need to be registered in  `orchestrator/server/workflows/__init__.py`:

```python
# Tasks
LazyWorkflowInstance(".tasks.nightly_sync", "task_sync_from")
```

### The task migration

And also like a workflow, a migration will need to introduce it to the system. It's a stripped down version of the "subscription" workflow migrations:

```python
params = dict(
    name="task_sync_from",
    target="SYSTEM",
    description="Nightly validate and NSO sync",
    is_task=True
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO workflows(name, target, description, is_task)
                VALUES (:name, :target, :description, true)
            """
        ),
        params,
    )
    pass
```

This just needs to add an entry in the workflows table. No relations with other tables like how the workflow id gets a relation in the products table and etc.

### Running the task in the UI

After the migration is applied, the new task will surface in the UI under the tasks tab.
It can be manually executed that way. Even if the task does not have any form input, an entry will still need to be made in `orchestrator-client/src/locale/en.ts` or an error will occur.

```ts
// ESnet
task_sync_from: "Verify and NSO sync",
```

## The schedule file

> from `4.3.0` we switched from [schedule] package to [apscheduler] to allow schedules to be stored in the DB and schedule tasks from the API.

The schedule file is essentially the crontab associated with the task.
They are located in `orchestrator/server/schedules/` - a sample schedule file:

```python
from orchestrator.schedules.scheduler import scheduler
from orchestrator.services.processes import start_process


# previously `scheduler()` which is now deprecated
@scheduler.scheduled_job(id="nightly-sync", name="Nightly sync", trigger="cron", hour=1)
def run_nightly_sync() -> None:
    start_process("task_sync_from")
```

This schedule will start the `task_sync_from` task every day at 01:00.

There are multiple triggers that can be used: [data from docs]

- [IntervalTrigger]: use when you want to run the task at fixed intervals of time.
- [CronTrigger]: use when you want to run the task periodically at certain time(s) of day.
- [DateTrigger]: use when you want to run the task just once at a certain point of time.
- [CalendarIntervalTrigger]: use when you want to run the task on calendar-based intervals, at a specific time of day.
- [AndTrigger]: use when you want to combine multiple triggers so the task only runs when **all** of them would fire at the same time.
- [OrTrigger]: use when you want to combine multiple triggers so the task runs when **any one** of them would fire.

For detailed configuration options, see the [APScheduler scheduling docs].

The scheduler automatically loads any schedules that are imported before the scheduler starts.
To keep things organized and consistent (similar to how workflows are handled), it’s recommended to place your schedules in a `/schedules/__init__.py`.

> `ALL_SCHEDULERS` (Backwards Compatibility)  
> In previous versions, schedules needed to be explicitly listed in an ALL_SCHEDULERS variable.
> This is no longer required, but ALL_SCHEDULERS is still supported for backwards compatibility.


## Executing the task

### Manually / development

When doing development, it is possible to manually make the scheduler run your task even if your Orchestrator instance is not in "scheduler mode." Shell into your running instance and run the following:

```shell
docker exec -it backend /bin/bash
./bin/scheduling force run_nightly_sync
```

Where `run_nightly_sync` is the name defined in the schedule file - not the name of the task. Not necessary to run the UI and you can get the logging output.

### Scheduled execution

The scheduler is a separate process - it isn't just a feature in the backend that gets toggled on. It is possible to run them both in a single container. It's a matter of modifying the Dockerfile to use a wrapper script to start the backend (which also runs the migrations) and then invoking the scheduler.

```docker
EXPOSE 8080
USER www-data:www-data
CMD /usr/src/app/bin/server
# Comment out the previous command and uncomment the
# following lines to build a version that runs the
# backend and scheduer in the same container.
# COPY ./bin/server ./bin/server
# COPY ./bin/scheduling ./bin/scheduling
# COPY ./bin/wrapper ./bin/wrapper
# CMD /usr/src/app/bin/wrapper
```

The scheduler will then run the jobs as they have been scheduled in the schedule files - and they will also be available to be run manually on an ad hoc basis in the UI.

## Developer notes

### Executing multiple tasks

If one needs to execute multiple tasks in concert with each other, one can not call a task from another task. Which is to say, calling `start_process` is a "top level" call. Trying to call it inside an already invoked task does not work.

But the schedule (ie: crontab) files are also code modules so one can achieve the same thing there:

```python
@scheduler(name="Nightly sync", time_unit="day", at="00:10")
def run_nightly_sync() -> None:
    subs = Subscription.query.filter(
        Subscription.description.like("Node%Provisioned")
    ).all()
    logger.info("Node schedule subs", subs=subs)

    for sub in subs:
        sub_id = sub.subscription_id
        logger.info("Validate node enrollment", sub_id=sub_id)
        start_process("validate_node_enrollment", [{"subscription_id": sub_id}])

    start_process("task_sync_from")
```

[schedule]: https://pypi.org/project/schedule/
[apscheduler]: https://pypi.org/project/APScheduler/
[IntervalTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.interval.IntervalTrigger
[CronTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.cron.CronTrigger
[DateTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.date.DateTrigger
[CalendarIntervalTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.calendarinterval.CalendarIntervalTrigger
[AndTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.combining.AndTrigger
[OrTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.combining.OrTrigger
[APScheduler scheduling docs]: https://apscheduler.readthedocs.io/en/master/userguide.html#scheduling-tasks
[data from docs]: https://apscheduler.readthedocs.io/en/master/api.html#triggers
