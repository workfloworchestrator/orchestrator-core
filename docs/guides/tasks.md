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

## The schedule file

> from `4.3.0` we switched from [schedule] package to [apscheduler] to allow schedules to be stored in the DB and schedule tasks from the API.

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

## The scheduler

The scheduler is invoked via `python main.py scheduler`.
Try `--help` or review the [CLI docs][cli-docs] to learn more.

### Manually executing tasks

When doing development, it is possible to manually make the scheduler run your task even if your Orchestrator instance is not in "scheduler mode."

Shell into your running instance and run the following:

```shell
docker exec -it backend /bin/bash
python main.py scheduler force run_nightly_sync
```

...where `run_nightly_sync` is the job defined in the schedule file - not the name of the task.
This doesn't depend on the UI being up, and you can get the logging output.

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
[trigger docs]: https://apscheduler.readthedocs.io/en/master/api.html#triggers
[registering-workflows]: ../../../getting-started/workflows#register-workflows
[cli-docs]: ../../../reference-docs/cli/#orchestrator.cli.scheduler.show_schedule
