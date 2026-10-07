# orchestrator-core Helm chart

Runs an [orchestrator-core](https://github.com/workfloworchestrator/orchestrator-core) application
on Kubernetes: the API, its database migrations, the scheduler and Celery workers. Postgres and
Redis/Valkey are not part of it.

The [Kubernetes guide](https://workfloworchestrator.org/orchestrator-core/getting-started/kubernetes/)
walks through a complete install, and
[Running your orchestrator](https://workfloworchestrator.org/orchestrator-core/getting-started/deployment/)
lists what each process needs. This file is the values reference.

## Install

```shell
helm install my-orchestrator oci://ghcr.io/workfloworchestrator/charts/orchestrator-core \
  --version <chart version> \
  --set image.repository=ghcr.io/example/my-orchestrator \
  --set image.tag=1.0.0 \
  --set existingSecrets[0]=my-orchestrator-env
```

`image` is your orchestrator, built `FROM` the orchestrator-core image; see
[Building an image](https://workfloworchestrator.org/orchestrator-core/getting-started/container-image/).
`my-orchestrator-env` is a Secret with at least `DATABASE_URI`.

## What it runs

| Component | Kind | Enabled by | Command |
|---|---|---|---|
| API | StatefulSet + Service | always | `api.command` (uvicorn on port 8080) |
| Migrations | init container of each API pod | `migrations.enabled` | `<cli> db upgrade heads` |
| Scheduler | Deployment, 1 replica | `scheduler.enabled` | `<cli> scheduler run`, after `scheduler.initCommands` |
| Celery workers | Deployment per `celery.workers[]` entry | `celery.enabled` | `celery -A <celery.app> worker -Q <queues>` |

On a rollout, API pods start one at a time, so their migrations run one after the other. Pods that
restart together can still run them at the same time; the one that loses fails and is retried.
Every orchestrator container, init containers included, gets the same environment, `volumes` and
`volumeMounts`.

## Environment

Configuration is orchestrator-core's settings, as environment variables. Later sources override
earlier ones:

1. Defaults set by the chart: `TESTING=false` (orchestrator-core defaults it to true, which makes
   the API wait for each workflow), and with `celery.enabled` also `EXECUTOR=celery` and
   `DISTLOCK_BACKEND=redis`.
2. `env`: plain settings, rendered into a ConfigMap together with the defaults.
3. `secretEnv`: a Secret owned by the chart.
4. `existingSecrets`: Secrets you manage, each read whole.
5. `secretProviderClass`: a Secret synced from an Azure key vault by the Secrets Store CSI driver.
6. `extraEnv`: Kubernetes `EnvVar` entries, e.g. with `valueFrom`.

With Celery or more than one API replica, also set `WEBSOCKET_BROADCASTER_URL` to your Redis/Valkey
URL, next to `CACHE_URI`; otherwise each process only sees its own updates.

Pods restart when `env` or `secretEnv` changes.

## Values

Standard Kubernetes passthroughs, applied to every orchestrator pod or container:
`imagePullSecrets`, `serviceAccount`, `podAnnotations`, `podLabels`, `podSecurityContext`,
`securityContext`, `volumes`, `volumeMounts`, `nodeSelector`, `tolerations`, `affinity`, and
`resources` per component.

| Key | Default | Description |
|---|---|---|
| `image.repository`, `image.tag` | `""` | Your orchestrator image. Required. |
| `cli` | `["python", "main.py"]` | Your CLI entrypoint; the chart appends subcommands. |
| `api.replicaCount` | `1` | Set `SESSION_SECRET` when above 1. |
| `api.command` | `python -m uvicorn ... wsgi:app` | Must listen on 8080. |
| `api.livenessProbe` | TCP on 8080 | Does not query the database, so a database outage does not restart the API. |
| `api.readinessProbe` | `GET /api/health/` | |
| `api.extraInitContainers` | `[]` | Run after the migrations. |
| `migrations.enabled` | `true` | |
| `migrations.command` | `[]` | Full command; defaults to `<cli> db upgrade heads`. |
| `scheduler.enabled` | `false` | Needs `CACHE_URI`. |
| `scheduler.initCommands` | `[["scheduler", "load-initial-schedule"]]` | Subcommands appended to `cli`, each an init container. Kubernetes retries a failing one, e.g. until the database is up. |
| `celery.enabled` | `false` | Needs the `celery` extra in your image and `CACHE_URI`. |
| `celery.app` | `""` | Module passed to `celery -A`. Required when enabled. |
| `celery.logLevel` | `info` | |
| `celery.concurrency` | `2` | Processes per worker pod. Celery's own default is one per node CPU, ignoring the pod's CPU limit. |
| `celery.workers` | `tasks`, `workflows` | Each entry: `name`, `queues`, and optionally `replicas`, `concurrency`, `resources`. |
| `service.type`, `service.port` | `ClusterIP`, `80` | |
| `ingress` | disabled | `className`, `annotations`, `hosts`, `tls`; routes `/api`. |
| `httpRoute` | disabled | Gateway API: `parentRefs`, `hostnames`; routes `/api`. |
| `certificate` | disabled | A cert-manager Certificate for `dnsName`, for server and client auth. |
| `secretProviderClass` | disabled | `keyVaultName`, `tenantId`, `nodePublishSecretRefName`, and `objects` as `{key, objectName}`. |

## Selectors

The API selects on `app.kubernetes.io/name: <name>`, the scheduler and workers on
`<name>-scheduler` and `<name>-worker-<worker name>`, each with `app.kubernetes.io/instance`.
Selectors are immutable: changing `nameOverride` or the release name of an install fails the
upgrade.
