import structlog
import typer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.db import db
from orchestrator.db.models import AiSearchIndex, SearchQueryTable
from orchestrator.llm_settings import llm_settings

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="embedding",
    help="Resize vector dimensions of the embeddings.",
)


def get_current_embedding_dimension() -> int | None:
    """Get the current dimension of the embedding column from ai_search_index table.

    Returns:
        Current dimension size or None if no records exist or column doesn't exist
    """
    try:
        query = text(
            """
            SELECT vector_dims(embedding) as dimension
            FROM ai_search_index
            WHERE embedding IS NOT NULL
            LIMIT 1
        """
        )
        result = db.session.execute(query).fetchone()
        if result and result[0]:
            return result[0]
        return None

    except SQLAlchemyError as e:
        logger.error("Failed to get current embedding dimension", error=str(e))
        return None


def drop_all_embeddings() -> tuple[int, int]:
    """Drop all records from ai_search_index and search_queries tables.

    Returns:
        Tuple of (ai_search_index records deleted, search_queries records deleted)
    """
    try:
        index_deleted = db.session.query(AiSearchIndex).delete()
        query_deleted = db.session.query(SearchQueryTable).delete()
        db.session.commit()
        logger.info(
            f"Deleted {index_deleted} records from ai_search_index and {query_deleted} records from search_queries"
        )
        return index_deleted, query_deleted

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to drop embeddings records", error=str(e))
        raise


def alter_embedding_column_dimension(new_dimension: int) -> None:
    """Alter the embedding columns in both ai_search_index and search_queries tables.

    Args:
        new_dimension: New vector dimension size
    """
    try:
        db.session.execute(text("ALTER TABLE ai_search_index DROP COLUMN IF EXISTS embedding"))
        db.session.execute(text(f"ALTER TABLE ai_search_index ADD COLUMN embedding vector({new_dimension})"))

        db.session.execute(text("ALTER TABLE search_queries DROP COLUMN IF EXISTS query_embedding"))
        db.session.execute(text(f"ALTER TABLE search_queries ADD COLUMN query_embedding vector({new_dimension})"))

        db.session.commit()
        logger.info(f"Altered embedding columns to dimension {new_dimension} in ai_search_index and search_queries")

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to alter embedding column dimensions", error=str(e))
        raise


@app.command("resize")
def resize_embeddings_command() -> None:
    """Resize vector dimensions of embedding columns in ai_search_index and search_queries tables.

    Compares the current embedding dimension in the database with the configured
    dimension in llm_settings. If they differ, drops all records and alters both
    embedding columns to match the new dimension.
    """
    new_dimension = llm_settings.EMBEDDING_DIMENSION

    logger.info("Starting embedding dimension resize", new_dimension=new_dimension)

    current_dimension = get_current_embedding_dimension()

    if current_dimension is None:
        logger.warning("Could not determine current dimension for embedding column")

    if current_dimension == new_dimension:
        logger.info(
            "Embedding dimensions match, no resize needed",
            current_dimension=current_dimension,
            new_dimension=new_dimension,
        )
        return

    logger.info("Dimension mismatch detected", current_dimension=current_dimension, new_dimension=new_dimension)

    if not typer.confirm(
        "This will DELETE ALL RECORDS from ai_search_index and search_queries tables and alter embedding columns. Continue?"
    ):
        logger.info("Operation cancelled by user")
        return

    try:
        # Drop all records first.
        logger.info("Dropping all embedding records...")
        index_deleted, query_deleted = drop_all_embeddings()

        # Then alter column dimensions.
        logger.info(f"Altering embedding columns to dimension {new_dimension}...")
        alter_embedding_column_dimension(new_dimension)

        logger.info(
            "Embedding dimension resize completed successfully",
            index_records_deleted=index_deleted,
            query_records_deleted=query_deleted,
            new_dimension=new_dimension,
        )

    except Exception as e:
        logger.error("Embedding dimension resize failed", error=str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
