# Backfilling Existing Subscriptions
When updating a product block that already exists in your orchestrator, it could be the case that new attributes are
added or removed. When removing resource types from a `ProductBlock`, the `migrate-domain-models` command is able to
pick up on this change, and generates a migration that removes these resource types from your database completely.

However, when adding a new resource type to a `ProductBlock`, pre-existing product instances in the subscription
database are not backfilled. For this, another SQL transaction must be added to the generated migration file.

## Generating a Database Migration
After the new resource type is added to the product block, the generated migration file should already contain at least the following two transactions:

```python
conn.execute(sa.text("""
INSERT INTO resource_types (resource_type, description) VALUES ('site_contains_optical_equipment', 'Whether a site contains optical equipment') RETURNING resource_types.resource_type_id
"""))

conn.execute(sa.text("""
INSERT INTO product_block_resource_types (product_block_id, resource_type_id) VALUES ((SELECT product_blocks.product_block_id FROM product_blocks WHERE product_blocks.name IN ('SiteBlock')), (SELECT resource_types.resource_type_id FROM resource_types WHERE resource_types.resource_type IN ('site_contains_optical_equipment')))
"""))
```

Note that this will correctly add the new resource type to the database, but is missing a backfill for a default value.
In the case of this example, a new resource type `site_contains_optical_equipment` is added. Assume that all
subscriptions that already exist in the database already are sites that contain optical equipment. It would therefore
make sense to backfill the value `True` into all subscriptions that already exist.

## Adapting the Generated Database Migration
To implement this backfilling mechanism, only one SQL statement needs to be added to the migration, given below.

```python
conn.execute(sa.text("""
WITH rt_id AS (SELECT resource_type_id FROM resource_types WHERE resource_type = 'site_contains_optical_equipment') INSERT INTO subscription_instance_values (subscription_instance_id, resource_type_id, value) SELECT subscription_instance_id, rt_id.resource_type_id, 'True' FROM rt_id, subscription_instances WHERE product_block_id = (SELECT product_block_id FROM product_blocks WHERE name = 'SiteBlock');
"""))
```

Adding this statement at the end of the `upgrade()` method in the generated migration file, will set the value of
`site_contains_optical_equipment` in all existing Site subscriptions to `True`. A more formatted version of this SQL
statement is given here. To adapt this example to your needs, update the resource type name, default value, and name of
the product block where this resource type is added.

```sql
WITH rt_id AS (
    SELECT
        resource_type_id
    FROM
        resource_types
    WHERE
        -- The name of your new resource type
        resource_type = 'site_contains_optical_equipment'
)
INSERT INTO
    subscription_instance_values (
        subscription_instance_id,
        resource_type_id,
        value
    )
SELECT
    subscription_instance_id,
    rt_id.resource_type_id,
    'True'  -- The new value that is backfilled
FROM
    rt_id,
    subscription_instances
WHERE
    product_block_id = (
        SELECT
            product_block_id
        FROM
            product_blocks
        WHERE
            -- The name of the product block where this value is backfilled
            name = 'SiteBlock'
    );
```

The `downgrade()` method of the generated migration does not need any modification to work. It simply removes the
resource type from the subscription database altogether.
