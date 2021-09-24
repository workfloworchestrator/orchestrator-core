import structlog
import asyncio
from typing import Any
from starlette.concurrency import run_until_first_complete
# from orchestrator.workflow import Process, Step
from orchestrator.utils.json import json_dumps
from broadcaster import Broadcast
from orchestrator.security import oidc_user, opa_security_default
from fastapi.websockets import WebSocket
from fastapi.exceptions import HTTPException
from httpx import AsyncClient
from orchestrator.forms import generate_form

logger = structlog.get_logger(__name__)


class WebsocketManager:
    def __init__(self):
        self.broadcast = Broadcast("redis://localhost:6379")

    async def authorize(self, websocket: WebSocket, token: str):

        try:
            async with AsyncClient() as client:
                user = await oidc_user(websocket.url, async_request=client, token=token)
                await opa_security_default(websocket, user_info=user, async_request=client)
        except HTTPException as e:
            return {"error": vars(e)}
        return

    async def connect(self, websocket, pid):
        await self.broadcast.connect()

        await run_until_first_complete(
            (self.receiver, {"websocket": websocket, "pid": pid}),
            (self.sender, {"websocket": websocket, "pid": pid}),
        )

    async def disconnect(self, websocket, code=1000, reason=''):
        if reason:
            await websocket.send_text(json_dumps(reason))
        await websocket.close()

    async def receiver(self, websocket, pid):
        async for message in websocket.iter_text():
            pass

    async def sender(self, websocket, pid):
        async with self.broadcast.subscribe(channel=f"step_process:{pid}") as subscriber:
            async for event in subscriber:
                if event.message == "Done":
                    await self.disconnect(websocket)
                    break

                await websocket.send_text(event.message)

    async def broadcast_data(self, pid, data):
        await self.broadcast.connect()
        await self.broadcast.publish(f"step_process:{pid}", message=json_dumps({"step": data}))

        if data['name'] == "Done":
            await self.broadcast.publish(f"step_process:{pid}", message="Done")
        await self.broadcast.disconnect()


ws_manager = WebsocketManager()


def send_data_to_websocket(step: Any, step_process_state: Any, process: Any):
    process_state = step_process_state.unwrap()

    if 'process_id' in process:
        pid = process['process_id']
    elif 'process_id' in process_state:
        pid = process_state['process_id']
    form = None
    if step.form:
        form = generate_form(step.form, process, [])

    step_data = {
        "name": step.name,
        "status": step_process_state.status,
        "state": process,
        "form": form,
    }

    loop = asyncio.new_event_loop()
    loop.run_until_complete(ws_manager.broadcast_data(pid, step_data))
    loop.close()
