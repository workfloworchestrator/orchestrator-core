import sqlalchemy as sa


def get_resource_type_id_by_name(conn, name):
    result = conn.execute(
        sa.text("SELECT resource_type_id FROM resource_types WHERE resource_types.resource_type=:name"), name=name
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_block_id_by_name(conn, name):
    result = conn.execute(
        sa.text("SELECT product_block_id FROM product_blocks WHERE product_blocks.name=:name"), name=name
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_id_by_name(conn, name):
    result = conn.execute(sa.text("SELECT product_id FROM products WHERE products.name=:name"), name=name)
    return [x for (x,) in result.fetchall()][0]


def get_product_name_by_id(conn, id):
    result = conn.execute(sa.text("SELECT name FROM products WHERE product_id=:id"), id=id)
    return [x for (x,) in result.fetchall()][0]


def get_product_by_id(conn, id):
    result = conn.execute(sa.text("SELECT * FROM products WHERE product_id=:id"), id=id)
    return result.fetchall()[0]


def get_fixed_inputs_by_product_id(conn, id):
    result = conn.execute(sa.text("SELECT * FROM fixed_inputs WHERE product_id=:id"), id=id)
    return result.fetchall()


def insert_resource_type(conn, resource_type, description):
    """Create a new resource types."""
    conn.execute(
        sa.text(
            """INSERT INTO resource_types (resource_type, description) VALUES
    (:resource_type, :description) ON CONFLICT DO NOTHING;"""
        ),
        resource_type=resource_type,
        description=description,
    )


def get_all_active_products_and_ids(conn):
    """Return a list, with dicts containing keys `product_id` and `name` of active products."""
    result = conn.execute(sa.text("SELECT product_id, name  FROM products WHERE status='active'"))
    return [{"product_id": row[0], "name": row[1]} for row in result.fetchall()]


def create_missing_modify_note_workflows(conn):
    products = get_all_active_products_and_ids(conn)

    workflow_id = conn.execute(sa.text("SELECT workflow_id FROM workflows WHERE name = 'modify_note'"))
    workflow_id = workflow_id.fetchone()[0]

    for product in products:
        # check if product <-> workflow relation already exists
        workflows_products_id = conn.execute(
            sa.text(
                "SELECT workflow_id FROM products_workflows WHERE workflow_id=:workflow_id AND product_id=:product_id"
            ),
            workflow_id=workflow_id,
            product_id=product["product_id"],
        )
        if not workflows_products_id.fetchone():
            conn.execute(
                sa.text("INSERT INTO products_workflows VALUES (:product_id, :workflow_id) ON CONFLICT DO NOTHING"),
                workflow_id=workflow_id,
                product_id=product["product_id"],
            )


def create_resource_types_for_product_blocks(conn, new):
    """Create new resource types and link them to existing product_blocks by product_block name.

    Note: If the resource type already exists it will still add the resource type to the provided Product Blocks.

    Args:
        conn: DB connection as available in migration main file
        new: a dict with your product blocks and resource types

    Usage:

    Example:
        >>> new_stuff = {
            "ProductBlockName1": {
                "resource_type1": "Resource description"
            },
            "ProductBlockName2": {
                "resource_type1": "Resource description",
                "resource_type1": "Resource description"
            }
        }
        >>> create_resource_types(conn, new_stuff)
    """
    insert_resource_type = sa.text(
        """INSERT INTO resource_types (resource_type, description) VALUES (:resource_type, :description)
        ON CONFLICT DO NOTHING;"""
    )
    for resource_types in new.values():
        for resource_type, description in resource_types.items():
            conn.execute(insert_resource_type, resource_type=resource_type, description=description)

    for product_block, resource_types in new.items():
        conn.execute(
            sa.text(
                """
                WITH resource_type_ids AS (
                    SELECT resource_types.resource_type_id
                    FROM   resource_types
                    WHERE  resource_types.resource_type IN :new_resource_types
                ), service_attach_point AS (
                    SELECT product_blocks.product_block_id
                    FROM   product_blocks
                    WHERE  product_blocks.name = :product_block_name
                )

                INSERT INTO
                    product_block_resource_types (product_block_id, resource_type_id)
                SELECT
                    service_attach_point.product_block_id,
                    resource_type_ids.resource_type_id
                FROM
                    service_attach_point
                CROSS JOIN
                    resource_type_ids
                """
            ),
            product_block_name=product_block,
            new_resource_types=tuple(resource_types.keys()),
        )


def delete_resource_types(conn, delete):
    """Delete a resource type and it's occurrences in product blocks.

    Args:
        conn: DB connection as available in migration main file
        delete: list of resource_type names you want to delete

    Usage:
    ```python
    obsolete_stuff = ["name_1", "name_2"]
    delete_resource_types(conn, obsolete_stuff)
    ```
    """
    conn.execute(
        sa.text(
            """DELETE FROM product_block_resource_types
               USING resource_types
               WHERE resource_types.resource_type_id = product_block_resource_types.resource_type_id
                 AND resource_types.resource_type IN :obsolete"""
        ),
        obsolete=tuple(delete),
    )
    conn.execute(sa.text("DELETE FROM resource_types WHERE resource_type in :obsolete"), obsolete=tuple(delete))
