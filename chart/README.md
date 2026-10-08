# orchestrator-core Helm chart

![Version: 0.1.0](https://img.shields.io/badge/Version-0.1.0-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square)

Runs an [orchestrator-core](https://github.com/workfloworchestrator/orchestrator-core) application
on Kubernetes: the API, its database migrations, the scheduler and Celery workers. Postgres and
Redis/Valkey are not part of it.

The [Kubernetes guide](https://workfloworchestrator.org/orchestrator-core/getting-started/kubernetes/)
walks through a complete install, and
[Running your orchestrator](https://workfloworchestrator.org/orchestrator-core/getting-started/deployment/)
lists what each process needs.

<!-- Generated from README.md.gotmpl and values.yaml by helm-docs; edit those, not README.md. -->

## Install

```shell
helm install my-orchestrator oci://ghcr.io/workfloworchestrator/charts/orchestrator-core \
  --version <chart version> \
  --set image.repository=ghcr.io/example/my-orchestrator \
  --set image.tag=1.0.0 \
  --set existingSecrets[0]=my-orchestrator-env
```

`image` is your own orchestrator image, built `FROM` the orchestrator-core image; see
[Building an image](https://workfloworchestrator.org/orchestrator-core/getting-started/container-image/).
`image.tag` is a version of that image, `ghcr.io/example/my-orchestrator:1.0.0` here, not an
orchestrator-core version. Which orchestrator-core version runs is decided by your image's `FROM`
line, so you upgrade orchestrator-core by building and tagging a new image. The chart works with any
version and does not pin one. `my-orchestrator-env` is a Secret with at least `DATABASE_URI`.

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

1. Defaults set by the chart: `TESTING=false` (orchestrator-core before 5.5 defaults it to true,
   which makes the API wait for each workflow); with `celery.enabled` also `EXECUTOR=celery` and
   `DISTLOCK_BACKEND=redis`; with `mcp.enabled` also `MCP_ENABLED=true`.
2. `env`: plain settings, rendered into a ConfigMap together with the defaults.
3. `secretEnv`: a Secret owned by the chart.
4. `existingSecrets`: Secrets you manage, each read whole.
5. `extraEnv`: Kubernetes `EnvVar` entries, e.g. with `valueFrom`.

With Celery or more than one API replica, also set `WEBSOCKET_BROADCASTER_URL` to your Redis/Valkey
URL, next to `CACHE_URI`; otherwise each process only sees its own updates.

Pods restart when `env` or `secretEnv` changes.

## Secrets and certificates from other sources

The chart does not create cluster-specific objects, but `extraObjects` renders any extra manifest,
and `volumes`/`volumeMounts` reach every container. For example, to read secrets from a key vault
with the Secrets Store CSI driver: put the SecretProviderClass in `extraObjects`, its CSI volume in
`volumes`/`volumeMounts` (mounting it is what makes the driver sync its Secret), and the synced
Secret in `existingSecrets`. A cert-manager Certificate the orchestrator presents as an mTLS client
certificate works the same way: the Certificate in `extraObjects`, its Secret in
`volumes`/`volumeMounts`. `chart/ci/full-values.yaml` shows both.

Names of these objects are unique per namespace, where other releases and applications can have
their own SecretProviderClass or Certificate. Include the release name, e.g. `{{ .Release.Name }}-kv`:
`extraObjects`, `volumes` and `existingSecrets` are rendered with `tpl`. If a cloud identity is bound
to a specific service account, as with Workload Identity, select it with `serviceAccountName`.

## Selectors

The API selects on `app.kubernetes.io/name: <name>`, the scheduler and workers on
`<name>-scheduler` and `<name>-worker-<worker name>`, each with `app.kubernetes.io/instance`.
Selectors are immutable: changing `nameOverride` or the release name of an install fails the
upgrade.

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | Affinity of every orchestrator pod. |
| api.command | list | `["python","-m","uvicorn","--host","0.0.0.0","--port","8080","wsgi:app"]` | The API process. Must listen on 8080, which the Service and probes use. |
| api.extraInitContainers | list | `[]` | Extra init containers of the API pods, run after the migrations. |
| api.livenessProbe | object | `{"initialDelaySeconds":15,"tcpSocket":{"port":"http"}}` | Liveness probe. TCP, so a database outage does not restart the API. |
| api.readinessProbe | object | `{"httpGet":{"path":"/api/health/","port":"http"},"periodSeconds":5}` | Readiness probe. `/api/health/` checks the database connection. |
| api.replicaCount | int | `1` | API replicas. Set `SESSION_SECRET` when above 1. |
| api.resources | object | `{}` | API container resources. |
| automountServiceAccountToken | bool | `true` | Mount a Kubernetes API token in the pods. The orchestrator does not call the Kubernetes API, but a service mesh can need it: for example, the Linkerd proxy uses it to get its mTLS identity. Set to `false` without one. |
| celery.app | string | `""` | The module that creates your Celery app, passed to `celery -A`. Required when enabled. |
| celery.concurrency | int | `2` | Worker processes per pod, unless a worker sets its own. Celery's default is one per node CPU, ignoring the pod's CPU limit. |
| celery.enabled | bool | `false` | Run Celery workers. Needs the `celery` extra in your image and `CACHE_URI`; sets `EXECUTOR=celery` and `DISTLOCK_BACKEND=redis`. |
| celery.logLevel | string | `"info"` | Celery log level. |
| celery.workers | list | `[{"name":"tasks","queues":["new_tasks","resume_tasks"]},{"name":"workflows","queues":["new_workflows","resume_workflows"]}]` | One Deployment per entry: `name`, `queues`, and optionally `replicas` (default 1, 0 pauses it), `concurrency` and `resources`. |
| cli | list | `["python","main.py"]` | Your CLI entrypoint; the chart appends subcommands such as `db upgrade heads`. |
| env | object | `{}` | Plain environment of every orchestrator container, rendered into a ConfigMap with the chart's defaults. See [Environment](#environment). |
| existingSecrets | list | `[]` | Names of existing Secrets whose keys become environment variables of every orchestrator container. Rendered with `tpl`, e.g. `"{{ .Release.Name }}-kv"`. |
| extraEnv | list | `[]` | Extra env entries (Kubernetes `EnvVar` objects, e.g. with `valueFrom`) for every orchestrator container. |
| extraObjects | list | `[]` | Extra manifests rendered as-is, through `tpl`, e.g. a cert-manager Certificate or a SecretProviderClass. |
| fullnameOverride | string | `""` | Override the full resource name prefix. |
| httpRoute.enabled | bool | `false` | Expose the API with a Gateway API HTTPRoute, routing `/api` (and `/mcp`). |
| httpRoute.hostnames | list | `["chart-example.local"]` | Host names. |
| httpRoute.parentRefs | list | `[{"name":"gateway","sectionName":"http"}]` | Gateways the route attaches to. |
| image.pullPolicy | string | `"IfNotPresent"` | Image pull policy. |
| image.repository | string | `""` | Your own orchestrator image, built FROM the orchestrator-core image. Required. |
| image.tag | string | `""` | Tag of your image, not an orchestrator-core version: your image's `FROM` line pins orchestrator-core. Required; a digest-pinned tag (`1.0@sha256:...`) works. |
| imagePullSecrets | list | `[]` | Image pull secrets for private registries. |
| ingress.annotations | object | `{}` | Ingress annotations, e.g. for cert-manager. |
| ingress.className | string | `""` | Ingress class. |
| ingress.enabled | bool | `false` | Expose the API with an Ingress, routing `/api` (and `/mcp`). |
| ingress.hosts | list | `["chart-example.local"]` | Host names. |
| ingress.tls | list | `[]` | TLS configuration. |
| mcp.enabled | bool | `false` | Serve the MCP server at `/mcp` and route it next to `/api`. Needs the `mcp` extra in your image (a `-mcp` or `-mcp-celery` base image); sets `MCP_ENABLED=true`. Uses the API's authentication. |
| migrations.command | list | `[]` | Full migrations command. Defaults to `<cli> db upgrade heads`. |
| migrations.enabled | bool | `true` | Run the database migrations in an init container of each API pod. |
| nameOverride | string | `""` | Override the chart name in resource names and labels. |
| nodeSelector | object | `{}` | Node selector of every orchestrator pod. |
| podAnnotations | object | `{}` | Annotations on every orchestrator pod. |
| podLabels | object | `{}` | Labels on every orchestrator pod. |
| podSecurityContext | object | `{}` | Pod security context of every orchestrator pod. |
| scheduler.enabled | bool | `false` | Run the scheduler, a singleton that runs scheduled tasks. Needs `CACHE_URI`. |
| scheduler.initCommands | list | `[["scheduler","load-initial-schedule"]]` | Subcommands run in order before the scheduler starts, each appended to `cli` in its own init container. Kubernetes retries a failing one, e.g. until the database is up. |
| scheduler.resources | object | `{}` | Scheduler container resources. |
| secretEnv | object | `{}` | Secret environment of every orchestrator container, rendered into a Secret owned by the chart. |
| securityContext | object | `{}` | Container security context of every orchestrator container. |
| service.port | int | `80` | Service port. |
| service.type | string | `"ClusterIP"` | Service type. |
| serviceAccountName | string | `""` | An existing service account for the pods, e.g. one bound to a cloud identity for Workload Identity. Empty uses the namespace's default account. The chart does not create one. |
| tolerations | list | `[]` | Tolerations of every orchestrator pod. |
| volumeMounts | list | `[]` | Volume mounts on every orchestrator container, init containers included. |
| volumes | list | `[]` | Volumes on every orchestrator pod. Rendered with `tpl`, so names can include `{{ .Release.Name }}`. |
