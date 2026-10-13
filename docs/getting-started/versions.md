# Prerequisites
The orchestrator backend has the following requirements

### Backend
For the backend you need the following packages:

* Python >= 3.11
* Postgres >= 15, with the [pgvector](https://github.com/pgvector/pgvector) extension available
  (e.g. the `pgvector/pgvector` images)

### Optional dependencies
* Redis or Valkey: required for the scheduler, Celery workers and more than one API replica
* Docker

See [Running your orchestrator](deployment.md) for what each process needs.
