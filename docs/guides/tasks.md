# Scheduling tasks in the Orchestrator

This document covers the moving parts needed to schedule jobs in the orchestrator.

In short, the scheduler is simply an additional process that adds Tasks to the queue.
A Task is just a workflow that isn't tied to a specific product.
Tasks are created in the same way as workflows, but with the `"system"` target, i.e.

```python
@workflow("Some task", target=Target.SYSTEM)
def some_task() -> StepList:
    return init >> foo >> done
```

Such a workflow will be flagged as a task in the database, and will not have a relation defined connecting it to a specific product.

Note that `@workflow` is a lower-level call than, say, `@create_workflow`.
So instead of `return begin >> foo`, we need to use `return init >> foo >> done` to instantiate a `StepList`.

## The task file

Let's step through a more complete example.
Four things need to happen to register a task:

1. Defining the task via `@workflow`
2. Registering the task via `LazyWorkflowInstance` in your workflows module
3. Writing or generating a migration file
4. Adding a translation for the frontend (necessary for the task to show in the UI)

### Task code

Here is a very bare-bones task file:

```python
# workflows/tasks/nightly_sync.py

import structlog
import time

from orchestrator.targets import Target
from orchestrator.types import State
from orchestrator.workflow import StepList, done, init, step, workflow

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

Again, the task is basically a workflow with `target=Target.SYSTEM`.

And like a workflow, it will need to be registered in your workflows module:

```python
# workflows/__init__.py

# Tasks
LazyWorkflowInstance(".tasks.nightly_sync", "task_sync_from")
```

### The task migration

Like other workflows, a task needs to be [registered in the database][registering-workflows]
in addition to being defined in the code.
However, instead of `create_workflow`, simply use the `create_task` helper instead.

```python
from orchestrator.migrations.helpers import create_task, delete_workflow

new_tasks = [
    {
        "name": "task_sync_from",
        "description": "Nightly validate and NSO sync",
    }
]

def upgrade() -> None:
    conn = op.get_bind()
    for task in new_tasks:
        create_task(conn, task)


def downgrade() -> None:
    conn = op.get_bind()
    for task in new_tasks:
        delete_workflow(conn, task["name"])
```

### Running the task in the UI

After the migration is applied, the new task will surface in the UI under the Tasks tab.
It can be manually executed that way.
Even if the task does not have any form input, an entry will still need to be made in `translations/en-GB.json`.

```json
// translations/en-GB.json
{
  ...
  "workflows": {
    ...
    "task_sync_from": "Verify and NSO sync",
  }
}
```

## The schedule file {: .deprecated }

!!! Warning
    As of [v4.7.0] this is deprecated, and it will be removed in v5.0.0.
    Please use the [new scheduling system](#the-schedule-api) below.

The schedule file is essentially the crontab associated with the task.
Continuing with our previous example:

```python
# schedules/nightly_sync.py

from orchestrator.schedules.scheduler import scheduler
from orchestrator.services.processes import start_process


# previously `scheduler()` which is now deprecated
@scheduler.scheduled_job(id="nightly-sync", name="Nightly sync", trigger="cron", hour=1)
def run_nightly_sync() -> None:
    start_process("task_sync_from")
```

This schedule will start the `task_sync_from` task every day at 01:00.

There are multiple triggers that can be used ([trigger docs]):

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


## The schedule API

!!! Info
    In [v4.4.0] we switched from [schedule] package to [apscheduler] to allow schedules to be stored in the DB and retrieve schedule tasks from the API.
    The apscheduler library has its own decorator to schedule tasks: `@scheduler.scheduled_job()` (from `orchestrator.schedules.scheduler`).
    We therefore deprecated the old `@schedule` decorator (from `orchestrator.schedules.scheduling`) and made it forwards compatible.

    In [v4.7.0] we deprecated `@scheduler.scheduled_job()` provided by [apscheduler] in favor of a more dynamic API based system described below.
    Although we no longer support the `@scheduler.scheduled_job()` decorator, it is still available because it is part of [apscheduler].
    Therefore, we do NOT recommend using it for new schedules. Because you will miss a Linker Table join between schedules and workflows/tasks.

    Consult the [v4.7 upgrade guide] for more details.



Schedules can be created, updated, and deleted via the REST API, and retrieved via the already existing GraphQL API. It
will become possible to manage schedules through the
UI ([development ticket](https://github.com/workfloworchestrator/orchestrator-ui-library/issues/2215)), but you may also
use the API directly to automate configuration of your schedules.

*Example POST*

To create a schedule, you can now simply run a `POST` request to the `/api/schedules` endpoint with a JSON body containing the schedule details.
An example body to create a nightly sync schedule would look like this:

```json
{
  "name": "Nightly Product Validation",
  "workflow_name": "validate_products",
  "workflow_id": "e96cc6bb-9494-4ac1-a572-050988487ee1",
  "trigger": "interval",
  "trigger_kwargs": {
    "hours": 12
  }
}
```

Respectively, you can update or delete schedules via `PUT` and `DELETE` requests to the same endpoint.

*Example PUT*

With `PUT` you can only update the `name`, `trigger`, and `trigger_kwargs` of an existing schedule.
For example, to update the above schedule to run every 24 hours instead of every 12 hours
```json
{
  "schedule_id": "c1b6e5e3-d9f0-48f2-bc65-3c9c33fcf561",
  "name": "Updated Nightly Cleanup",
  "trigger": "interval",
  "trigger_kwargs": {
    "hours": 24
  }
}
```

*Example DELETE*

To delete a schedule, you only need to provide the `schedule_id` in the `DELETE` call
```json
{
  "workflow_id": "b67d4ca7-19fb-4b83-a022-34c6322fb5f1",
  "schedule_id": "1fe43a96-b0f4-4c89-b9b7-87db14bbd8d3"
}
```

There are multiple triggers that can be used ([trigger docs]):

- [IntervalTrigger]: use when you want to run the task at fixed intervals of time.
- [CronTrigger]: use when you want to run the task periodically at certain time(s) of day.
- [DateTrigger]: use when you want to run the task just once at a certain point of time.
- [CalendarIntervalTrigger]: use when you want to run the task on calendar-based intervals, at a specific time of day.
- [AndTrigger]: use when you want to combine multiple triggers so the task only runs when **all** of them would fire at the same time.
- [OrTrigger]: use when you want to combine multiple triggers so the task runs when **any one** of them would fire.

For detailed configuration options, see the [APScheduler scheduling docs].

The scheduler automatically loads any schedules that are imported before the scheduler starts.

!!! Info
    In previous versions, schedules needed to be explicitly added in the `ALL_SCHEDULERS` variable.
    This is no longer required; `ALL_SCHEDULERS` is deprecated as of orchestrator-core v4.7.0 and will be removed in v5.0.0.
    Follow-up ticket to remove deprecated code: [#1276](https://github.com/workfloworchestrator/orchestrator-core/issues/1276)

## The scheduler

The scheduler is invoked via `python main.py scheduler`.
Try `--help` or review the [CLI docs][cli-docs] to learn more.

### Initial schedules

From version orchestrator-core >= `4.7.0`, the scheduler uses the database to store schedules instead of hard-coded schedule files.
Previous versions (orchestrator-core < `4.7.0` had hard-coded schedules. These can be ported to the new system by creating them via the API or CLI.
Run the following CLI command to import previously existing orchestrator-core schedules and change them if needed via the API.

```shell
python main.py scheduler load-initial-schedule
```

> Remember, that if you do not explicitly import these, they will not be available to the scheduler.
### Manually executing tasks

When doing development, it is possible to manually make the scheduler run your task even if your Orchestrator instance is not in "scheduler mode."

Shell into your running instance and run the following:

```shell
docker exec -it backend /bin/bash
python main.py scheduler force "c1b6e5e3-d9f0-48f2-bc65-3c9c33fcf561"
```

...where `c1b6e5e3-d9f0-48f2-bc65-3c9c33fcf561` is the job id of the schedule you want to run.
The job id can be found via the GraphQL API or directly in the database.

### Starting the scheduler

The scheduler runs as a separate process - it isn't just a feature in the backend that gets toggled on.
In short, the scheduler is started by calling `python main.py scheduler run`.
The scheduler will then run the jobs as they have been scheduled in the schedule files - and they will also be available to be run manually on an ad hoc basis in the UI.

When running Orchestrator in Docker, you can run the scheduler in its own container,
or you can fork it from the main process of your backend in a pinch.

The first option can be accomplished by re-using your Orchestrator image with a new entrypoint and command:
```docker
# Dockerfile for scheduler image
FROM your-orchestrator
ENTRYPOINT ["python", "main.py"]
CMD ["scheduler", "run"]
```

For the second option: suppose you start your app with a script, `bin/server`, that handles your migrations, kicks off uvicorn, etc.
You can then replace your backend's Docker entrypoint with a script like this, `bin/wrapper`:

```sh
#!/bin/sh
# bin/wrapper

# Start the scheduler.
python main.py scheduler run &
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to start scheduler: $status"
  exit $status
fi

# Start the server backend process in the background.
/usr/src/app/bin/server
status=$?
if [ $status -ne 0 ]; then
  echo "Failed to start backend: $status"
  exit $status
fi
```

### Decorator vs API
Tasks can be scheduled using the `@scheduler.scheduled_job()` decorator, but this is not recommended for new schedules because it does not create a Linker Table join between schedules and workflows/tasks.
Instead, it is recommended to use the API to create schedules, as described above in the [new scheduling system](#the-schedule-api) section.

From the Frontend, you will not be able to see schedules that were created using the `@scheduler.scheduled_job()` decorator, because we actively filter those out of the GraphQL response. This is because they do not have a Linker Table join between schedules and workflows/tasks, which is necessary for the frontend to display them properly.
If you want to see all schedules, you can:

1. Directly query the database for schedules
2. Run the `python main.py scheduler show-schedule` command to see all schedules, including those created with the `@scheduler.scheduled_job()` decorator.
   3. > This command will effectively run a Database query to list all schedules, including those created with the `@scheduler.scheduled_job()` decorator. It will print the schedule id, name, trigger, and trigger kwargs for each schedule.


Example result for running `python main.py scheduler show-schedule`:

```
                                                                                Scheduled Tasks  
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ id                                             ┃ name                                                           ┃ source    ┃ next run time             ┃ trigger           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 5feb3845-08aa-497e-a475-a4fff8b9aa5f           │ Task Resume Workflows                                          │ API       │ 2026-02-11 13:21:09+00:00 │ interval[1:00:00] │          │
│ 6a00c713-d8e5-46df-9e37-18790c3412ac           │ Task Validate Subscriptions                                    │ API       │ 2026-02-12 00:10:00+00:00 │ cron              │          │
│ import-come-workflow                           │ Import Some Workflow                                           │ decorator │ 2026-02-12 12:00:00+00:00 │ cron              │
└────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────┴───────────┴───────────────────────────┴───────────────────┘

```


<!-- link definitions -->

[schedule]: https://pypi.org/project/schedule/
[apscheduler]: https://pypi.org/project/APScheduler/
[IntervalTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.interval.IntervalTrigger
[CronTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.cron.CronTrigger
[DateTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.date.DateTrigger
[CalendarIntervalTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.calendarinterval.CalendarIntervalTrigger
[AndTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.combining.AndTrigger
[OrTrigger]: https://apscheduler.readthedocs.io/en/master/api.html#apscheduler.triggers.combining.OrTrigger
[APScheduler scheduling docs]: https://apscheduler.readthedocs.io/en/master/userguide.html#scheduling-tasks
[trigger docs]: https://apscheduler.readthedocs.io/en/master/api.html#triggers
[registering-workflows]: ../../../getting-started/workflows#register-workflows
[cli-docs]: ../../../reference-docs/cli/#orchestrator.cli.scheduler.show_schedule
[v4.4.0]: https://github.com/workfloworchestrator/orchestrator-core/releases/tag/4.4.0
[v4.7.0]: https://github.com/workfloworchestrator/orchestrator-core/releases/tag/4.7.0
[v4.7 upgrade guide]: ../guides/upgrading/4.7.md
