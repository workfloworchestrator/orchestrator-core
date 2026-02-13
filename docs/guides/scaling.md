# Scaling the Orchestrator

By default the Orchestrator is capable to handle a reasonable amount of workflows and tasks. For a larger and more
distributed workload we introduced the [Celery library](https://docs.celeryq.dev/en/stable/).

This document describes the two modes in which an Orchestrator instance can run and what you need to configure:

1. running tasks and workflows in a threadpool (default)
2. running the Orchestrator with a number of workflow workers

## Running workflows or tasks within a threadpool

This is the default configuration. Workflows and tasks are both scheduled by the same threadpool with equal priority.
If you need to have tasks with a lower priority, you can for example [use a scheduler][use-a-scheduler] and run them during a quiet period.

In AppSettings you will notice the default `"threadpool"`, which can be updated to `"celery"` directly or overridden via the `EXECUTOR` environment variable.

```python
class AppSettings(BaseSettings):
    # fields omitted

    EXECUTOR: str = "threadpool"

    # fields omitted
```

## Running workflows or tasks using a worker

When the orchestrator-core's process executor is specified as `"celery"`, the FastAPI
application registers Celery-specific task functions, and `start_process` and `resume_process` now defer to the Celery task queue.

For those new to Celery, we recommend [the Celery introduction][celery-intro].

When using Celery, the Orchestrator is split into two parts:

1. orchestrator-api
2. orchestrator-worker

The orchestrator-api functionality is now limited to handling REST requests and delegating them (via one or more
queues) to the orchestrator-worker. The workflows are executed in the orchestrator-worker.

The orchestrator-worker has additional dependencies which can be installed with the `celery` dependency group:

```shell
pip install orchestrator-core[celery]
```

Celery's task queue enables features like nightly validations by providing a task queue and workers to execute
workflows that are all started in parallel, which would crash a single-threaded orchestrator-core.

The application flow looks like this when `EXECUTOR = "celery"` and websockets are enabled:

- FastAPI application validates form input and places a task on Celery queue (`tasks.new_workflow`)
    - If websockets are enabled, a connection should exist already between the client and backend.
- FastAPI application begins watching Redis pubsub channel for process updates from Celery.
- Celery worker picks up task from queue and begins executing.
- On each step completion, it publishes state information to the Redis pubsub channel.
- FastAPI application grabs this information and publishes it to the client websocket connection.

By default, [Redis](https://redis.io/) is used for the Celery broker and backend, but these [can be overridden][celery-backends-and-brokers].

### Invoking Celery

A Celery worker must start by calling your worker module instead of `main.py`, like so:

```sh
celery -A your_orch.celery_worker worker -E -l INFO -Q new_tasks,resume_tasks,new_workflows,resume_workflows
```

* `-A` points to this module where the worker class is defined
* `-E` sends task-related events (capturable and monitorable)
* `-l` is the short flag for `--loglevel`
* `-Q` specifies the queues which the worker should watch for new tasks

### Queues

Tasks and workflows are submitted on different queues:

- `tasks`: starting or resuming tasks
- `workflows`: starting or resuming workflows

This allows for independent scaling of workers that handle low priority tasks and high priority workflows simply by letting the workers listen to different queues.
For example, a user starting a CREATE workflow expects timely resolution, and shouldn't have to wait for a scheduled validation to complete in order to start their workflow.

`"orchestrator.services.tasks"` is the namespace in orchestrator-core where the Celery tasks (i.e. Celery jobs, not Orchestrator tasks) can be found.
At the moment, 4 Celery tasks are defined as constants in `services/tasks.py`:

1. `tasks.new_task`: start a new task (delivered on the Task queue)
2. `tasks.new_workflow`: start a new workflow (delivered on the Workflow queue)
3. `tasks.resume_task`: resume an existing task (delivered on the Task queue)
4. `tasks.resume_workflow`: resume an existing workflow (delivered on the Workflow queue)

To handle the Tasks and Workflows queues independently, use the `-Q` option described above.
That is, kick off one worker with

```sh
celery -A your_orch.celery_worker worker -E -l INFO -Q new_tasks,resume_tasks
```

and the other with

```sh
celery -A your_orch.celery_worker worker -E -l INFO -Q new_workflows,resume_workflows
```

The queues are defined in the Celery config in `services/tasks.py`:

```python
celery.conf.task_routes = {
    NEW_TASK: {"queue": "new_tasks"},
    NEW_WORKFLOW: {"queue": "new_workflows"},
    RESUME_TASK: {"queue": "resume_tasks"},
    RESUME_WORKFLOW: {"queue": "resume_workflows"},
}
```

If you decide to override the queue names in this configuration, you must also update the names accordingly after the `-Q` flag.

### Worker count

How many workers one needs for each queue depends on the number of subscriptions they have, what resources (mostly RAM) they have available, and how demanding their workflows/tasks are on external systems.

Currently, SURF recommends 1 worker per queue by default. You can then scale those up after observing which queues experience the most contention for your workflows.

### Implementing the worker

The orchestrator-core needs to know what workflows a user has defined.
After creating workflows, you should have
[registered them][registering-workflows].
For the default threadpool executor, these are exposed to the application by importing them in `main.py`
to ensure the registration calls are made.
When using the Celery executor, you'll need to do this again for the worker instance(s) to run those registrations.

Below is an example implementation of a Celery worker with Websocket support, which can be updated to your project's needs.

```python
"""This module contains functions and classes necessary for celery worker processes.

The application flow looks like this when EXECUTOR = "celery" (and websockets are enabled):

- FastAPI application validates form input, and places a task on celery queue (create new process).
  - If websockets are enabled, a connection should exist already b/t the client and backend.
- FastAPI application begins watching Redis pubsub channel for process updates from celery.
- Celery worker picks up task from queue and begins executing.
- On each step completion, it publishes state information to Redis pubsub channel.
- FastAPI application grabs this information and publishes it to the client websocket connection.
"""

from structlog import get_logger
from uuid import UUID

from celery import Celery
from celery.signals import worker_shutting_down
from nwastdlib.debugging import start_debugger
from orchestrator.db import init_database
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.types import BroadcastFunc
from orchestrator.websocket import broadcast_process_update_to_websocket, init_websocket_manager
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflows import ALL_WORKFLOWS

# Substitute your_orch with your org's Orchestrator instance.
# class AppSettings(OrchSettings):
#     ...
#
# app_settings = AppSettings()
from your_orch.settings import app_settings


logger = get_logger(__name__)


def process_broadcast_fn(process_id: UUID) -> None:
    # Catch all exceptions as broadcasting failure is noncritical to workflow completion
    try:
        broadcast_process_update_to_websocket(process_id)
    except Exception as e:
        logger.exception(e)


class OrchestratorWorker(Celery):
    websocket_manager: WebSocketManager
    process_broadcast_fn: BroadcastFunc

    def on_init(self) -> None:
        # Depending on how you gate your debug settings, you can do something like this:
        # if app_settings.DEBUG:
        #     start_debugger()

        init_database(app_settings)

        # Prepare the wrapped_websocket_manager
        # Note: cannot prepare the redis connections here as broadcasting is async
        self.websocket_manager = init_websocket_manager(app_settings)
        self.process_broadcast_fn = process_broadcast_fn

        # Load the product and workflow modules to register them with the application
        import your_orch.products
        import your_orch.workflows


    def close(self) -> None:
        super().close()


celery = OrchestratorWorker(
    f"{app_settings.SERVICE_NAME}-worker", broker=str(app_settings.CACHE_URI.get_secret_value()), include=["orchestrator.services.tasks"]
)

if app_settings.TESTING:
    celery.conf.update(backend=str(app_settings.CACHE_URI.get_secret_value()), task_ignore_result=False)
else:
    celery.conf.update(task_ignore_result=True)

celery.conf.update(
    result_expires=3600,
    worker_prefetch_multiplier=1,
    worker_send_task_event=True,
    task_send_sent_event=True,
)
```

Create a file with the above, for example `my_orchestrator/celery_client.py`.

Next, update your `main.py` and `wsgi.py` to include the following imports:

```python
from orchestrator.services.tasks import initialise_celery
from my_orchestrator.celery_client import celery
```

And finally, ensure both files include `initialise_celery(celery)` in the initialization of the CLI or API app.

#### Redis

As you can see in the code above, we are using Redis as a broker.
You can of course replace this by RabbitMQ or another broker of your choice.
See the Celery documentation for more details.

### Running locally

If you want to test your application locally you have to start both the orchestrator-api and one or more workers.
For example:

Start the orchestrator API with Celery as the executor:

```bash
EXECUTOR="celery" uvicorn --reload --host 127.0.0.1 --port 8080 wsgi:app
```

Start a single worker that listens both on the `tasks` and `workflows` queue (indicated by the `-Q` flag):

```bash
celery -A surf.tasks  worker --loglevel=info -Q new_tasks,resume_tasks,new_workflows,resume_workflows
```

Notice that `-A surf.tasks` indicates the module that contains your `celery.Celery` instance.


### Celery workflow/task flow

This diagram shows the current flow of how we execute a workflow or task with celery.
It's created to show the reason why a workflow/task can get stuck on `CREATED` or `RESUMED` and what we've done to fix it.
All step statuses are shown in UPPERCASE for clarity.

![Celery Workflow/Task flow](celery-flow.drawio.png)

[registering-workflows]: ../../../getting-started/workflows#register-workflows

[use-a-scheduler]: orchestrator-core/architecture/application/tasks/#the-schedule-file
[celery-intro]: https://docs.celeryq.dev/en/stable/getting-started/introduction.html
[celery-backends-and-brokers]: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html
