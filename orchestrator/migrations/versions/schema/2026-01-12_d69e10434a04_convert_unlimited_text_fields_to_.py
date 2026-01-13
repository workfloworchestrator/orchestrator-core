"""Convert unlimited text fields to limited nullable strings and normalize empty strings.

Revision ID: d69e10434a04
Revises: 9736496e3eba
Create Date: 2026-01-12 14:17:58.255515

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "d69e10434a04"
down_revision = "9736496e3eba"
branch_labels = None
depends_on = None

# Field length limits chosen based on expected usage patterns
# These values are intended to be reasonable, but give lots of wiggle room
# If these values are updated, they also need to be updated in orchestrator-core/orchestrator/db/models.py
NOTE_LENGTH = 5000
DESCRIPTION_LENGTH = 2000
FAILED_REASON_LENGTH = 10000
TRACEBACK_LENGTH = 50000
RESOURCE_VALUE_LENGTH = 10000
DOMAIN_MODEL_ATTR_LENGTH = 255

# Materialized view query (from 460ec6748e37 migration - includes UUID search workaround)
SUBSCRIPTIONS_SEARCH_QUERY = """
WITH rt_info AS (SELECT s.subscription_id,
                        concat_ws(
                                ' ',
                                string_agg(rt.resource_type || ' ' || siv.value, ' '),
                                string_agg(distinct 'subscription_instance_id' || ':' || si.subscription_instance_id, ' ')
                        ) AS rt_info
                 FROM subscription_instance_values siv
                          JOIN resource_types rt ON siv.resource_type_id = rt.resource_type_id
                          JOIN subscription_instances si ON siv.subscription_instance_id = si.subscription_instance_id
                          JOIN subscriptions s ON si.subscription_id = s.subscription_id
                 GROUP BY s.subscription_id),
     sub_prod_info AS (SELECT s.subscription_id,
                              array_to_string(
                                      ARRAY ['subscription_id:' || s.subscription_id,
                                          'status:' || s.status,
                                          'insync:' || s.insync,
                                          'subscription_description:' || s.description,
                                          'note:' || coalesce(s.note, ''),
                                          'customer_id:' || s.customer_id,
                                          'product_id:' || s.product_id],
                                      ' '
                              ) AS sub_info,
                              array_to_string(
                                      ARRAY ['product_name:' || p.name,
                                          'product_description:' || p.description,
                                          'tag:' || p.tag,
                                          'product_type:', p.product_type],
                                      ' '
                              ) AS prod_info
                       FROM subscriptions s
                                JOIN products p ON s.product_id = p.product_id),
     fi_info AS (SELECT s.subscription_id,
                        string_agg(fi.name || ':' || fi.value, ' ') AS fi_info
                 FROM subscriptions s
                          JOIN products p ON s.product_id = p.product_id
                          JOIN fixed_inputs fi ON p.product_id = fi.product_id
                 GROUP BY s.subscription_id),
     cust_info AS (SELECT s.subscription_id,
                          string_agg('customer_description: ' || scd.description, ' ') AS cust_info
                   FROM subscriptions s
                            JOIN subscription_customer_descriptions scd ON s.subscription_id = scd.subscription_id
                   GROUP BY s.subscription_id)
-- to_tsvector handles parsing of hyphened words in a peculiar way and is inconsistent with how to_tsquery parses it in Postgres <14
-- Replacing all hyphens with underscores makes the parsing more predictable and removes some issues arising when searching for subscription ids for example
-- See: https://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=0c4f355c6a5fd437f71349f2f3d5d491382572b7
SELECT s.subscription_id,
       to_tsvector(
               'simple',
               replace(
                       concat_ws(
                               ' ',
                               spi.sub_info,
                               spi.prod_info,
                               fi.fi_info,
                               rti.rt_info,
                               ci.cust_info,
                               md.metadata::text
                       ),
                       '-', '_')
       ) as tsv
FROM subscriptions s
         LEFT JOIN sub_prod_info spi ON s.subscription_id = spi.subscription_id
         LEFT JOIN fi_info fi ON s.subscription_id = fi.subscription_id
         LEFT JOIN rt_info rti ON s.subscription_id = rti.subscription_id
         LEFT JOIN cust_info ci ON s.subscription_id = ci.subscription_id
         LEFT JOIN subscription_metadata md ON s.subscription_id = md.subscription_id
"""

# Refresh function with epoch-based throttling (from 460ec6748e37 migration)
REFRESH_FUNCTION = """
CREATE OR REPLACE FUNCTION refresh_subscriptions_search_view()
    RETURNS TRIGGER
    LANGUAGE plpgsql
AS
$$
DECLARE
    should_refresh     bool;
    current_epoch      int;
    last_refresh_epoch int;
    comment_sql        text;
BEGIN
    SELECT extract(epoch from now())::int INTO current_epoch;
    SELECT coalesce(pg_catalog.obj_description('subscriptions_search'::regclass)::int, 0) INTO last_refresh_epoch;

    SELECT (current_epoch - last_refresh_epoch) > 120 INTO should_refresh;

    IF should_refresh THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY subscriptions_search;

        comment_sql := 'COMMENT ON MATERIALIZED VIEW subscriptions_search IS ' || quote_literal(current_epoch);
        EXECUTE comment_sql;
    END IF;
    RETURN NULL;
END;
$$;
"""

# Triggers that depend on the refresh function
TRIGGERS = [
    ("fi_refresh_search", "fixed_inputs", "AFTER UPDATE"),
    ("products_refresh_search", "products", "AFTER UPDATE"),
    ("sub_cust_desc_refresh_search", "subscription_customer_descriptions", "AFTER INSERT OR UPDATE OR DELETE"),
    ("siv_refresh_search", "subscription_instance_values", "AFTER INSERT OR UPDATE OR DELETE"),
    ("sub_refresh_search", "subscriptions", "AFTER INSERT OR UPDATE OR DELETE"),
]


def drop_materialized_view_and_dependencies(conn) -> None:
    """Drop the subscriptions_search materialized view and all dependencies.
    Although previous migrations that have changed the view's dependencies have only
    dropped it is only strictly required that we drop the materialized view prior to
    altering the underlying columns, the approach below potentially prevents confusing
    errors should the migration fail (i.e. if triggers fire mid-migration in a failure scenario)
    """
    # Drop triggers first
    for trigger_name, table_name, _ in TRIGGERS:
        conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};"))

    # Drop the refresh function
    conn.execute(text("DROP FUNCTION IF EXISTS refresh_subscriptions_search_view();"))

    # Drop the materialized view (CASCADE will drop indexes)
    conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS subscriptions_search CASCADE;"))


def recreate_materialized_view_and_dependencies(conn) -> None:
    """Recreate the subscriptions_search materialized view and all dependencies."""
    # Create the materialized view
    conn.execute(text(f"CREATE MATERIALIZED VIEW subscriptions_search AS {SUBSCRIPTIONS_SEARCH_QUERY}"))

    # Create indexes
    conn.execute(text("CREATE INDEX subscriptions_search_tsv_idx ON subscriptions_search USING GIN (tsv);"))
    conn.execute(
        text("CREATE UNIQUE INDEX subscriptions_search_subscription_id_idx ON subscriptions_search (subscription_id);")
    )

    # Create refresh function
    conn.execute(text(REFRESH_FUNCTION))

    # Create triggers
    for trigger_name, table_name, event in TRIGGERS:
        conn.execute(
            text(
                f"CREATE CONSTRAINT TRIGGER {trigger_name} {event} ON {table_name} "
                f"DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
            )
        )

    # Refresh the materialized view
    conn.execute(text("REFRESH MATERIALIZED VIEW subscriptions_search;"))


def upgrade() -> None:
    conn = op.get_bind()

    drop_materialized_view_and_dependencies(conn)

    op.execute(
        """
        UPDATE subscriptions
        SET note = NULL
        WHERE note IS NOT NULL AND TRIM(note) = ''
        """
    )

    op.execute(
        """
        UPDATE processes
        SET failed_reason = NULL
        WHERE failed_reason IS NOT NULL AND TRIM(failed_reason) = ''
        """
    )

    op.execute(
        """
        UPDATE processes
        SET traceback = NULL
        WHERE traceback IS NOT NULL AND TRIM(traceback) = ''
        """
    )

    op.execute(
        """
        UPDATE resource_types
        SET description = NULL
        WHERE description IS NOT NULL AND TRIM(description) = ''
        """
    )

    op.execute(
        """
        UPDATE subscription_instance_relations
        SET domain_model_attr = NULL
        WHERE domain_model_attr IS NOT NULL AND TRIM(domain_model_attr) = ''
        """
    )

    op.alter_column(
        "subscriptions",
        "note",
        existing_type=sa.Text(),
        type_=sa.String(NOTE_LENGTH),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "subscriptions",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "processes",
        "failed_reason",
        existing_type=sa.Text(),
        type_=sa.String(FAILED_REASON_LENGTH),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "processes",
        "traceback",
        existing_type=sa.Text(),
        type_=sa.String(TRACEBACK_LENGTH),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "products",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "product_blocks",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "resource_types",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "workflows",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_customer_descriptions",
        "description",
        existing_type=sa.Text(),
        type_=sa.String(DESCRIPTION_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_instance_values",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(RESOURCE_VALUE_LENGTH),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_instance_relations",
        "domain_model_attr",
        existing_type=sa.Text(),
        type_=sa.String(DOMAIN_MODEL_ATTR_LENGTH),
        existing_nullable=True,
        nullable=True,
    )

    recreate_materialized_view_and_dependencies(conn)


def downgrade() -> None:
    conn = op.get_bind()

    drop_materialized_view_and_dependencies(conn)

    op.alter_column(
        "subscriptions",
        "note",
        existing_type=sa.String(NOTE_LENGTH),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "subscriptions",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "processes",
        "failed_reason",
        existing_type=sa.String(FAILED_REASON_LENGTH),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "processes",
        "traceback",
        existing_type=sa.String(TRACEBACK_LENGTH),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "products",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "product_blocks",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "resource_types",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    op.alter_column(
        "workflows",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_customer_descriptions",
        "description",
        existing_type=sa.String(DESCRIPTION_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_instance_values",
        "value",
        existing_type=sa.String(RESOURCE_VALUE_LENGTH),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
    )

    op.alter_column(
        "subscription_instance_relations",
        "domain_model_attr",
        existing_type=sa.String(DOMAIN_MODEL_ATTR_LENGTH),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True,
    )

    recreate_materialized_view_and_dependencies(conn)
