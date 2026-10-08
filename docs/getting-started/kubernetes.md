# Kubernetes

orchestrator-core publishes a Helm chart that runs your orchestrator's own
[processes](deployment.md#processes): the API, the migrations, the scheduler and Celery workers. It
does not run Postgres or Redis. Use managed services in production, or other charts; this page uses
two maintained ones to get a first install running.

The chart's [README](https://github.com/workfloworchestrator/orchestrator-core/blob/main/chart/README.md)
lists every value.

## What you need

- A Kubernetes cluster and Helm 3.8 or later.
- Your orchestrator as an image; see [Building an image](container-image.md). This guide uses
  `ghcr.io/example/my-orchestrator:1.0.0`, built on the `-celery` base image. `1.0.0` is your
  image's version, not orchestrator-core's: the `FROM` line of your Dockerfile pins orchestrator-core,
  so you choose and upgrade it when you build your image.
- For Celery workers, a module that creates your Celery app; see
  [Implementing the worker](../guides/scaling.md#implementing-the-worker). This guide calls it
  `celery_worker`.

## 1. Valkey

[Valkey](https://valkey.io) is the open-source fork of Redis. Install its official chart with a
password:

```yaml title="valkey.yaml"
auth:
  enabled: true
  aclUsers:
    default:
      permissions: "~* &* +@all"
      password: change-me-valkey
```

```shell
helm repo add valkey https://valkey.io/valkey-helm/
helm install valkey valkey/valkey -f valkey.yaml
```

This gives `CACHE_URI=redis://:change-me-valkey@valkey:6379/0`. Without persistence, a Valkey
restart loses what is still queued in it: schedule changes the scheduler has not yet applied, and
Celery tasks no worker has picked up. If that matters, set `dataStorage.enabled: true`.

## 2. Postgres with pgvector

Any Postgres 15 or later with pgvector works. To get started, the
[CloudPirates `postgres` chart](https://github.com/CloudPirates-io/helm-charts/tree/main/charts/postgres)
can run the `pgvector/pgvector` image. The init script creates the
[extensions](deployment.md#postgres-with-pgvector) as superuser, so the orchestrator can run its
migrations as an ordinary user that owns its database:

```yaml title="postgres.yaml"
image:
  registry: docker.io
  repository: pgvector/pgvector
  tag: pg17
auth:
  password: change-me-postgres-admin
customUser:
  name: orchestrator
  database: orchestrator
  password: change-me-postgres
initdb:
  scripts:
    10-extensions.sh: |
      psql -v ON_ERROR_STOP=1 -U postgres -d orchestrator <<'SQL'
      CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
      CREATE EXTENSION IF NOT EXISTS ltree;
      CREATE EXTENSION IF NOT EXISTS unaccent;
      CREATE EXTENSION IF NOT EXISTS pg_trgm;
      CREATE EXTENSION IF NOT EXISTS vector;
      SQL
```

```shell
helm install postgres oci://registry-1.docker.io/cloudpirates/postgres -f postgres.yaml
```

This gives
`DATABASE_URI=postgresql+psycopg://orchestrator:change-me-postgres@postgres:5432/orchestrator`.

!!! warning
    Init scripts only run when the data directory is empty, on first install. Both charts are a
    starting point; for production, use a managed database or a chart you are prepared to operate,
    with backups.

## 3. The orchestrator

Put the connection strings and a session secret in a Secret. With Celery or more than one API
replica, websocket updates go through Valkey too:

```shell
kubectl create secret generic my-orchestrator-env \
  --from-literal=DATABASE_URI='postgresql+psycopg://orchestrator:change-me-postgres@postgres:5432/orchestrator' \
  --from-literal=CACHE_URI='redis://:change-me-valkey@valkey:6379/0' \
  --from-literal=WEBSOCKET_BROADCASTER_URL='redis://:change-me-valkey@valkey:6379/0' \
  --from-literal=SESSION_SECRET="$(openssl rand -hex 32)"
```

```yaml title="orchestrator.yaml"
image:
  repository: ghcr.io/example/my-orchestrator
  tag: "1.0.0"  # your image's version; its FROM line sets the orchestrator-core version
existingSecrets:
  - my-orchestrator-env
env:
  OAUTH2_ACTIVE: "false"  # for this walkthrough only; configure OIDC for anything shared
api:
  replicaCount: 2
scheduler:
  enabled: true
celery:
  enabled: true
  app: celery_worker
```

```shell
helm install my-orchestrator oci://ghcr.io/workfloworchestrator/charts/orchestrator-core \
  --version <chart version> -f orchestrator.yaml
```

This starts two API pods, which run the migrations first, the scheduler, and a `worker-tasks` and a
`worker-workflows` Celery worker. The chart sets `EXECUTOR` and `DISTLOCK_BACKEND` for Celery; see
the chart README's
[Environment](https://github.com/workfloworchestrator/orchestrator-core/blob/main/chart/README.md#environment).

## 4. Check it

```shell
kubectl port-forward svc/my-orchestrator-orchestrator-core 8080:80
curl http://127.0.0.1:8080/api/health/
```

Start a task and watch a worker pick it up:

```shell
curl -X POST -H 'Content-Type: application/json' -d '[{}]' \
  http://127.0.0.1:8080/api/processes/task_clean_up_tasks
kubectl logs deploy/my-orchestrator-orchestrator-core-worker-tasks | grep succeeded
```

## Exposing it

The API is served under `/api`. Enable `httpRoute` (Gateway API) or `ingress` with your host name;
both route `/api` to the API. With `mcp.enabled`, they also route `/mcp` to the
[MCP server](../reference-docs/mcp.md); the image then needs the `mcp` extra, e.g. a `-mcp-celery`
base image. A [UI](orchestration-ui.md) is deployed separately and takes `/` on the same host.

```yaml
httpRoute:
  enabled: true
  parentRefs:
    - name: my-gateway
      sectionName: https
  hostnames:
    - orchestrator.example.net
```

## Next

- Turn authentication on: [Auth(n|z)](../reference-docs/auth-backend-and-frontend.md).
- Tune worker queues and counts: [Scaling the orchestrator](../guides/scaling.md).
- Keep secrets out of values files, e.g. in a key vault: see the chart README's
  [Secrets and certificates from other sources](https://github.com/workfloworchestrator/orchestrator-core/blob/main/chart/README.md#secrets-and-certificates-from-other-sources).
