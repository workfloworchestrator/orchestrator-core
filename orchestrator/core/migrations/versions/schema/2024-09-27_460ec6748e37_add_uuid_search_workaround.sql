-- Must drop the materialized view and recreate, as you cannot edit it directly/any of its dependencies
DROP MATERIALIZED VIEW IF EXISTS subscriptions_search;

-- Recreate the view
CREATE MATERIALIZED VIEW IF NOT EXISTS subscriptions_search AS
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
         LEFT JOIN subscription_metadata md ON s.subscription_id = md.subscription_id;

-- Recreate refresh fn if doesn't exist
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

-- Recreate indexes
CREATE INDEX subscriptions_search_tsv_idx ON subscriptions_search USING GIN (tsv);
CREATE UNIQUE INDEX subscriptions_search_subscription_id_idx ON subscriptions_search (subscription_id);

-- Refresh the view
REFRESH MATERIALIZED VIEW subscriptions_search;
