import json
from unittest import mock
from unittest.mock import AsyncMock

from fastapi import HTTPException, WebSocketDisconnect, status
from pytest import raises

from orchestrator.websocket import broadcast_invalidate_cache, sync_broadcast_invalidate_cache


def test_websocket_events_ping_pong(test_client):
    with test_client.websocket_connect("api/ws/events") as websocket:
        websocket.send_text("__ping__")
        assert websocket.receive_text() == "__pong__"


def test_websocket_events_invalidate_cache(test_client):
    with test_client.websocket_connect("api/ws/events") as websocket:
        sync_broadcast_invalidate_cache({"type": "foobar"})
        assert websocket.receive_json() == {"name": "invalidateCache", "value": {"type": "foobar"}}


async def test_websocket_events_invalidate_cache_async(test_client):
    with test_client.websocket_connect("api/ws/events") as websocket:
        await broadcast_invalidate_cache({"type": "foobar", "id": "bar"})
        assert websocket.receive_json() == {"name": "invalidateCache", "value": {"type": "foobar", "id": "bar"}}


@mock.patch("orchestrator.websocket.websocket_manager.authorize_websocket")
@mock.patch("orchestrator.websocket.websocket_manager.authenticate_websocket")
async def test_websocket_events_invalid_protocol(mock_user, mock_security, test_client):
    # when: we create a websocket connection with an invalid protocol
    with raises(WebSocketDisconnect) as error_info:
        with test_client.websocket_connect(
            "api/ws/events", headers={"sec-websocket-protocol": "my token"}
        ) as websocket:
            websocket.send_text("__ping__")
            websocket.receive_text()

    # then: it returns an error with code 1002
    assert error_info.value.code == status.WS_1002_PROTOCOL_ERROR


@mock.patch("orchestrator.websocket.websocket_manager.authorize_websocket")
@mock.patch("orchestrator.websocket.websocket_manager.authenticate_websocket")
async def test_websocket_events_not_authenticated(mock_authenticate_websocket, mock_authorize_websocket, test_client):
    # given: the user is not authenticated
    mock_authenticate_websocket.side_effect = AsyncMock(side_effect=HTTPException(status_code=401))
    mock_authorize_websocket.side_effect = AsyncMock(side_effect=Exception("This should not be called"))

    # when: we create a websocket connection and ping it
    with test_client.websocket_connect("api/ws/events") as websocket:
        websocket.send_text("__ping__")
        reply = websocket.receive_text()

    # then: it does not reply with pong and returns 401
    assert reply != "__pong__"
    assert json.loads(reply) == {"error": {"detail": "Unauthorized", "headers": None, "status_code": 401}}
    assert mock_authenticate_websocket.call_count == 1
    assert mock_authenticate_websocket.call_args[1]["token"] == ""
    assert mock_authorize_websocket.call_count == 0


@mock.patch("orchestrator.websocket.websocket_manager.authorize_websocket")
@mock.patch("orchestrator.websocket.websocket_manager.authenticate_websocket")
async def test_websocket_events_not_authorized(mock_user, mock_security, test_client):
    # given: the user is authenticated but not authorized
    mock_user.side_effect = AsyncMock(return_value={"active": True})
    mock_security.side_effect = AsyncMock(side_effect=HTTPException(status_code=403))

    # when: we create a websocket connection and ping it
    with test_client.websocket_connect(
        "api/ws/events", headers={"sec-websocket-protocol": "base64.bearer.token, my token"}
    ) as websocket:
        websocket.send_text("__ping__")
        reply = websocket.receive_text()

    # then: it does not reply with pong and returns 403
    assert reply != "__pong__"
    assert json.loads(reply) == {"error": {"detail": "Forbidden", "headers": None, "status_code": 403}}
    assert mock_user.call_count == 1
    assert mock_user.call_args[1]["token"] == "my token"  # noqa: S105
    assert mock_security.call_count == 1


@mock.patch("orchestrator.websocket.websocket_manager.authorize_websocket")
@mock.patch("orchestrator.websocket.websocket_manager.authenticate_websocket")
async def test_websocket_events_authorized(mock_user, mock_security, test_client):
    # given: the user is authenticated and authorized
    mock_user.side_effect = AsyncMock(return_value={"active": True})
    mock_security.side_effect = AsyncMock(return_value=True)

    # when: we create a websocket connection and ping it
    with test_client.websocket_connect(
        "api/ws/events", headers={"sec-websocket-protocol": "base64.bearer.token, my token"}
    ) as websocket:
        websocket.send_text("__ping__")
        reply = websocket.receive_text()

    # then: it replies with pong
    assert reply == "__pong__"
    assert mock_user.call_args[1]["token"] == "my token"  # noqa: S105
    assert mock_security.call_count == 1
