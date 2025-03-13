# Scaling the Orchestrator

By default the Orchestrator is capable to handle a reasonable amount of workflows and tasks. For a larger and more
distributed workload we introduced the [Celery library](https://docs.celeryq.dev/en/stable/).

This document describes the two modes in which an Orchestrator instance can run and what you need to configure:
1. running tasks an workflows in a threadpool (default)
2. running the Orchestrator with a number of workflow workers

## Running workflows or tasks within a threadpool

This is the default configuration. workflows and tasks are both scheduled by the same threadpool with equal priority.
If you need to have tasks with a lower priority, you can for example use a scheduler and run them during a quiet
period.

In AppSettings you will notice the default:

```python
class AppSettings(BaseSettings):
    # fields omitted

    EXECUTOR: str = "threadpool"

    # fields omitted
```

## Running workflows or tasks using a worker

Celery concepts are introduced in the [Documentation](https://docs.celeryq.dev/en/stable/getting-started/introduction.html).

When using Celery, the Orchestrator is split into two parts: the orchestrator-api and the orchestrator-worker.

The orchestrator-api functionality is now limited to handling REST requests and delegating them (via one or more
queues) to the orchestrator-worker. The workflows are executed in the orchestrator-worker.


### Queues

Tasks and workflows are submitted on different queues. This allows for independent scaling of
workers that handle low priority tasks and high priority tasks simply by letting the workers listen
to different queues. Currently, there are two queues defined:

- workflows: starting or resuming workflows
- tasks: starting or resuming tasks

By default, [Redis](https://redis.io/) is used for the Celery Broker and Backend. See the next chapter
about implementing on how to change this behaviour.


### Implementing the worker

The orchestrator-core needs to know what workflows a user has defined. This information is only available in the
actual application using the orchestrator-core. Here we will use an example as used withing SURF. The file is
called tasks.py. First we define our own class derived from the Celery base class:

```python
class OrchestratorCelery(Celery):
    def on_init(self) -> None:
        from orchestrator import OrchestratorCore

        app = OrchestratorCore(base_settings=AppSettings())
        init_app(app)  # This will load the workflows
```

The `init_app` should be replaced by your own function that at least makes sure that all the workflows are imported
(which make sure that the are registered) so that the worker can recognize them. This is the minimum implementation
you need, but you might want to add other initialisation that is needed to execute workflows.

Next we instantiate Celery using our own `OrchestratorCelery` class:

```python
broker = f"redis://{AppSettings().CACHE_URI}"
backend = f"rpc://{AppSettings().CACHE_URI}/0"

celery = OrchestratorCelery(
    "proj", broker=broker, backend=backend, include=["orchestrator.services.tasks"]
)

celery.conf.update(result_expires=3600)
```

As you can see in the code above we are using Redis as broker. You can of course replace this by RabbitMQ or
another broker of your choice. See the Celery documentation for more details.

`"orchestrator.services.tasks" ` is the namespace in orchestrator-core where the Celery tasks can be found. At the
moment 4 tasks are defined:

1. `tasks.new_task`: start a new task (delivered on the Task queue)
2. `tasks.new_workflow`: start a new workflow (delivered on the Workflow queue)
3. `tasks.resume_task`: resume an existing task (delivered on the Task queue)
4. `tasks.resume_workflow`: resume an existing workflow (delivered on the Workflow queue)


Finally, we initialise the orchestrator core:

```python
def init_celery() -> None:
    from orchestrator.services.tasks import initialise_celery

    initialise_celery(celery)


# Needed if we load this as a Celery worker because in that case, the application is not started with a user-specified top-level `__main__` module
init_celery()
```

The code above sets our local Celery instance (which initializes the workflows) as the celery instance that is
going to be used by the orchestrator-core. Without this code, the orchestrator-core would be only aware of a limited
set of workflows that are part of orchestrator-core itself.

### An example implementation

When using Celery and Websockets you can use the following example and change it to your needs.

```python
"""This module contains functions and classes necessary for celery worker processes.

When the orchestrator-core's thread process executor is specified as "celery", the `OrchestratorCore` FastAPI
application registers celery-specific task functions and `start_process` and `resume_process` now defer to the
celery task queue.

Celery's task queue enables features like nightly validations by providing a task queue and workers to execute
workflows that are all started in parallel, which would crash a single-threaded orchestrator-core.

The application flow looks like this when "celery" is the executor (and websockets are enabled):

- FastAPI application validates form input, and places a task on celery queue (create new process).
  - If websockets are enabled, a connection should exist already b/t the client and backend.
- FastAPI application begins watching redis pubsub channel for process updates from celery.
- Celery worker picks up task from queue and begins executing.
- On each step completion, it publishes state information to redis pubsub channel.
- FastAPI application grabs this information and publishes it to the client websocket connection.

A celery worker container will start by calling this module instead of `main.py` like so:
```sh
celery -A esnetorch.celery_worker worker -E -l INFO -Q new_tasks,resume_tasks,new_workflows,resume_workflows
```

* `-A` points to this module where the worker class is defined
* `-E` sends task-related events (capturable and monitorable)
* `-l` is the short flag for --loglevel
* `-Q` specifies the queues which the worker should watch for new tasks

See https://workfloworchestrator.org/orchestrator-core/reference-docs/app/scaling for more information.
"""

from uuid import UUID

from celery import Celery
from celery.signals import worker_shutting_down
from orchestrator.db import init_database
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.services.tasks import initialise_celery
from orchestrator.types import BroadcastFunc
from orchestrator.websocket import broadcast_process_update_to_websocket, init_websocket_manager
from orchestrator.websocket.websocket_manager import WebSocketManager
from orchestrator.workflows import ALL_WORKFLOWS
from structlog import get_logger

from esnetorch.settings import app_settings


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
        init_database(app_settings)

        # Prepare the wrapped_websocket_manager
        # Note: cannot prepare the redis connections here as broadcasting is async
        self.websocket_manager = init_websocket_manager(app_settings)
        self.process_broadcast_fn = process_broadcast_fn

        # Load the products and load the workflows
        import esnetorch.products  # noqa: F401  Side-effects
        import esnetorch.workflows  # noqa: F401  Side-effects

        logger.info(
            "Loaded the workflows and products",
            workflows=len(ALL_WORKFLOWS.values()),
            products=len(SUBSCRIPTION_MODEL_REGISTRY.values()),
        )

    def close(self) -> None:
        super().close()


celery = OrchestratorWorker(
    f"{app_settings.SERVICE_NAME}-worker", broker=str(app_settings.CACHE_URI), include=["orchestrator.services.tasks"]
)

if app_settings.TESTING:
    celery.conf.update(backend=str(app_settings.CACHE_URI), task_ignore_result=False)
else:
    celery.conf.update(task_ignore_result=True)

celery.conf.update(
    result_expires=3600,
    worker_prefetch_multiplier=1,
    worker_send_task_event=True,
    task_send_sent_event=True,
)
```

### Running locally

If you want to test your application locally you have to start both the orchestrator-api and one or more workers.
For example:

Start the orchestrator api:

```bash
EXECUTOR="celery" uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

Notice that we are setting `EXECUTOR` to `celery`. Without that variable the api resorts to the default threadpool.

Start a single worker that listens both on the `tasks` and `workflows` queue (indicated by the `-Q` flag):

```bash
celery -A surf.tasks  worker --loglevel=info -Q new_tasks,resume_tasks,new_workflows,resume_workflows
```

Notice that `-A surf.tasks` indicates the module that contains your 'celery.Celery' instance.

The queues are defined in the celery config (see in services/tasks.py):

```python
celery.conf.task_routes = {
    NEW_TASK: {"queue": "tasks"},
    NEW_WORKFLOW: {"queue": "workflows"},
    RESUME_TASK: {"queue": "tasks"},
    RESUME_WORKFLOW: {"queue": "workflows"},
}
```

If you decide to override the queue names in this configuration, you also have to make sure that you also
update the names accordingly after the `-Q` flag.
