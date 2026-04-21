"""fix_parse_websearch.

Revision ID: 19cdd3ab86f6
Revises: 6896a54e9483
Create Date: 2021-11-17 21:23:09.959694

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "19cdd3ab86f6"
down_revision = "6896a54e9483"
branch_labels = None
depends_on = None


def upgrade() -> None:
    command = """
              CREATE OR REPLACE FUNCTION parse_websearch(config regconfig, search_query text)
              RETURNS tsquery AS $$
              SELECT
                  string_agg(
                      (
                          CASE
                              WHEN position('''' IN words.word) > 0 THEN CONCAT(words.word, ':*')
                              ELSE words.word
                          END
                      ),
                      ' '
                  )::tsquery
              FROM (
                  SELECT trim(
                      regexp_split_to_table(
                          websearch_to_tsquery(config, lower(search_query))::text,
                          ' '
                      )
                  ) AS word
              ) AS words
              $$ LANGUAGE SQL IMMUTABLE;

              CREATE OR REPLACE FUNCTION parse_websearch(search_query text)
              RETURNS tsquery AS $$
              SELECT parse_websearch('pg_catalog.simple', search_query);
              $$ LANGUAGE SQL IMMUTABLE;"""
    op.execute(text(command))


def downgrade() -> None:
    op.execute(text("DROP FUNCTION public.parse_websearch(regconfig, text);"))
    op.execute(text("DROP FUNCTION public.parse_websearch(text);"))
