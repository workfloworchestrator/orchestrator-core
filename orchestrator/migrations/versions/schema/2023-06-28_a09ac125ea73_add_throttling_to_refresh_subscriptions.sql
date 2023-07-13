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
        REFRESH MATERIALIZED VIEW subscriptions_search;

        comment_sql := 'COMMENT ON MATERIALIZED VIEW subscriptions_search IS ' || quote_literal(current_epoch);
        EXECUTE comment_sql;
    END IF;
    RETURN NULL;
END;
$$;
