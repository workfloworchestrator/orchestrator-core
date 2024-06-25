# Docker development
As well as developing within a regular python environment it is also possible to develop with a docker environment.
This method clones our [example-orchestrator](https://github.com/workfloworchestrator/example-orchestrator) repo and
kickstarts the development from this mono-repo setup.

!!! note
    This method of developing is meant for beginners who would like to have a very opinionated version of the
    orchestrator that already has some pre-built integrations.


## Shipped inside this repo
This repo contains a `docker-compose` that builds the following applications:

* Orchestrator-core
* Orchestrator-ui
* Postgres
* Redis
* NetBox
* GraphQL Federation

Furthermore the repository also contains a lot of example code for some of the example products that have been
implemented. If you would like to quickly get to know the application please follow the [README.md](https://github.com/workfloworchestrator/example-orchestrator/blob/master/README.md)
to find out how the docker setup works.
