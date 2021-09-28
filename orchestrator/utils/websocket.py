from asyncio import new_event_loop
from structlog import get_logger
from typing import Union, Dict
from httpx import AsyncClient
from broadcaster import Broadcast
from uuid import UUID
from starlette.concurrency import run_until_first_complete
from fastapi.websockets import WebSocket
from fastapi.exceptions import HTTPException
from orchestrator.security import oidc_user, opa_security_default
from orchestrator.utils.json import json_dumps
from orchestrator.types import strEnum
from orchestrator.types import State
from orchestrator.forms import generate_form
from orchestrator.workflow import Step
from orchestrator.settings import app_settings

logger = get_logger(__name__)


class ProcessName(strEnum):
    DONE = "done"


class WebSocketManager:
    def __init__(self, broadcast_url: str):
        self.broadcast = Broadcast(broadcast_url)

    async def authorize(self, websocket: WebSocket, token: str) -> Union[Dict, None]:
        try:
            async with AsyncClient() as client:
                user = await oidc_user(websocket, async_request=client, token=token)
                if user:
                    await opa_security_default(websocket, user, client)
        except HTTPException as e:
            return {"error": vars(e)}
        return None

    async def connect(self, websocket: WebSocket, pid: UUID) -> None:
        await self.broadcast.connect()

        await run_until_first_complete(
            (self.sender, {"websocket": websocket, "pid": pid}),
        )

    async def disconnect(self, websocket: WebSocket, code: int = 1000, reason: Union[Dict, str, None] = None) -> None:
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close(code)

    async def receiver(self, websocket: WebSocket, pid: UUID) -> None:
        async for message in websocket.iter_text():
            pass

    async def sender(self, websocket: WebSocket, pid: UUID) -> None:
        async with self.broadcast.subscribe(channel=f"step_process:{pid}") as subscriber:
            async for event in subscriber:
                if event.message == ProcessName.DONE:
                    await self.disconnect(websocket)
                    break

                await websocket.send_text(event.message)

    async def broadcast_data(self, pid: UUID, data: Dict) -> None:
        await self.broadcast.connect()
        await self.broadcast.publish(f"step_process:{pid}", message=json_dumps({"step": data}))

        if data["name"] == ProcessName.DONE:
            await self.broadcast.publish(f"step_process:{pid}", message=ProcessName.DONE)
        await self.broadcast.disconnect()


websocket_manager = WebSocketManager(app_settings.WEBSOCKET_BROADCASTER_URL)


def send_data_to_websocket(pid: UUID, step: Step, state: State, status: str) -> None:
    form = None
    if step.form:
        form = generate_form(step.form, state, [])

    step_data = {
        "name": step.name,
        "status": status,
        "state": state,
        "form": form,
    }

    loop = new_event_loop()
    loop.run_until_complete(websocket_manager.broadcast_data(pid, step_data))
    loop.close()
