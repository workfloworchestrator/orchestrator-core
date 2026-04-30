# Copyright 2019-2026 SURF, GÉANT.
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

import time
from typing import Any

from sqlalchemy import Connection, event
from sqlalchemy.engine import Engine

_listener_registry = []


def monitor_sqlalchemy_queries() -> None:

    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn: Connection, *_args: Any) -> None:
        conn.info["queries_started"] = conn.info.get("queries_started", 0) + 1
        conn.info.setdefault("query_start_time", []).append(time.time())

    _listener_registry.append((Engine, "before_cursor_execute", before_cursor_execute))

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn: Connection, *_args: Any) -> None:
        conn.info["queries_completed"] = conn.info.get("queries_completed", 0) + 1
        total = time.time() - conn.info["query_start_time"].pop(-1)
        conn.info["query_time_spent"] = conn.info.get("query_time_spent", 0.0) + total

    _listener_registry.append((Engine, "after_cursor_execute", after_cursor_execute))


def disable_listeners() -> None:
    while _listener_registry:
        listener = _listener_registry.pop()
        event.remove(*listener)
