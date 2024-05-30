import asyncio
import contextlib
from collections import namedtuple
from unittest import mock

import pytest
from fastapi import WebSocket

from orchestrator.settings import app_settings
from orchestrator.websocket import WS_CHANNELS
from orchestrator.websocket.websocket_manager import WebSocketManager


@pytest.fixture
def redis_uri() -> str:
    return str(app_settings.CACHE_URI)


@pytest.fixture
async def websocket_managers(redis_uri):
    async def create_manager():
        wsm = WebSocketManager(True, redis_uri)
        await wsm.connect_redis()
        return wsm

    managers = [await create_manager() for _ in range(2)]

    yield managers

    for manager in managers:
        await manager.disconnect_redis()


FakeWsClient = namedtuple("FakeWsClient", ["client", "stop_event"])


@pytest.fixture
async def websocket_clients(websocket_managers, test_client):
    wsm1, wsm2 = websocket_managers

    def make_client(name: str) -> FakeWsClient:
        # Create a fake websocket client based the WebSocket class
        mock_client = mock.MagicMock(spec_set=WebSocket, name=name)
        stop_event = asyncio.Event()

        block_seconds = 3

        async def blocking_receive_text():
            # Block for block_seconds or until the stop_event has been set
            with contextlib.suppress(asyncio.TimeoutError):
                # Suppress timeout error, if something's wrong this will be seen in the main testcase
                await asyncio.wait_for(stop_event.wait(), block_seconds)
            raise StopAsyncIteration  # End the

        # Make the BroadcastWebsocketManager.receiver() function block, and thereby the .connect() loop
        mock_client.receive_text.side_effect = blocking_receive_text

        def mock_send_text(*_args):
            stop_event.set()

        # When there is a call to WebSocket.send_text(), unblock .receiver() to close the loop
        mock_client.send_text.side_effect = mock_send_text
        return FakeWsClient(mock_client, stop_event)

    # Prepare 2 fake clients
    clients: list[FakeWsClient] = [make_client("Fake Websocket Client 1"), make_client("Fake Websocket Client 2")]

    async with asyncio.TaskGroup() as taskgroup:
        # 'Connect' client 1 to WSM 1
        taskgroup.create_task(wsm1.connect(clients[0].client, WS_CHANNELS.EVENTS))
        # 'Connect' client 2 to WSM 2
        taskgroup.create_task(wsm2.connect(clients[1].client, WS_CHANNELS.EVENTS))

        # Continue the testcase - tasks are cleared on teardown
        yield clients


async def test_broadcast(websocket_managers: list[WebSocketManager], websocket_clients: list[FakeWsClient]):
    """Integration test for websocket broadcasting, requires redis."""
    wsm1, wsm2 = websocket_managers

    # given: 2 websocket clients, each connected to a different WSM
    assert len(websocket_clients) == 2, "Fixture should return 2 clients"
    assert len(wsm1._backend.connected) == 1  # type: ignore
    assert len(wsm2._backend.connected) == 1  # type: ignore

    # when: we broadcast something on WSM 2
    await wsm2.broadcast_data([WS_CHANNELS.EVENTS], {"message": "foobar"})

    # then: both clients should have been sent the broadcasted message
    for client, stop_event in websocket_clients:
        await asyncio.wait_for(stop_event.wait(), 1)
        assert mock.call('{"message":"foobar"}') in client.send_text.mock_calls
