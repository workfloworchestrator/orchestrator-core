# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import asyncio
import threading
from typing import Any

from fastapi import WebSocket, status
from redis.asyncio import Connection, ConnectionPool
from starlette.concurrency import run_until_first_complete
from starlette.websockets import WebSocketDisconnect
from structlog import get_logger

from orchestrator.utils.json import json_dumps
from orchestrator.utils.redis import RedisBroadcast

logger = get_logger(__name__)


def log_redis_conn(connection: Connection | None) -> dict:
    if not connection:
        return {"conn_type": None}

    connection_attributes = sorted(
        [
            "health_check_interval",
            "socket_keepalive",
            "last_active_at",
            "retry_on_timeout",
            "retry_on_error",
            "port",
            "socket_type",
        ]
    )
    return {
        # "conn_dict": connection.__dict__,
        "conn_type": type(connection),
        "conn_id": id(connection),
    } | {f"conn.{attr}": getattr(connection, attr, "NOTSET") for attr in connection_attributes}


def log_redis_connpool(pool: ConnectionPool) -> dict:
    def to_attr(name: str) -> Any:
        return getattr(pool, name, "NOTSET")

    def to_pool(name: str) -> dict:
        conns = getattr(pool, name, [])
        n = len(conns)
        return {f"{idx}/{n}": log_redis_conn(i) for idx, i in enumerate(conns, start=1)}

    pool_attributes = {
        "max_connections": to_attr,
        "connection_class": to_attr,
        "_available_connections": to_pool,
        "_in_use_connections": to_pool,
    }

    return {"pool_type": type(pool), "pool_id": id(pool)} | {
        f"pool.{attr}": func(attr) for attr, func in pool_attributes.items()
    }


def log_websocket(websocket: WebSocket) -> dict:
    return {
        "client": websocket.client,
        "websocket_key": websocket.headers.get("sec-websocket-key"),
    }


def log_ctx() -> dict:
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None

    thread = threading.current_thread()
    return {
        "thread_name": thread.name,
        "thread_id": thread.ident,
        "asyncio_task": task,
    }


class BroadcastWebsocketManager:
    def __init__(self, broadcast_url: str):
        self.connected: list[WebSocket] = []
        self.broadcast_url = broadcast_url
        self.broadcast = RedisBroadcast(broadcast_url)

    async def connect_redis(self) -> None:
        await self.broadcast.connect()

    async def disconnect_redis(self) -> None:
        await self.broadcast.disconnect()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Connect a new websocket client."""
        self.connected.append(websocket)
        log = logger.bind(channel=channel, **log_websocket(websocket))
        log.debug("Websocket client connected, start loop", total_connections=len(self.connected))
        try:
            await run_until_first_complete(
                (self.sender, {"websocket": websocket, "channel": channel}),
                (self.receiver, {"websocket": websocket, "channel": channel}),
            )
        except Exception as exc:  # noqa: S110
            log.info("Websocket client loop stopped with an exception", message=str(exc))
            try:
                log.info("(experiment) Closing the websocket connection")
                await websocket.close(code=status.WS_1010_MANDATORY_EXT, reason="Loop stopped with an exception")
                log.info("(experiment) Closed the websocket connection")
            except Exception as exc2:
                log.info("(experiment) Closing the websocket connection failed", exc=exc2)
        else:
            log.debug("Websocket client loop stopped normally")
        self.remove_ws_from_connected_list(websocket)

    async def disconnect(
        self, websocket: WebSocket, code: int = status.WS_1000_NORMAL_CLOSURE, reason: dict | str | None = None
    ) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)
        self.remove_ws_from_connected_list(websocket)

    async def disconnect_all(self) -> None:
        for websocket in self.connected:
            await self.disconnect(websocket, code=status.WS_1001_GOING_AWAY, reason="Shutting down")

    async def receiver(self, websocket: WebSocket, channel: str) -> None:
        """Read messages from websocket client."""
        log = logger.bind(channel=channel, **log_websocket(websocket))
        try:
            log.info("Receiver loop starting")
            while True:
                try:
                    message = await websocket.receive_text()
                    log.debug("Received websocket message", message=repr(message))
                except WebSocketDisconnect as disconnect:
                    log.debug("Websocket connection closed by client", code=disconnect.code, reason=disconnect.reason)
                    break
                except Exception as exc:
                    log.info("Exception while reading from websocket", msg=str(exc), klass=exc.__class__)
                    break
                if message == "__ping__":
                    await websocket.send_text("__pong__")
        except Exception:
            log.exception("Unhandled exception in receiver loop")
        finally:
            log.info("Receiver loop stopped")

    async def sender(self, websocket: WebSocket, channel: str) -> None:
        """Read messages from redis channel and send to websocket client."""
        log = logger.bind(channel=channel, **log_websocket(websocket))
        try:

            def parse_message(raw_message: Any) -> str | None:
                match raw_message:
                    case {"type": "message", "data": bytes() as data}:
                        return data.decode()
                    case None:
                        return None
                    case _:
                        log.info("Drop unrecognized message", raw=raw_message)
                        return None

            log.info(
                "Sender loop starting",
                **log_redis_conn(self.broadcast.client.connection),
                **log_redis_connpool(self.broadcast.client.connection_pool),
                **log_ctx(),
            )

            async with self.broadcast.subscriber(channel) as subscriber:
                # TODO: this is sometimes raising a `redis.exceptions.ConnectionError: Error UNKNOWN while writing to socket. Connection lost` when a new client connects
                #  My hypothesis is that it uses a connection (from the pool) which is stale/broken, or being reused incorrectly
                #  Solutions/ideas:
                #  - Add a bunch of logging for connections, connection pools, etc
                #  - [x] (maybe) RedisBroadcast.subscriber was being cancelled and not able to release connection -> fixed with CancelScope(shield=True)
                #  - [ ] (doubtful) try to enable health_check_interval and socket_keepalive in RedisBroadcast
                #  - [ ] (last resort) use redis[hiredis], some search results online point to this as a solution

                log.debug(
                    "Websocket client subscribed to channel",
                    subscriber_dict=subscriber.__dict__,
                    **log_redis_conn(subscriber.connection),
                    **log_redis_connpool(self.broadcast.client.connection_pool),
                    **log_ctx(),
                )
                while True:
                    raw = await subscriber.get_message(timeout=1)
                    if (message := parse_message(raw)) is None:
                        continue

                    log.debug("Send websocket message", message=message)
                    await websocket.send_text(message)
        except Exception:
            log.exception(
                "Unhandled exception in sender loop",
                **log_redis_conn(self.broadcast.client.connection),
                **log_redis_connpool(self.broadcast.client.connection_pool),
                **log_ctx(),
            )
        finally:
            log.info(
                "Sender loop stopped",
                **log_redis_conn(self.broadcast.client.connection),
                **log_redis_connpool(self.broadcast.client.connection_pool),
                **log_ctx(),
            )

    async def broadcast_data(self, channels: list[str], data: dict) -> None:
        """Send messages to redis channel.

        This can be called by API and/or Worker instances.
        """
        message = json_dumps(data)
        async with RedisBroadcast(self.broadcast_url).pipeline() as pipe:
            for channel in channels:
                pipe.publish(channel, message)

    def remove_ws_from_connected_list(self, websocket: WebSocket) -> None:
        if websocket in self.connected:
            self.connected.remove(websocket)
        logger.debug("Websocket client disconnected", total_connections=len(self.connected), **log_websocket(websocket))
