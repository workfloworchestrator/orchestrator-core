# Scaling the Orchestrator

By default the Orchestrator is capable to handle a reasonable amount of workflows and tasks. For a larger and more
distributed workload we introduced the [Celery library](https://docs.celeryq.dev/en/stable/).

This document describes the two modes in which an Orchestrator instance can run and what you need to configure:
1. running tasks an nodes in a threadpool (default)
2. running the Orchestrator with a number of workflow workers

## Running workflows or tasks within a threadpool

This is the default configuration. There is no difference between workflows and tasks. They have the same priority.
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

In AppSettings you first will have to change the `EXECUTOR` field:


```python
class AppSettings(BaseSettings):
    # fields omitted

    EXECUTOR: str = "celery"

    # fields omitted
```

### queues

Tasks and workflows are submitted on different queues. This allows for independent scaling of
pods that handle low priority tasks and high priority tasks simply by letting the workers listen
to different queues. Currently there are two queues defined:

- workflows: starting or resuming workflows
- tasks: starting or resuming tasks

