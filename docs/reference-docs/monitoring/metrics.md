# Collecting Metrics

The ``orchestrator-core`` is capable of exporting metrics on an API endpoint that is compatible with
[Prometheus](https://prometheus.io). Prometheus is a time-series database that can be used to collect metrics over time,
to give insight in the usage and performance of your orchestrator, the running processes, and its subscriptions.

By default, ``orchestrator-core`` exports metrics for: subscriptions, processes, and the workflow engine. These can be
enabled by enabling the corresponding app setting ``ENABLE_PROMETHEUS_METRICS_ENDPOINT``. An API response on
``/api/metrics`` with the default metrics enabled looks as follows:

```shell
# HELP wfo_subscriptions_count Number of subscriptions per product, lifecycle state, customer, and in sync state.
# TYPE wfo_subscriptions_count gauge
wfo_subscriptions_count{customer_id="00000000-0000-0000-0000-000000000000",insync="True",lifecycle_state="active",product_name="Router"} 53.0
wfo_subscriptions_count{customer_id="00000000-0000-0000-0000-000000000000",insync="True",lifecycle_state="active",product_name="IP trunk"} 52.0
wfo_subscriptions_count{customer_id="00000000-0000-0000-0000-000000000000",insync="True",lifecycle_state="active",product_name="Site"} 36.0
wfo_subscriptions_count{customer_id="00000000-0000-0000-0000-000000000000",insync="True",lifecycle_state="terminated",product_name="Router"} 22.0
# HELP wfo_process_count Number of processes per status, creator, task, product, workflow, customer, and target.
# TYPE wfo_process_count gauge
wfo_process_count{created_by="SYSTEM",customer_id="00000000-0000-0000-0000-000000000000",is_task="True",last_status="completed",product_name="IP trunk",workflow_name="validate_iptrunk",workflow_target="SYSTEM"} 5755.0
wfo_process_count{created_by="SYSTEM",customer_id="00000000-0000-0000-0000-000000000000",is_task="True",last_status="completed",product_name="Router",workflow_name="validate_router",workflow_target="SYSTEM"} 4066.0
wfo_process_count{created_by="SYSTEM",customer_id="12345678-1234-abcd-deff-123456789012",is_task="True",last_status="completed",product_name="Edge Port",workflow_name="validate_edge_port",workflow_target="SYSTEM"} 133.0
# HELP wfo_process_seconds_total_count Total time spent on processes in seconds.
# TYPE wfo_process_seconds_total_count gauge
wfo_process_seconds_total_count{created_by="SYSTEM",customer_id="00000000-0000-0000-0000-000000000000",is_task="True",last_status="completed",product_name="IP trunk",workflow_name="validate_iptrunk",workflow_target="SYSTEM"} 3.11e+06
wfo_process_seconds_total_count{created_by="SYSTEM",customer_id="00000000-0000-0000-0000-000000000000",is_task="True",last_status="completed",product_name="Router",workflow_name="validate_router",workflow_target="SYSTEM"} 6.72e+06
wfo_process_seconds_total_count{created_by="SYSTEM",customer_id="12345678-1234-abcd-deff-123456789012",is_task="True",last_status="completed",product_name="Edge Port",workflow_name="validate_edge_port",workflow_target="SYSTEM"} 6514.921
# HELP wfo_engine_status Current workflow engine status.
# TYPE wfo_engine_status gauge
wfo_engine_status{wfo_engine_status="PAUSED"} 0.0
wfo_engine_status{wfo_engine_status="PAUSING"} 0.0
wfo_engine_status{wfo_engine_status="RUNNING"} 1.0
# HELP wfo_active_process_count Number of currently running processes in the workflow engine.
# TYPE wfo_active_process_count gauge
wfo_active_process_count 5.0
```

An example Grafana dashboard that uses these metrics is given in the code repository in `grafana-example.json`.

`wfo_engine_status` and `wfo_active_process_count` are derived from the same worker/queue status data as the
`/api/settings/worker-status` endpoint.

### Flower worker metrics

If you run [Flower](https://flower.readthedocs.io/en/latest/) alongside your Celery workers (see
[Monitoring Celery with Flower](../../guides/scaling.md#monitoring-celery-with-flower)), `WorkerCollector`
re-exposes a subset of Flower's own `/metrics` endpoint under `/api/metrics`, unchanged. It requires
`FLOWER_URL` to be set and yields nothing if Flower is unset or unreachable — there is no fallback to Celery's
`inspect()` API for these metrics, since inspecting every worker on each scrape would be too costly to do by
default. Flower's per-task runtime histogram and event counter are excluded, since their cardinality grows
with the number of distinct task names. With Flower configured, it adds this subset to the metrics:

```shell
# HELP flower_worker_online Worker online status.
# TYPE flower_worker_online gauge
flower_worker_online{worker="celery@worker1"} 1.0
# HELP flower_worker_number_of_currently_executing_tasks Number of currently executing tasks.
# TYPE flower_worker_number_of_currently_executing_tasks gauge
flower_worker_number_of_currently_executing_tasks{worker="celery@worker1"} 2.0
# HELP flower_worker_prefetched_tasks Number of prefetched tasks.
# TYPE flower_worker_prefetched_tasks gauge
flower_worker_prefetched_tasks{task="orchestrator.workflow.run_workflow",worker="celery@worker1"} 1.0
```

## Adding custom metrics

It's possible to add more metric collectors to your orchestrator, if there are organization-specific metrics you want
to keep track of. This is done by implementing extra metrics from the ``prometheus_client`` library, documentation on
how to achieve this is available [here](https://prometheus.github.io/client_python/).

When your new collector is implemented, register it in the orchestrator metrics registry when initializing your
orchestrator with ``ORCHESTRATOR_METRICS_REGISTRY.register(MyNewCollector())``.
