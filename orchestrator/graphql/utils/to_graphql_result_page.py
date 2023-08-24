from typing import Any

from orchestrator.graphql.pagination import Connection, PageInfo


def to_graphql_result_page(items: list[Any], first: int, after: int, total: int) -> Connection:
    has_next_page = len(items) > first

    page_items = items[:first]
    page_items_length = len(page_items)
    start_cursor = after if page_items_length else None
    end_cursor = after + page_items_length - 1

    return Connection(
        page=page_items,
        page_info=PageInfo(
            has_previous_page=bool(after),
            has_next_page=has_next_page,
            start_cursor=start_cursor,
            end_cursor=end_cursor,
            total_items=total if total else None,
        ),
    )
