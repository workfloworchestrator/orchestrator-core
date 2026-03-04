#!/usr/bin/env python3
"""Demo: AG-UI client that streams agent events over SSE.

Usage:
    uv run demos/agui_client.py "find active subscriptions"
    uv run demos/agui_client.py "export them" <thread-id-from-previous-run>
"""

import json
import sys
import uuid

import httpx
from ag_ui.core import EventType

URL = "http://localhost:8080/api/agent/"

BUFFERED = {
    EventType.TEXT_MESSAGE_CONTENT,
    EventType.TOOL_CALL_ARGS,
}
SKIPPED = {
    EventType.TEXT_MESSAGE_START,
    EventType.TEXT_MESSAGE_END,
    EventType.TOOL_CALL_START,
    EventType.TOOL_CALL_END,
}


def stream(query: str, thread_id: str | None = None) -> None:
    thread_id = thread_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    print(f"thread={thread_id} run={run_id}\n")

    body = {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [{"role": "user", "id": "msg-1", "content": query}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }

    buffer = ""
    with httpx.stream("POST", URL, json=body, headers={"Accept": "text/event-stream"}, timeout=60.0) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            etype = EventType(event.get("type"))

            if etype in BUFFERED:
                buffer += event.get("delta", "")
            elif etype in SKIPPED:
                if buffer:
                    print(f"  {buffer}")
                    buffer = ""
            else:
                print(json.dumps(event, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    stream(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
