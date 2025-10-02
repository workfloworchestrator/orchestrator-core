import structlog
import typer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from orchestrator.db import db
from orchestrator.db.models import AiSearchIndex
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


def drop_all_embeddings() -> int:
    """Drop all records from the ai_search_index table.

    Returns:
        Number of records deleted
    """
    try:
        result = db.session.query(AiSearchIndex).delete()
        db.session.commit()
        logger.info(f"Deleted {result} records from ai_search_index")
        return result

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to drop embeddings records", error=str(e))
        raise


def alter_embedding_column_dimension(new_dimension: int) -> None:
    """Alter the embedding column to use the new dimension size.

    Args:
        new_dimension: New vector dimension size
    """
    try:
        drop_query = text("ALTER TABLE ai_search_index DROP COLUMN IF EXISTS embedding")
        db.session.execute(drop_query)

        add_query = text(f"ALTER TABLE ai_search_index ADD COLUMN embedding vector({new_dimension})")
        db.session.execute(add_query)

        db.session.commit()
        logger.info(f"Altered embedding column to dimension {new_dimension}")

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error("Failed to alter embedding column dimension", error=str(e))
        raise


@app.command("resize")
def resize_embeddings_command() -> None:
    """Resize vector dimensions of the ai_search_index embedding column.

    Compares the current embedding dimension in the database with the configured
    dimension in llm_settings. If they differ, drops all records and alters the
    column to match the new dimension.
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

    if not typer.confirm("This will DELETE ALL RECORDS from ai_search_index and alter the embedding column. Continue?"):
        logger.info("Operation cancelled by user")
        return

    try:
        # Drop all records first.
        logger.info("Dropping all embedding records...")
        deleted_count = drop_all_embeddings()

        # Then alter column dimension.
        logger.info(f"Altering embedding column to dimension {new_dimension}...")
        alter_embedding_column_dimension(new_dimension)

        logger.info(
            "Embedding dimension resize completed successfully",
            records_deleted=deleted_count,
            new_dimension=new_dimension,
        )

    except Exception as e:
        logger.error("Embedding dimension resize failed", error=str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
