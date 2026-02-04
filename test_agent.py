#!/usr/bin/env python3

import json
import sys
import uuid

import httpx


def test_agent(query: str, base_url: str = "http://localhost:8080", thread_id: str | None = None):
    """Test the agent with a query."""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    if thread_id is None:
        thread_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    print(f"Thread ID: {thread_id}")
    print(f"Run ID: {run_id}\n")

    endpoint = f"{base_url}/api/agent/"
    request_body = {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [{"role": "user", "id": "msg-1", "content": query}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }

    text_buffer = ""
    current_message_id = None
    tool_args_buffer = ""

    try:
        with httpx.stream(
            "POST",
            endpoint,
            json=request_body,
            headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
            timeout=60.0,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue

                event_json = line[6:].strip()  # Remove "data: " prefix and whitespace

                try:
                    event_data = json.loads(event_json)
                    event_type = event_data.get("type")

                    # Buffer text message content
                    if event_type == "TEXT_MESSAGE_START":
                        current_message_id = event_data.get("messageId")
                        text_buffer = ""
                    elif event_type == "TEXT_MESSAGE_CONTENT":
                        text_buffer += event_data.get("delta", "")
                    elif event_type == "TEXT_MESSAGE_END":
                        # Print buffered text as single event
                        print(
                            json.dumps(
                                {"type": "TEXT_MESSAGE", "messageId": current_message_id, "content": text_buffer},
                                indent=2,
                            )
                        )
                        text_buffer = ""
                        current_message_id = None
                    # Buffer tool call args
                    elif event_type == "TOOL_CALL_START":
                        tool_args_buffer = ""
                        print(json.dumps(event_data, indent=2))
                    elif event_type == "TOOL_CALL_ARGS":
                        tool_args_buffer += event_data.get("delta", "")
                    elif event_type == "TOOL_CALL_END":
                        # Add buffered args to the event
                        if tool_args_buffer:
                            try:
                                event_data["arguments"] = json.loads(tool_args_buffer)
                            except json.JSONDecodeError:
                                event_data["arguments"] = tool_args_buffer
                        print(json.dumps(event_data, indent=2))
                        tool_args_buffer = ""
                        current_tool_call_id = None
                    else:
                        # Print all other events
                        print(json.dumps(event_data, indent=2))

                except json.JSONDecodeError as e:
                    print(f"[WARNING] Failed to parse event: {e}")

    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP {e.response.status_code}: {e.response.text}")
    except httpx.RequestError as e:
        print(f"[ERROR] Request failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_agent.py 'your search query' [thread_id]")
        print("\nExamples:")
        print("  python test_agent.py 'Search for renewable energy'")
        print("  python test_agent.py 'export them' <thread-id-from-previous-run>")
        sys.exit(1)

    query = sys.argv[1]
    thread_id = sys.argv[2] if len(sys.argv) > 2 else None
    test_agent(query, thread_id=thread_id)
