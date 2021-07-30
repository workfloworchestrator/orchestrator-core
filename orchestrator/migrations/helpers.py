from typing import Any, Dict, List
from uuid import UUID, uuid4

import sqlalchemy as sa


def get_resource_type_id_by_name(conn: sa.engine.Connection, name: str) -> Any:
    result = conn.execute(
        sa.text("SELECT resource_type_id FROM resource_types WHERE resource_types.resource_type=:name"), name=name
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_block_id_by_name(conn: sa.engine.Connection, name: str) -> Any:
    result = conn.execute(
        sa.text("SELECT product_block_id FROM product_blocks WHERE product_blocks.name=:name"), name=name
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_id_by_name(conn: sa.engine.Connection, name: str) -> Any:
    result = conn.execute(sa.text("SELECT product_id FROM products WHERE products.name=:name"), name=name)
    return [x for (x,) in result.fetchall()][0]


def get_product_name_by_id(conn: sa.engine.Connection, id: str) -> Any:
    result = conn.execute(sa.text("SELECT name FROM products WHERE product_id=:id"), id=id)
    return [x for (x,) in result.fetchall()][0]


def get_product_by_id(conn: sa.engine.Connection, id: str) -> Any:
    result = conn.execute(sa.text("SELECT * FROM products WHERE product_id=:id"), id=id)
    return result.fetchall()[0]


def get_fixed_inputs_by_product_id(conn: sa.engine.Connection, id: str) -> Any:
    result = conn.execute(sa.text("SELECT * FROM fixed_inputs WHERE product_id=:id"), id=id)
    return result.fetchall()


def insert_resource_type(conn: sa.engine.Connection, resource_type: str, description: str) -> Any:
    """Create a new resource types."""
    conn.execute(
        sa.text(
            """INSERT INTO resource_types (resource_type, description) VALUES
    (:resource_type, :description) ON CONFLICT DO NOTHING;"""
        ),
        resource_type=resource_type,
        description=description,
    )


def get_all_active_products_and_ids(conn: sa.engine.Connection) -> Any:
    """Return a list, with dicts containing keys `product_id` and `name` of active products."""
    result = conn.execute(sa.text("SELECT product_id, name  FROM products WHERE status='active'"))
    return [{"product_id": row[0], "name": row[1]} for row in result.fetchall()]


def create_missing_modify_note_workflows(conn: sa.engine.Connection) -> None:
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


def create_workflows(conn: sa.engine.Connection, new: dict) -> None:
    """
    Create a new workflow.

    Args:
        conn: DB connection as available in migration main file
        new: an dict of your workflow data

    Example:
        >>> new_workflows = {
                "workflow_name": {
                    "target": "CREATE",
                    "description": "Workflow description",
                    "tag": "ProductBlockName1",
                    "search_phrase": "Search Phrase%",
                }
            }
    """
    for name, workflow in new.items():
        workflow["name"] = name
        conn.execute(
            sa.text(
                """
                WITH new_workflow AS (
                INSERT INTO workflows(name, target, description)
                    VALUES (:name, :target, :description)
                    RETURNING workflow_id)
                INSERT
                INTO products_workflows (product_id, workflow_id)
                SELECT
                p.product_id,
                nw.workflow_id
                FROM products AS p
                    CROSS JOIN new_workflow AS nw
                        WHERE p.tag = :tag
                        AND p.name LIKE :search_phrase

            """
            ),
            workflow,
        )


def create_fixed_inputs(conn: sa.engine.Connection, product_id: str, new: dict) -> Dict[str, UUID]:
    """
    Create a fixed inputs for a product.

    Args:
        conn: DB connection as available in migration main file
        product_id: UUID of the product to link to
        new: an dict of your workflow data

    Example:
        >>> new = {
                "fixed_input_1": "value",
                "fixed_input_2": "value"
            }
    """
    uuids = {}
    for key, value in new.items():
        uuids[key] = uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO fixed_inputs (fixed_input_id, name, value, created_at, product_id)
                VALUES (:fixed_input_id, :key, :value, now(), :product_id)
                ON CONFLICT DO NOTHING;
            """
            ),
            {"fixed_input_id": uuids[key], "key": key, "value": value, "product_id": product_id},
        )
    return uuids


def create_products(conn: sa.engine.Connection, new: dict) -> Dict[str, UUID]:
    """
    Create a new workflow.

    Args:
        conn: DB connection as available in migration main file
        new: an dict of your workflow data

    Example:
        >>> new = {
                "Example Product": {
                    "product_id": "c9dc2374-514c-11eb-b685-acde48001122",
                    "product_type": "ProductType1",
                    "description": "Product description",
                    "tag": "ProductType",
                    "status": "active",
                    "fixed_inputs": {
                        "fixed_input_1": "value",
                        "fixed_input_2": "value2"
                    }
                },
                "Example Product 2": {
                    "product_type": "ProductType1",
                    "description": "Product description",
                    "tag": "ProductType",
                    "status": "active",
                    "product_block_ids": [
                        "37afe017-5a04-4d87-96b0-b8f88a328d7a"
                    ]
                }
            }
    """
    uuids = {}
    for name, product in new.items():
        product["name"] = name
        product["product_id"] = str(product.get("product_id", uuid4()))
        current_uuid = product["product_id"]
        uuids[name] = current_uuid
        conn.execute(
            sa.text(
                """
                INSERT INTO products (product_id, name, description, product_type, tag, status, created_at)
                VALUES (:product_id, :name, :description, :product_type, :tag, :status, now())
                ON CONFLICT DO NOTHING;
            """
            ),
            product,
        )
        if "product_block_ids" in product:
            for product_block_uuid in product["product_block_ids"]:
                # Link many-to-many if product blocks are given.
                conn.execute(
                    sa.text("INSERT INTO product_product_blocks VALUES (:product_id, :product_block_id)"),
                    {
                        "product_id": current_uuid,
                        "product_block_id": product_block_uuid,
                    },
                )
        if "fixed_inputs" in product:
            create_fixed_inputs(conn, current_uuid, product["fixed_inputs"])
    return uuids


def create_product_blocks(conn: sa.engine.Connection, new: dict) -> Dict[str, UUID]:
    """
    Create a new workflow.

    Args:
        conn: DB connection as available in migration main file
        new: an dict of your workflow data
        products: list of product block ids to link these product blocks to

    Example:
        >>> new = {
                "Example Product Block": {
                    "product_block_id": "37afe017-5a04-4d87-96b0-b8f88a328d7a",
                    "description": "Product description",
                    "tag": "ProductType",
                    "status": "active",
                },
                "Example Product Block Two": {
                    "product_type": "ProductBlock2",
                    "description": "Product description",
                    "tag": "ProductType",
                    "status": "active",
                }
            }
    """
    uuids = {}
    for name, product_block in new.items():
        product_block["name"] = name
        product_block["product_block_id"] = str(product_block.get("product_block_id", uuid4()))
        uuids[name] = product_block["product_block_id"]
        conn.execute(
            sa.text(
                """
                INSERT INTO product_blocks (product_block_id, name, description, tag, status, created_at)
                VALUES (:product_block_id, :name, :description, :tag, :status, now())
                ON CONFLICT DO NOTHING;
            """
            ),
            product_block,
        )

    return uuids


def create_resource_types_for_product_blocks(conn: sa.engine.Connection, new: dict) -> None:
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
        >>> create_resource_types(conn: sa.engine.Connection, new_stuff)
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


def delete_resource_types(conn: sa.engine.Connection, delete: List[str]) -> None:
    """Delete a resource type and it's occurrences in product blocks.

    Args:
        conn: DB connection as available in migration main file
        delete: list of resource_type names you want to delete

    Usage:
        >>>
            obsolete_stuff = ["name_1", "name_2"]
            delete_resource_types(conn: sa.engine.Connection, obsolete_stuff)
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


def create(conn: sa.engine.Connection, new: dict) -> None:
    """
    Call other functions in this file based on the schema.

    Args:
        conn: DB connection as available in migration main file
        new: a dict with everything you want to make and link

    Example:
        >>> new_stuff = {
                "products": {
                    "Example Product": {
                        "product_id": "c9dc2374-514c-11eb-b685-acde48001122",
                        "product_type": "ProductType1",
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "product_blocks": [
                            "Example Product Block"
                        ],
                        "fixed_inputs": {
                            "fixed_input_1": "value",
                            "fixed_input_2": "value2"
                        }
                    },
                    "Example Product 2": {
                        "product_type": "ProductType1",
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "product_block_ids": [
                            "37afe017-5a04-4d87-96b0-b8f88a328d7a"
                        ]
                    }
                },
                "product_blocks": {
                    "Example Product Block": {
                        "product_block_id": "37afe017-5a04-4d87-96b0-b8f88a328d7a",
                        "product_type": "ProductBlock1",
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "resources": {
                            "resource_type1": "Resource description",
                            "resource_type2": "Resource description"
                        }
                    },
                    "Generated UUID Product Block": {
                        "product_type": "ProductBlock2",
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "resources": {
                            "resource_type1": "Resource description",
                            "resource_type3": "Resource description"
                        }
                    }
                },
                "resources": {
                    "Existing Product": {
                        "resource_type4": "Resource description",
                        "resource_type5": "Resource description"
                    }
                },
                "workflows": {
                    "workflow_name": {
                        "target": "CREATE",
                        "description": "Workflow description",
                        "tag": "ProductType1",
                        "search_phrase": "Search Phrase%",
                    }
                }
            }
    """
    resources = new.get("resources", {})
    product_block_uuids = {}

    if "product_blocks" in new:
        for product_block_name, product_block in new["product_blocks"].items():
            # Move resources into one dict
            if "resources" in product_block:
                res_dict = {product_block_name: product_block["resources"]}
                resources.update(res_dict)
                del product_block["resources"]
        product_block_uuids = create_product_blocks(conn, new["product_blocks"])

    if "products" in new:
        for product in new.get("product_blocks", {}).values():
            if "product_blocks" in product:
                if "product_block_ids" not in product:
                    product["product_block_ids"] = []
                for product_block_name in product["product_blocks"]:
                    try:
                        product["product_block_ids"].append(product_block_uuids[product_block_name])
                    except KeyError:
                        try:
                            product["product_block_ids"].append(get_product_block_id_by_name(conn, product_block_name))
                        except Exception:
                            raise ValueError(f"{product_block_name} is not a valid product block.")
                del product["product_blocks"]
        create_products(conn, new["products"])

    if resources:
        create_resource_types_for_product_blocks(conn, resources)

    if "workflows" in new:
        create_workflows(conn, new["workflows"])
