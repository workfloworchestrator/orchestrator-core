import asyncio

import structlog
import typer
from pydantic import ValidationError

from orchestrator.cli.search.display import display_filtered_paths_only, display_results
from orchestrator.db import db
from orchestrator.search.core.types import EntityType, FilterOp, UIType
from orchestrator.search.filters import EqualityFilter, FilterTree, LtreeFilter, PathFilter
from orchestrator.search.query import engine
from orchestrator.search.query.queries import SelectQuery
from orchestrator.search.query.validation import get_structured_filter_schema

app = typer.Typer(help="Experiment with the subscription search indexes.")

logger = structlog.getLogger(__name__)


@app.command()
def structured(path: str, value: str, entity_type: EntityType = EntityType.SUBSCRIPTION, limit: int = 10) -> None:
    """Finds subscriptions where a specific field path contains an exact value.

    Example:
        dotenv run python main.py search structured "subscription.status" "provisioning"
        ...
        {
            "path": "subscription.status",
            "value": "provisioning"
        },
        ...
    """
    path_filter = PathFilter(path=path, condition=EqualityFilter(op=FilterOp.EQ, value=value), value_kind=UIType.STRING)
    query = SelectQuery(entity_type=entity_type, filters=FilterTree.from_flat_and([path_filter]), limit=limit)
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))
    display_filtered_paths_only(search_response.results, query, db.session)
    display_results(search_response.results, db.session, "Match")


@app.command()
def semantic(query_text: str, entity_type: EntityType = EntityType.SUBSCRIPTION, limit: int = 10) -> None:
    """Finds subscriptions that are conceptually most similar to the query text.

    Example:
        dotenv run python main.py search semantic "Shop for an alligator store"
        ...
        {
            "path": "subscription.shop.shop_description",
            "value": "Kingswood reptiles shop"
        },
        ...
    """
    query = SelectQuery(entity_type=entity_type, query_text=query_text, limit=limit)
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))
    display_results(search_response.results, db.session, "Distance")


@app.command()
def fuzzy(term: str, entity_type: EntityType = EntityType.SUBSCRIPTION, limit: int = 10) -> None:
    """Finds subscriptions containing text similar to the query, tolerating typos.

    Example:
        dotenv run python main.py search fuzzy "Colonel"
        ...
        {
          "path": "description",
          "value": "X Follower WF for TimCoronel"
        },
        ...
    """
    query = SelectQuery(entity_type=entity_type, query_text=term, limit=limit)
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))
    display_results(search_response.results, db.session, "Similarity")


@app.command()
def hierarchical(
    op: str = typer.Argument(..., help="The hierarchical operation to perform."),
    path: str = typer.Argument(..., help="The ltree path or lquery pattern for the operation."),
    query_text: str | None = typer.Option(None, "--query", "-q", help="An optional fuzzy term to rank the results."),
    entity_type: EntityType = EntityType.SUBSCRIPTION,
    limit: int = 10,
) -> None:
    """Performs a hierarchical search, optionally combined with fuzzy ranking.

    Examples:
        dotenv run python main.py search hierarchical is_descendant "subscription.shop" --query "Kingwood"
        dotenv run python main.py search hierarchical matches_lquery "*.x_follower.x_follower_status*"
    """
    try:
        condition = LtreeFilter(value=path, op=op)  # type: ignore[arg-type]
    except (ValueError, ValidationError) as e:
        raise typer.BadParameter(f"Invalid filter: {e}")

    path_filter = PathFilter(path="ltree_hierarchical_filter", condition=condition, value_kind=UIType.STRING)

    query = SelectQuery(
        entity_type=entity_type, filters=FilterTree.from_flat_and([path_filter]), query_text=query_text, limit=limit
    )
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))
    display_results(search_response.results, db.session, "Hierarchical Score")


@app.command()
def hybrid(query_text: str, term: str, entity_type: EntityType = EntityType.SUBSCRIPTION, limit: int = 10) -> None:
    """Performs a hybrid search, combining semantic and fuzzy matching.

    Example:
        dotenv run python main.py search hybrid "reptile store" "Kingswood"
    """
    query = SelectQuery(entity_type=entity_type, query_text=query_text, limit=limit)
    logger.info("Executing Hybrid Search", query_text=query_text, term=term)
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))
    display_results(search_response.results, db.session, "Hybrid Score")


@app.command("generate-schema")
def generate_schema() -> None:
    """Generates and prints the dynamic filter schema from the live search index.

    This queries the index for all distinct non-string paths to be used as
    context for the LLM agent.

    Example:
        dotenv run python main.py search generate-schema
    """

    schema_map = get_structured_filter_schema()

    if not schema_map:
        logger.warning("No filterable paths found in the search index.")
        return

    logger.info("\nAvailable Structured Filters:\n")
    for path, value_type in schema_map.items():
        logger.info(f"- {path}: {value_type}")

    logger.info("Successfully generated dynamic schema.", path_count=len(schema_map))


@app.command("nested-demo")
def nested_demo(entity_type: EntityType = EntityType.SUBSCRIPTION, limit: int = 10) -> None:
    tree = FilterTree.model_validate(
        {
            "op": "AND",
            "children": [
                {
                    "op": "OR",
                    "children": [
                        # First OR case: Active subscriptions from 2024
                        {
                            "op": "AND",
                            "children": [
                                {
                                    "path": "subscription.status",
                                    "condition": {"op": "eq", "value": "active"},
                                    "value_kind": "string",
                                },
                                {
                                    "path": "subscription.start_date",
                                    "condition": {
                                        "op": "between",
                                        "value": {
                                            "start": "2024-01-01T00:00:00Z",
                                            "end": "2024-12-31T23:59:59Z",
                                        },
                                    },
                                    "value_kind": "datetime",
                                },
                            ],
                        },
                        # Second OR case: Terminated subscriptions before 2026
                        {
                            "op": "AND",
                            "children": [
                                {
                                    "path": "subscription.status",
                                    "condition": {"op": "eq", "value": "terminated"},
                                    "value_kind": "string",
                                },
                                {
                                    "path": "subscription.end_date",
                                    "condition": {"op": "lte", "value": "2025-12-31"},
                                    "value_kind": "datetime",
                                },
                            ],
                        },
                    ],
                },
                {
                    "path": "subscription.*.port_mode",
                    "condition": {"op": "matches_lquery", "value": "*.port_mode"},
                    "value_kind": "string",
                },
            ],
        }
    )

    query = SelectQuery(entity_type=entity_type, filters=tree, limit=limit)
    search_response = asyncio.run(engine.execute_search(query=query, db_session=db.session))

    display_results(search_response.results, db.session, "Score")


if __name__ == "__main__":
    app()
