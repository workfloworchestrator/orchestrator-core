# Docker Compose (example orchestrator)

The [example-orchestrator](https://github.com/workfloworchestrator/example-orchestrator) repository
contains a complete orchestrator with example products and workflows, and a `docker-compose.yml`
that runs it with everything around it. It is the quickest way to see a working setup on your own
machine.

!!! note
    This setup is meant for exploring and for local development. It is opinionated and mounts the
    repository into the containers. To run your own orchestrator, see
    [Running your orchestrator](deployment.md), [Building an image](container-image.md) and
    [Kubernetes](kubernetes.md).

## What it runs

The `docker-compose.yml` starts:

* Orchestrator-core, with the example products and workflows
* Orchestrator-ui
* Postgres
* Redis
* NetBox
* GraphQL Federation

Follow the [README.md](https://github.com/workfloworchestrator/example-orchestrator/blob/master/README.md)
to start it.
