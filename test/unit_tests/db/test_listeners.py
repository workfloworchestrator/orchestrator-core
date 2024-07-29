from dirty_equals import IsFloat
from sqlalchemy import text

from orchestrator.db import db
from orchestrator.db.listeners import disable_listeners, monitor_sqlalchemy_queries


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
