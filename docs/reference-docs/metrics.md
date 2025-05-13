# Collecting Metrics

The ``orchestrator-core`` is capable of exporting metrics on an API endpoint that is compatible with
[Prometheus](https://prometheus.io). Prometheus is a time-series database that can be used to collect metrics over time,
to give insight in the usage and performance of your orchestrator, the running processes, and its subscriptions.

By default, ``orchestrator-core`` exports metrics for: subscriptions, processes, and the workflow engine. These can be
enabled by enabling the corresponding app setting ``ENABLE_PROMETHEUS_METRICS_ENDPOINT``. An API response on
``/api/metrics`` with the default metrics enabled looks as follows:

```
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

## Adding custom metrics

It's possible to add more metric collectors to your orchestrator, if there are organisation-specific metrics you want
to keep track of. This is done by implementing extra metrics from the ``prometheus_client`` library, documentation on
how to achieve this is available [here](https://prometheus.github.io/client_python/).

When your new collector is implemented, register it in the orchestrator metrics registry when initialising your
orchestrator with ``ORCHESTRATOR_METRICS_REGISTRY.register(MyNewCollector())``.
