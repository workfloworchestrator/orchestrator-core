"""Add Subscriptions search view.

Revision ID: e05bb1967eff
Revises: bed6bc0b197a
Create Date: 2023-03-06 10:09:55.675588

"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "e05bb1967eff"
down_revision = "bed6bc0b197a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    subscriptions_search_query = """
WITH rt_info AS (SELECT s.subscription_id,
                        concat_ws(', ',
                                  string_agg(rt.resource_type || ':' || siv.value, ', ' ORDER BY rt.resource_type),
                                  string_agg(distinct 'subscription_instance_id' || ':' || si.subscription_instance_id, ', ')
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
                                      ', ') AS sub_info,
                              array_to_string(
                                      ARRAY ['product_name:' || p.name,
                                          'product_description:' || p.description,
                                          'tag:' || p.tag,
                                          'product_type:', p.product_type],
                                      ', ') AS prod_info
                       FROM subscriptions s
                                JOIN products p ON s.product_id = p.product_id),
     fi_info AS (SELECT s.subscription_id,
                        string_agg(fi.name || ':' || fi.value, ', ' ORDER BY fi.name) AS fi_info
                 FROM subscriptions s
                          JOIN products p ON s.product_id = p.product_id
                          JOIN fixed_inputs fi ON p.product_id = fi.product_id
                 GROUP BY s.subscription_id),
     cust_info AS (SELECT s.subscription_id,
                          string_agg('customer_description: ' || scd.description, ', ') AS cust_info
                   FROM subscriptions s
                            JOIN subscription_customer_descriptions scd ON s.subscription_id = scd.subscription_id
                   GROUP BY s.subscription_id)
SELECT s.subscription_id,
       to_tsvector('simple',
                   concat_ws(', ',
                             spi.sub_info,
                             spi.prod_info,
                             fi.fi_info,
                             rti.rt_info,
                             ci.cust_info)
           ) as tsv
FROM subscriptions s
         LEFT JOIN sub_prod_info spi ON s.subscription_id = spi.subscription_id
         LEFT JOIN fi_info fi ON s.subscription_id = fi.subscription_id
         LEFT JOIN rt_info rti ON s.subscription_id = rti.subscription_id
         LEFT JOIN cust_info ci ON s.subscription_id = ci.subscription_id
         """
    subscriptions_search_view_ddl = (
        f"CREATE MATERIALIZED VIEW IF NOT EXISTS subscriptions_search AS {subscriptions_search_query}"
    )

    refresh_subscriptions_search_fn = """
      CREATE OR REPLACE FUNCTION refresh_subscriptions_search_view()
  RETURNS TRIGGER LANGUAGE plpgsql
  AS $$
  BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY subscriptions_search;
  RETURN NULL;
  END $$;
"""

    conn.execute(text(subscriptions_search_view_ddl))
    conn.execute(text(refresh_subscriptions_search_fn))
    conn.execute(text("CREATE INDEX subscriptions_search_tsv_idx ON subscriptions_search USING GIN (tsv);"))
    conn.execute(
        text("CREATE UNIQUE INDEX subscriptions_search_subscription_id_idx ON subscriptions_search (subscription_id);")
    )

    # Refresh the view when dependent tables change
    conn.execute(
        text(
            "CREATE CONSTRAINT TRIGGER fi_refresh_search AFTER UPDATE ON fixed_inputs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
        )
    )
    conn.execute(
        text(
            "CREATE CONSTRAINT TRIGGER products_refresh_search AFTER UPDATE ON products DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
        )
    )
    conn.execute(
        text(
            "CREATE CONSTRAINT TRIGGER sub_cust_desc_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscription_customer_descriptions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
        )
    )
    conn.execute(
        text(
            "CREATE CONSTRAINT TRIGGER siv_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscription_instance_values DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
        )
    )
    conn.execute(
        text(
            "CREATE CONSTRAINT TRIGGER sub_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscriptions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();"
        )
    )

    # DROP old text-search column and triggers (irreversible)
    old_triggers = [
        ("subscriptions_ins_trigger", "subscriptions"),
        ("subscriptions_upd_trigger", "subscriptions"),
        ("subscriptions_set_tsv_trigger", "subscriptions"),
        ("subscription_customer_descriptions_trigger", "subscription_customer_descriptions"),
        ("subscription_instance_values_trigger", "subscription_instance_values"),
        ("products_trigger", "products"),
        ("fixed_inputs_trigger", "fixed_inputs"),
    ]
    for trigger, table in old_triggers:
        conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger} ON {table};"))

    functions_to_drop = [
        *[trigger for trigger, _ in old_triggers],
        "tsq_parse(regconfig, text), tsq_parse(text), tsq_parse(text, text)",
        "tsq_process_tokens(regconfig, text[]), tsq_process_tokens(text[])",
        "tsq_tokenize",
        "tsq_tokenize_character",
        "tsq_append_current_token",
        "array_nremove",
        "generate_subscription_tsv",
        "parse_websearch(regconfig, text), parse_websearch(text)",
    ]
    for fn in functions_to_drop:
        conn.execute(text(f"DROP FUNCTION IF EXISTS {fn}"))

    conn.execute(text("DROP TYPE IF EXISTS tsq_state;"))
    conn.execute(text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS tsv;"))

    # Fill the materialized view
    conn.execute(text("REFRESH MATERIALIZED VIEW subscriptions_search;"))


def downgrade() -> None:
    conn = op.get_bind()
    triggers_to_drop = [
        ("fi_refresh_search", "fixed_inputs"),
        ("products_refresh_search", "products"),
        ("sub_cust_desc_refresh_search", "subscription_customer_descriptions"),
        ("siv_refresh_search", "subscription_instance_values"),
        ("sub_refresh_search", "subscriptions"),
    ]
    for trigger, table in triggers_to_drop:
        conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger} ON {table};"))

    conn.execute(text("DROP FUNCTION IF EXISTS refresh_subscriptions_search_view();"))
    conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS subscriptions_search CASCADE;"))
