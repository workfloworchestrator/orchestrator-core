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

from dirty_equals import IsFloat
from sqlalchemy import text

from orchestrator.core.db import db
from orchestrator.core.db.listeners import disable_listeners, monitor_sqlalchemy_queries


def test_monitor_sqlalchemy_queries():
    monitor_sqlalchemy_queries()

    try:
        db.session.execute(text("select 1"))

        stats = db.session.connection().info.copy()
        assert stats == {
            "queries_completed": 1,
            "queries_started": 1,
            "query_start_time": [],
            "query_time_spent": IsFloat,
        }
    finally:
        disable_listeners()
