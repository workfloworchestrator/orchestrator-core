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
from orchestrator.forms import generate_form
from orchestrator.workflow import ProcessStatus
from orchestrator.settings import app_settings
from orchestrator.db import ProcessTable, ProcessStepTable
from orchestrator.types import InputFormGenerator

logger = get_logger(__name__)


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
                if event.message == ProcessStatus.COMPLETED:
                    await self.disconnect(websocket)
                    break

                await websocket.send_text(event.message)

    async def broadcast_data(self, pid: UUID, data: Dict) -> None:
        await self.broadcast.connect()
        await self.broadcast.publish(f"step_process:{pid}", message=json_dumps(data))

        if data["process"]["status"] == ProcessStatus.COMPLETED:
            await self.broadcast.publish(f"step_process:{pid}", message=ProcessStatus.COMPLETED)
        await self.broadcast.disconnect()


websocket_manager = WebSocketManager(app_settings.WEBSOCKET_BROADCASTER_URL)


def create_websocket_data(process: ProcessTable, step: ProcessStepTable, step_form: InputFormGenerator) -> Dict:
    form = None
    if step_form:
        form = generate_form(step_form, step.state, [])

    return {
        "process": {
            "assignee": process.assignee,
            "step": process.last_step,
            "status": process.last_status,
            "last_modified": process.last_modified_at,
        },
        "step": {
            "name": step.name,
            "status": step.status,
            "state": step.state,
            "form": form,
        },
    }


def send_data_to_websocket(pid: int, data: Dict) -> None:
    loop = new_event_loop()
    loop.run_until_complete(websocket_manager.broadcast_data(pid, data))
    loop.close()
