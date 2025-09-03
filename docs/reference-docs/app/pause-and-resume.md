# Pausing the Orchestrator

This document explains the different Orchestrator Engine states and outlines the various methods to
pause and resume the Orchestrator engine.

## Orchestrator Engine States
The Orchestrator engine operates in three distinct states that control workflow execution and system behavior.

| Status | Description | Workflow Behavior | Transitions |
| ------ | ----------- | ----------------- | ----------- |
| `RUNNING` | Normal operational state | New workflows can start, existing workflows continue execution | Can transition to `PAUSING` |
| `PAUSING` | Transitional state during shutdown | No new workflows accepted, existing workflows are being gracefully stopped | Automatically transitions to `PAUSED` when complete |
| `PAUSED` | Fully stopped state | No workflow activity, all processes stopped | Can transition back to `RUNNING` |

## Pause and Resume the Orchestrator
There are several ways to pause (and resume) the Orchestrator:

### 1. Using the API

#### Pause Orchestrator
You can send a `PUT` request to the `/api/settings/status` endpoint with the `global_lock` parameter
 set to `true` to pause the Orchestrator. This will stop all running workflows and prevent new
workflows from starting.

Via CLI:
```bash
curl -X PUT http://localhost:8080/api/settings/status \
  -H "Content-Type: application/json" \
  -d '{"global_lock": true}'
```

Using Python:
```python
import requests

response = requests.put(
    "http://localhost:8080/api/settings/status",
    json={"global_lock": True}
)
status = response.json()
```

!!! note
    The Orchestrator Engine State should be `RUNNING` before pausing via above API call.

#### Resume Orchestrator
You can send a `PUT` request to the `/api/settings/status` endpoint with the `global_lock` parameter
 set to `false` to resume the Orchestrator. This will allow new workflows to start and existing
 workflows to continue execution.

```bash
curl -X PUT http://localhost:8080/api/settings/status \
  -H "Content-Type: application/json" \
  -d '{"global_lock": false}'
```

!!! note
    The Orchestrator Engine State should be `PAUSED` before resuming via above API call.

#### API Docs
You can also pause and resume the Orchestrator via the interactive [Swagger UI API docs](http://localhost:8080/api/docs).

### 2. Using the UI
If you have access to the WFO UI (e.g. when running the [`example-orchestrator`](https://github.com/workfloworchestrator/example-orchestrator) or when running both the `orchestrator-core` and [`orchestrator-ui`](../../getting-started/orchestration-ui.md)), you can pause the Orchestrator from there.

1. Navigate to the "Settings" page in the left sidebar.
2. Click the "Pause workflow engine" button.
