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
