-- Convert unlimited text fields to limited nullable strings and normalize empty subscription notes.
-- Revision ID: d69e10434a04

-- Field length limits chosen based on expected usage patterns
-- These values are intended to be reasonable, but give lots of wiggle room
-- If these values are updated, they also need to be updated in orchestrator-core/orchestrator/db/models.py
-- NOTE_LENGTH = 5000
-- DESCRIPTION_LENGTH = 2000
-- FAILED_REASON_LENGTH = 10000
-- TRACEBACK_LENGTH = 50000
-- RESOURCE_VALUE_LENGTH = 10000
-- DOMAIN_MODEL_ATTR_LENGTH = 255

-- Drop triggers first
DROP TRIGGER IF EXISTS fi_refresh_search ON fixed_inputs;
DROP TRIGGER IF EXISTS products_refresh_search ON products;
DROP TRIGGER IF EXISTS sub_cust_desc_refresh_search ON subscription_customer_descriptions;
DROP TRIGGER IF EXISTS siv_refresh_search ON subscription_instance_values;
DROP TRIGGER IF EXISTS sub_refresh_search ON subscriptions;

-- Drop the refresh function
DROP FUNCTION IF EXISTS refresh_subscriptions_search_view();

-- Drop the materialized view (CASCADE will drop indexes)
DROP MATERIALIZED VIEW IF EXISTS subscriptions_search CASCADE;

-- Normalize empty strings to NULL before altering column types
UPDATE subscriptions
SET note = NULL
WHERE note IS NOT NULL AND TRIM(note) = '';

-- Truncate existing values to fit within new length limits before altering column types
-- For most columns, preserve the first X characters; for traceback, preserve the last X characters
UPDATE subscriptions SET note = LEFT(note, 5000) WHERE LENGTH(note) > 5000;
UPDATE subscriptions SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE processes SET failed_reason = LEFT(failed_reason, 10000) WHERE LENGTH(failed_reason) > 10000;
UPDATE processes SET traceback = RIGHT(traceback, 50000) WHERE LENGTH(traceback) > 50000;
UPDATE products SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE product_blocks SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE resource_types SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE workflows SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE subscription_customer_descriptions SET description = LEFT(description, 2000) WHERE LENGTH(description) > 2000;
UPDATE subscription_instance_values SET value = LEFT(value, 10000) WHERE LENGTH(value) > 10000;
UPDATE subscription_instance_relations SET domain_model_attr = LEFT(domain_model_attr, 255) WHERE LENGTH(domain_model_attr) > 255;

-- Alter column types from TEXT to VARCHAR with limits
ALTER TABLE subscriptions ALTER COLUMN note TYPE VARCHAR(5000);
ALTER TABLE subscriptions ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE processes ALTER COLUMN failed_reason TYPE VARCHAR(10000);
ALTER TABLE processes ALTER COLUMN traceback TYPE VARCHAR(50000);
ALTER TABLE products ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE product_blocks ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE resource_types ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE workflows ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE subscription_customer_descriptions ALTER COLUMN description TYPE VARCHAR(2000);
ALTER TABLE subscription_instance_values ALTER COLUMN value TYPE VARCHAR(10000);
ALTER TABLE subscription_instance_relations ALTER COLUMN domain_model_attr TYPE VARCHAR(255);

-- Recreate the materialized view
CREATE MATERIALIZED VIEW subscriptions_search AS
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

-- Create indexes
CREATE INDEX subscriptions_search_tsv_idx ON subscriptions_search USING GIN (tsv);
CREATE UNIQUE INDEX subscriptions_search_subscription_id_idx ON subscriptions_search (subscription_id);

-- Create refresh function with epoch-based throttling
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

-- Create triggers
CREATE CONSTRAINT TRIGGER fi_refresh_search AFTER UPDATE ON fixed_inputs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();
CREATE CONSTRAINT TRIGGER products_refresh_search AFTER UPDATE ON products DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();
CREATE CONSTRAINT TRIGGER sub_cust_desc_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscription_customer_descriptions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();
CREATE CONSTRAINT TRIGGER siv_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscription_instance_values DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();
CREATE CONSTRAINT TRIGGER sub_refresh_search AFTER INSERT OR UPDATE OR DELETE ON subscriptions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION refresh_subscriptions_search_view();

-- Refresh the materialized view
REFRESH MATERIALIZED VIEW subscriptions_search;
