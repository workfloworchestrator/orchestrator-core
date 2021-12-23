# Scheduling tasks in the Orchestrator

This document covers the moving parts needed to schedule jobs in the orchestrator.

## The task file

Tasks have a lot in common with regular workflows.

### Task code

The task code modules are located in `orchestrator/orchestrator/server/workflows/tasks/`. Here is a very bare bones task file:

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
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO workflows(name, target, description)
                VALUES (:name, :target, :description)
            """
        ),
        params,
    )
    pass
```

This just needs to add an entry in the workflows table. No relations with other tables like how the workflow id gets a relation in the products table and etc.

### Running the task in the UI

After the migration is applied, the new task will surface in the UI under the tasks tab. It can be manually executed that way. Even if the task does not have any form input, an entry will still need to be made in `orchestrator-client/src/locale/en.ts` or an error will occur.

```ts
// ESnet
task_sync_from: "Verify and NSO sync",
```

## The schedule file

The schedule file is essentially the crontab associated with the task. They are located in `orchestrator/server/schedules/` - a sample schedule file:

```python
from server.schedules.scheduling import scheduler
from server.services.processes import start_process


@scheduler(name="Nightly sync", time_unit="minutes", period=1)
def run_nightly_sync() -> None:
    start_process("task_sync_from")
```

Yes this runs every minute even though it's called `nightly_sync`. There are other variations on the time units that can be used:

```python
time_unit = "hour", period = 1
time_unit = "hours", period = 6
time_unit = "day", at = "03:00"
time_unit = "day", at = "00:10"
```

And similar to the task/workflow file, the schedule file will need to be registered in `orchestrator/server/schedules/__init__.py`:

```python
from server.schedules.scheduling import SchedulingFunction
from server.schedules.nightly_sync import run_nightly_sync

ALL_SCHEDULERS: List[SchedulingFunction] = [
    run_nightly_sync,
]
```

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
