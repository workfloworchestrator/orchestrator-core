# Websockets

Orchestrator provides a websocket interface through which the frontend can receive real-time updates. This includes:

* The process overview pages
* The process detail page
* Engine status


## Implementation

To function properly in a scalable architecture, the websocket implentation consists of multiple layers,

The main component is the `WebSocketManager` (WSM) which has the following responsibilities:

1. Keep track of connected frontend clients
2. Forward messages to all frontend clients
3. Provide an interface to pass messages from a backend process (workflow/task)

In a setup with multiple isolated Orchestrator instances the WSM is initialized multiple times as well, therefore clients can be connected to any arbitrary WSM instance.
Letting a backend process broadcast messages to all clients thus requires a message broker, for which we use [Redis Pub/Sub](https://redis.io/docs/manual/pubsub).

There are 2 WSM implementations: a `MemoryWebsocketManager` for development/testing, and a `BroadcastWebsocketManager` that connects to Redis. We'll continue to discuss the latter.

* `BroadcastWebsocketManager.broadcast_data()` is called by backend processes, and publishes messages to a channel in Redis [1]
* `BroadcastWebsocketManager.sender()` starts in a loop for each connected client, subscribes to a channel in Redis, and forwards messages into the websocket connection

[1] Backend processes do not call this function directly, refer to the **ProcessDataBroadcastThread** section

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

Backend processes are executed in a threadpool and therefore access the same WSM instance. This caused asyncio RuntimeErrors as the async Redis Pub/Sub implementation is not thread-safe.

To solve this there is a dedicated `ProcessDataBroadcastThread` (attached to and managed by the `OrchestratorCore` app) to perform the actual `broadcast_data()` call.

The API endpoints which start/resume/abort a process call `api_broadcast_process_data(request)` to acquire a function that can be used to submit process updates into a `threading.Queue` on which `ProcessDataBroadcastThread` listens.
