import structlog
import asyncio
from httpx import AsyncClient
from broadcaster import Broadcast
from starlette.concurrency import run_until_first_complete
from fastapi.websockets import WebSocket
from fastapi.exceptions import HTTPException
from orchestrator.security import oidc_user, opa_security_default
from orchestrator.types import State
from orchestrator.utils.json import json_dumps
from orchestrator.forms import generate_form

logger = structlog.get_logger(__name__)


class WebsocketManager:
    def __init__(self, broadcast_url: str):
        self.broadcast = Broadcast(broadcast_url)

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
            (self.sender, {"websocket": websocket, "pid": pid}),
        )

    async def disconnect(self, websocket, code=1000, reason=""):
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

        if data["name"] == "Done":
            await self.broadcast.publish(f"step_process:{pid}", message="Done")
        await self.broadcast.disconnect()


websocket_manager = WebsocketManager("redis://localhost:6379")


def send_data_to_websocket(pid: str, step: str, state: State, status: str):
    form = None
    if step.form:
        form = generate_form(step.form, state, [])

    step_data = {
        "name": step.name,
        "status": status,
        "state": state,
        "form": form,
    }

    loop = asyncio.new_event_loop()
    loop.run_until_complete(websocket_manager.broadcast_data(pid, step_data))
    loop.close()
