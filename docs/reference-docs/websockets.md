# Websockets

Orchestrator provides a websocket interface through which the frontend can receive real-time updates. This includes:

* The process overview pages
* The process detail page
* Engine status


## Implementation

To function properly in a scalable architecture, the websocket implementation consists of multiple layers.

The main component is the `WebSocketManager` (WSM) which has the following responsibilities:

1. Keep track of connected frontend clients
2. Forward messages to all frontend clients
3. Provide an interface to pass messages from a backend process (workflow/task)

In a setup with multiple isolated Orchestrator instances the WSM is initialized multiple times as well, therefore clients can be connected to any arbitrary WSM instance.
Letting a backend process broadcast messages to all clients thus requires a message broker, for which we use [Redis Pub/Sub](https://redis.io/docs/manual/pubsub).

There are 2 WSM implementations: a `MemoryWebsocketManager` for development/testing, and a `BroadcastWebsocketManager` that connects to Redis. We'll continue to discuss the latter.

* `BroadcastWebsocketManager.broadcast_data()` is called by backend processes, and publishes messages to a channel in Redis [1]
* `BroadcastWebsocketManager.sender()` starts in a loop for each connected client, subscribes to a channel in Redis, and forwards messages into the websocket connection

[1] When using `EXECUTOR="threadpool"` this function is not called directly, refer to the **ProcessDataBroadcastThread** section

Roughly speaking a message travels through these components:
```
Process
  -> BroadcastWebsocketManager.broadcast_data()
  -> Redis channel
  -> BroadcastWebsocketManager.sender()
  -> Websocket connection
  -> Frontend client
```

### ProcessDataBroadcastThread

**Note**: this section is only relevant when the orchestrator is configured with `EXECUTOR="threadpool"`.

Backend processes are executed in a threadpool and therefore access the same WSM instance. This caused asyncio RuntimeErrors as the async Redis Pub/Sub implementation is not thread-safe.

To solve this there is a dedicated `ProcessDataBroadcastThread` (attached to and managed by the `OrchestratorCore` app) to perform the actual `broadcast_data()` call.

The API endpoints which start/resume/abort a process, call `api_broadcast_process_data(request)` to acquire a function that can be used to submit process updates into a `threading.Queue` on which `ProcessDataBroadcastThread` listens.

## Channel overview

As mentioned in Implementation, messages are organized into channels that clients can listen to.
Each channel has its own usecase and specific message format.

### Events

The `events` channel is designed for the [Orchestrator UI v2](https://github.com/workfloworchestrator/example-orchestrator-ui).
Events are notifications to the UI/user that something happened in the backend API or workers.
They only include the bare minimum of information and can be sent at a high volume.

The API endpoint for this channel is `/api/ws/events` .

Messages in this channel are of the format:
```json
{"name": name, "value": value}
```

Where `name` and `value` are one of the following combinations:

| name                 | value                                                     | Notifies that                                         |
|----------------------|-----------------------------------------------------------|-------------------------------------------------------|
| `"invalidateCache"`  | `{"type": "processes", "id": "LIST"} `                    | A process was started, updated or finished [1]        |
| `"invalidateCache"`  | `{"type": "processes", "id": "<process UUID>"}`           | A process was started, updated or finished [1]        |
| `"invalidateCache"`  | `{"type": "subscriptions", "id": "LIST"} `                | A subscription was created, updated or terminated [1] |
| `"invalidateCache"`  | `{"type": "subscriptions", "id": "<subscription UUID>"} ` | A subscription was created, updated or terminated [1] |
| `"invalidateCache"`  | `{"type": "processStatusCounts"} `                        | A process transitioned to/from a failed state [2]     |
| `"invalidateCache"`  | `{"type": "engineStatus"} `                               | The workflow engine has been enabled or disabled      |

<!-- Hint: an editor like VSCode/PyCharm makes editing markdown tables very easy -->

Notes:
1. The `LIST` and `<uuid>` combinations currently mean one and the same. The reason to keep them separate is that we may want to implement throttling on the `LIST` event.
2. The process status count event is triggered when a process:
   * Transitions to non-failed state -> count may go down:
     1. Non-running process is scheduled to be resumed
     2. Non-running process is deleted from database
   * Transitions to a failed state -> count goes up:
     1. Running process finishes with an error

Example of a complete message:

```json
{"name":"invalidateCache","value":{"type":"engineStatus"}}
```

### Engine settings (deprecated)

The `engine-settings` channel was designed for the now deprecated [Orchestrator UI v1](https://github.com/workfloworchestrator/orchestrator-core-gui).

The API endpoint for this channel is `/api/settings/ws-status/` .

### Processes (deprecated)

The `processes` channel was designed for the now deprecated [Orchestrator UI v1](https://github.com/workfloworchestrator/orchestrator-core-gui).
It sent process list/detail data to the client which it would use to directly update the frontend.

The API endpoint for this channel is `/api/processes/all/` .
