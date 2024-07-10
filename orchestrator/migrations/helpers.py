# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Iterable, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa
import structlog

from orchestrator.settings import app_settings
from orchestrator.types import UUIDstr

logger = structlog.get_logger(__name__)


def get_resource_type_id_by_name(conn: sa.engine.Connection, name: str) -> UUID:
    result = conn.execute(
        sa.text("SELECT resource_type_id FROM resource_types WHERE resource_types.resource_type=:name"), {"name": name}
    )
    return [x for (x,) in result.fetchall()][0]


def get_fixed_input_id_by_name(conn: sa.engine.Connection, name: str) -> UUID:
    result = conn.execute(
        sa.text("SELECT fixed_input_id FROM fixed_inputs WHERE fixed_inputs.name=:name"), {"name": name}
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_block_id_by_name(conn: sa.engine.Connection, name: str) -> UUID:
    result = conn.execute(
        sa.text("SELECT product_block_id FROM product_blocks WHERE product_blocks.name=:name"), {"name": name}
    )
    return [x for (x,) in result.fetchall()][0]


def get_product_id_by_name(conn: sa.engine.Connection, name: str) -> UUID:
    result = conn.execute(sa.text("SELECT product_id FROM products WHERE products.name=:name"), {"name": name})
    return [x for (x,) in result.fetchall()][0]


def get_product_name_by_id(conn: sa.engine.Connection, id: UUID | UUIDstr) -> str:
    result = conn.execute(sa.text("SELECT name FROM products WHERE product_id=:id"), {"id": id})
    return [x for (x,) in result.fetchall()][0]


def get_product_by_id(conn: sa.engine.Connection, id: UUID | UUIDstr) -> dict:
    result = conn.execute(sa.text("SELECT * FROM products WHERE product_id=:id"), {"id": id})

    return dict(result.mappings().one())
    # return result.fetchall()[0]


def get_product_ids_by_product_type(conn: sa.engine.Connection, product_type: str) -> list[UUID]:
    result = conn.execute(
        sa.text("SELECT product_id FROM products WHERE product_type=:product_type"),
        {"product_type": product_type},
    )
    return [x for (x,) in result.fetchall()]


def get_fixed_inputs_by_product_id(conn: sa.engine.Connection, id: UUID | UUIDstr) -> Sequence:
    result = conn.execute(sa.text("SELECT * FROM fixed_inputs WHERE product_id=:id"), {"id": id})
    return result.fetchall()


def insert_resource_type(conn: sa.engine.Connection, resource_type: str, description: str) -> None:
    """Create a new resource types."""
    conn.execute(
        sa.text(
            """INSERT INTO resource_types (resource_type, description) VALUES
    (:resource_type, :description) ON CONFLICT DO NOTHING;"""
        ),
        {
            "resource_type": resource_type,
            "description": description,
        },
    )


def get_all_active_products_and_ids(conn: sa.engine.Connection) -> list[dict[str, UUID | UUIDstr | str]]:
    """Return a list, with dicts containing keys `product_id` and `name` of active products."""
    result = conn.execute(sa.text("SELECT product_id, name  FROM products WHERE status='active'"))
    return [{"product_id": row[0], "name": row[1]} for row in result.fetchall()]


def ensure_default_workflows(conn: sa.engine.Connection) -> None:
    """Ensure products_workflows table contains a link between all 'active' workflows and the set of workflows identified in the DEFAULT_PRODUCT_WORKFLOWS app_setting.

    Note that the 0th element of the uuids are taken when generating product_workflow_table_rows because sqlalchemy returns a row tuple even if selecting for a single column.
    """
    products = sa.Table("products", sa.MetaData(), autoload_with=conn)
    workflows = sa.Table("workflows", sa.MetaData(), autoload_with=conn)
    product_workflows_table = sa.Table("products_workflows", sa.MetaData(), autoload_with=conn)

    all_product_uuids = conn.execute(sa.select(products.c.product_id)).fetchall()
    default_workflow_ids = conn.execute(
        sa.select(workflows.c.workflow_id).where(workflows.c.name.in_(app_settings.DEFAULT_PRODUCT_WORKFLOWS))
    ).fetchall()
    product_workflow_table_rows = [
        (product_uuid[0], workflow_uuid[0])
        for product_uuid in all_product_uuids
        for workflow_uuid in default_workflow_ids
    ]
    conn.execute(
        sa.dialects.postgresql.insert(product_workflows_table)
        .values(product_workflow_table_rows)
        .on_conflict_do_nothing(index_elements=("product_id", "workflow_id"))
    )


def create_workflow(conn: sa.engine.Connection, workflow: dict) -> None:
    """Create a new workflow for a product.

    Args:
        conn: DB connection as available in migration main file.
        workflow: Dict with data for a new workflow.
            name: Name of the workflow.
            target: Target of the workflow ("CREATE", "MODIFY", "TERMINATE", "SYSTEM")
            description: Description of the workflow.
            product_type: Product type to add the workflow to.

    Usage:
        >>> workflow = {
            "name": "workflow_name",
            "target": "SYSTEM",
            "description": "workflow description",
            "product_type": "product_type",
        }
        >>> create_workflow(conn, workflow)
    """

    conn.execute(
        sa.text(
            """
                WITH new_workflow AS (
                INSERT INTO workflows(name, target, description)
                    VALUES (:name, :target, :description)
                    ON CONFLICT DO NOTHING
                    RETURNING workflow_id)
                INSERT
                INTO products_workflows (product_id, workflow_id)
                SELECT
                p.product_id,
                nw.workflow_id
                FROM products AS p
                    CROSS JOIN new_workflow AS nw
                                WHERE p.product_type = :product_type
                ON CONFLICT DO NOTHING
            """
        ),
        workflow,
    )


def create_workflows(conn: sa.engine.Connection, new: dict) -> None:
    """Create new workflows.

    Args:
        conn: DB connection as available in migration main file
        new: an dict of your workflow data

    Example:
        >>> new_workflows = {
                "workflow_name": {
                    "workflow_id": "f2702074-3203-454c-b298-6dfa7675423d",
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
                    INSERT INTO workflows(workflow_id, name, target, description)
                    VALUES (:workflow_id, :name, :target, :description)
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


def create_fixed_inputs(conn: sa.engine.Connection, product_id: UUID | UUIDstr, new: dict) -> dict[str, str]:
    """Create fixed inputs for a given product.

    Args:
        conn: DB connection as available in migration main file
        product_id: UUID of the product to link to
        new: an dict of your workflow data

    Example:
        >>> product_id = "id"
        >>> new = {
                "fixed_input_1": ("value", "f6a4f529-ad17-4ad8-b8ba-45684e2354ba"),
                "fixed_input_2": ("value", "5a67321d-45d5-4921-aa93-b8708b5d74c6")
            }
        >>> create_resource_types(conn, product_id, new)

    without extra ID's you don't need the tuple:

        >>> product_id = "id"
        >>> new = {
            "fixed_input_1": "value",
            "fixed_input_2": "value",
        }
        >>> create_fixed_inputs(conn, product_id, new)

    """
    insert_fixed_input_with_id = sa.text(
        """INSERT INTO fixed_inputs (fixed_input_id, name, value, created_at, product_id)
        VALUES (:fixed_input_id, :key, :value, now(), :product_id)
        ON CONFLICT DO NOTHING;"""
    )
    insert_fixed_input_without_id = sa.text(
        """INSERT INTO fixed_inputs (name, value, created_at, product_id)
        VALUES (:key, :value, now(), :product_id)
        ON CONFLICT DO NOTHING;"""
    )

    uuids = {}
    for key, values in new.items():
        if isinstance(values, tuple):
            value, fixed_input_id = values
            uuids[key] = fixed_input_id
            conn.execute(
                insert_fixed_input_with_id,
                {"fixed_input_id": fixed_input_id, "key": key, "value": value, "product_id": product_id},
            )
        else:
            conn.execute(insert_fixed_input_without_id, {"key": key, "value": values, "product_id": product_id})
            uuids[key] = get_fixed_input_id_by_name(conn, key)

    return uuids


def create_products(conn: sa.engine.Connection, new: dict) -> dict[str, UUIDstr]:
    """Create new products with their fixed inputs.

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
        for product_block_uuid in product.get("product_block_ids", []):
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


def create_product_blocks(conn: sa.engine.Connection, new: dict) -> dict[str, UUIDstr]:
    """Create new product blocks.

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
                    "product_block_id": "e8312243-f5cc-4560-adf0-63be4cefeccd",
                    "description": "Product description",
                    "tag": "ProductType",
                    "status": "active",
                }
            }
    """
    uuids = {}
    for name, product_block in new.items():
        product_block["name"] = name
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
        if "resource_types" in product_block:
            block_resource_types = {name: product_block["resource_types"]}
            create_resource_types_for_product_blocks(conn, block_resource_types)

        if "in_use_by_block_relations" in product_block:
            for in_use_by_block_name in product_block["in_use_by_block_relations"]:
                in_use_by_block_id = get_product_block_id_by_name(conn, in_use_by_block_name)
                add_product_block_relation_between_products_by_id(
                    conn, str(in_use_by_block_id), str(product_block["product_block_id"])
                )

        if "depends_on_block_relations" in product_block:
            for depends_on_block_name in product_block["depends_on_block_relations"]:
                depends_on_block_id = get_product_block_id_by_name(conn, depends_on_block_name)
                add_product_block_relation_between_products_by_id(
                    conn, str(product_block["product_block_id"]), str(depends_on_block_id)
                )

    return uuids


def create_resource_types_for_product_blocks(conn: sa.engine.Connection, new: dict) -> list[UUID]:
    """Create new resource types and link them to existing product_blocks by product_block name.

    Note: If the resource type already exists it will still add the resource type to the provided Product Blocks.

    Args:
        conn: DB connection as available in migration main file
        new: a dict with your product blocks and resource types
    Returns:
        List of resource type ids in order of insertion

    Usage examples:
        >>> new_stuff = {
            "ProductBlockName1": {
                "resource_type1": ("Resource description", "a47a3f96-c32f-4e4d-8e8c-11596451e878")
            },
            "ProductBlockName2": {
                "resource_type1": ("Resource description", "a47a3f96-c32f-4e4d-8e8c-11596451e878"),
                "resource_type2": ("Resource description", "dffe1890-e0f8-4ed5-8d0b-e769c3f726cc")
            }
        }
        >>> create_resource_types(conn, new_stuff)

    without extra ID's you don't need the tuple:

        >>> new_stuff = {
            "ProductBlockName1": {
                "resource_type1": "Resource description"
            },
            "ProductBlockName2": {
                "resource_type1": "Resource description",
                "resource_type1": "Resource description"
            }
        }

        >>> create_resource_types_for_product_blocks(conn, new_stuff)

    """
    insert_resource_type_with_id = sa.text(
        """INSERT INTO resource_types (resource_type_id, resource_type, description)
        VALUES (:resource_type_id, :resource_type, :description)
        ON CONFLICT DO NOTHING;"""
    )
    insert_resource_type_without_id = sa.text(
        """INSERT INTO resource_types (resource_type, description)
        VALUES (:resource_type, :description)
        ON CONFLICT DO NOTHING;"""
    )

    resource_type_ids = []
    for resource_types in new.values():
        for resource_type, values in resource_types.items():
            if isinstance(values, tuple):
                description, resource_type_id = values
                conn.execute(
                    insert_resource_type_with_id,
                    {
                        "resource_type_id": resource_type_id,
                        "resource_type": resource_type,
                        "description": description,
                    },
                )
            else:
                conn.execute(insert_resource_type_without_id, {"resource_type": resource_type, "description": values})
            resource_type_ids.append(get_resource_type_id_by_name(conn, resource_type))

    for product_block, resource_types in new.items():
        conn.execute(
            sa.text(
                """
                WITH resource_type_ids AS (
                    SELECT resource_types.resource_type_id
                    FROM   resource_types
                    WHERE  resource_types.resource_type = ANY(:new_resource_types)
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
            {
                "product_block_name": product_block,
                "new_resource_types": list(resource_types.keys()),
            },
        )
    return resource_type_ids


def create(conn: sa.engine.Connection, new: dict) -> None:  # noqa: C901
    """Call other functions in this file based on the schema.

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
                            "fixed_input_1": ("value", "f6a4f529-ad17-4ad8-b8ba-45684e2354ba"),
                            "fixed_input_2": ("value", "5a67321d-45d5-4921-aa93-b8708b5d74c6")
                        }
                    },
                    "Example Product 2": {
                        "product_id": "c9dc2374-514c-11eb-b685-acde48001122",
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
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "resources": {
                            "resource_type1": ("Resource description", "a47a3f96-c32f-4e4d-8e8c-11596451e878"),
                            "resource_type2": ("Resource description", "dffe1890-e0f8-4ed5-8d0b-e769c3f726cc")
                        }
                    },
                    "Generated UUID Product Block": {
                        "product_block_id": "37afe017-5a04-4d87-96b0-b8f88a328d7a",
                        "description": "Product description",
                        "tag": "ProductType",
                        "status": "active",
                        "resources": {
                            "resource_type1": ("Resource description", "a47a3f96-c32f-4e4d-8e8c-11596451e878"),
                            "resource_type2": ("Resource description", "dffe1890-e0f8-4ed5-8d0b-e769c3f726cc")
                        }
                    }
                },
                "resources": {
                    "Existing Product": {
                        "resource_type1": ("Resource description", "a47a3f96-c32f-4e4d-8e8c-11596451e878"),
                        "resource_type2": ("Resource description", "dffe1890-e0f8-4ed5-8d0b-e769c3f726cc")
                    }
                },
                "workflows": {
                    "workflow_name": {
                        "workflow_id": "f2702074-3203-454c-b298-6dfa7675423d",
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

    # Create defined product blocks
    if "product_blocks" in new:
        for product_block_name, product_block in new.get("product_blocks", {}).items():
            # Move resources into one dict
            if "resources" in product_block:
                res_dict = {product_block_name: product_block["resources"]}
                resources.update(res_dict)
                del product_block["resources"]
        product_block_uuids = create_product_blocks(conn, new["product_blocks"])

    def get_product_block_id(product_block_name: str) -> str:
        if product_block_id := product_block_uuids.get(product_block_name):
            return product_block_id

        try:
            return str(get_product_block_id_by_name(conn, product_block_name))
        except Exception:
            raise ValueError(f"{product_block_name} is not a valid product block.")

    # Create defined products
    if "products" in new:
        for _, product in new["products"].items():
            # The best practice is for a product to have only 1 root product block.
            # Migrations created through the generator adhere to this practice.
            product_block_ids = product.get("product_block_ids", [])
            if root_product_block := product.get("root_product_block"):
                root_product_block_id = get_product_block_id(root_product_block)
                if product_block_ids and product_block_ids != [root_product_block_id]:
                    logger.warning("Overriding hardcoded product_block_ids with root product block id")
                product["product_block_ids"] = [root_product_block_id]
                continue

            # To avoid forcing users to re-write old migrations or their products, this function will still
            # allow inserting multiple root product blocks.
            if "product_blocks" in product:
                product.setdefault("product_block_ids", [])
                for product_block_name in product["product_blocks"]:
                    product["product_block_ids"].append(get_product_block_id(product_block_name))
                del product["product_blocks"]
        create_products(conn, new["products"])

    # Create defined resource types
    if resources:
        create_resource_types_for_product_blocks(conn, resources)

    # Create defined workflows
    if "workflows" in new:
        create_workflows(conn, new["workflows"])

    # Ensure default workflows exist for all products
    ensure_default_workflows(conn)


def add_products_to_workflow_by_product_tag(
    conn: sa.engine.Connection, workflow_name: str, product_tag: str, product_name_like: str = "%%"
) -> None:
    """Add products to a workflow by product tag.

    Args:
        conn: DB connection as available in migration main file.
        workflow_name: Name of the workflow to add the products to.
        product_tag: Tag of the product to add to the workflow.
        product_name_like (optional): Part of the product name to get more specific products (necessary for fw v2)

    Usage:
    ```python
    product_tag = "product_tag"
    workflow_name = "workflow_name"
    add_products_to_workflow_by_product_tag(conn, product_tag, workflow_name)
    ```
    """

    conn.execute(
        sa.text(
            """
                WITH workflow AS (
                    SELECT workflow_id FROM workflows WHERE name=:workflow_name
                )
                INSERT INTO products_workflows (product_id, workflow_id)
                SELECT
                    p.product_id,
                    nw.workflow_id
                FROM products AS p
                    CROSS JOIN workflow AS nw
                    WHERE p.tag=:product_tag AND name LIKE :product_name_like
            """
        ),
        {
            "workflow_name": workflow_name,
            "product_tag": product_tag,
            "product_name_like": product_name_like,
        },
    )


def remove_products_from_workflow_by_product_tag(
    conn: sa.engine.Connection, workflow_name: str, product_tag: str, product_name_like: str = "%%"
) -> None:
    """Delete products from a workflow by product tag.

    Args:
        conn: DB connection as available in migration main file.
        workflow_name: Name of the workflow that the products need to be removed from.
        product_tag: Tag of the product to remove from the workflow.
        product_name_like (optional): Part of the product name to get more specific products (necessary for fw v2)

    Usage:
    ```python
    product_tag = "product_tag"
    workflow_name = "workflow_name"
    remove_products_from_workflow_by_product_tag(conn, product_tag, workflow_name)
    ```
    """

    conn.execute(
        sa.text(
            """
                DELETE FROM products_workflows
                WHERE workflow_id = (
                    SELECT workflow_id FROM workflows where name=:workflow_name
                ) AND product_id IN (
                    SELECT product_id FROM products
                    WHERE tag=:product_tag AND name LIKE :product_name_like
                )
            """
        ),
        {
            "workflow_name": workflow_name,
            "product_tag": product_tag,
            "product_name_like": product_name_like,
        },
    )


def add_product_block_relation_between_products_by_id(
    conn: sa.engine.Connection, in_use_by_id: UUID | UUIDstr, depends_on_id: UUID | UUIDstr
) -> None:
    """Add product block relation by product block id.

    Args:
        conn: DB connection as available in migration main file.
        in_use_by_id: ID of the product block that uses another product block.
        depends_on_id: ID of the product block that is used as dependency.

    Usage:
    ```python
    in_use_by_id = "in_use_by_id"
    depends_on_id = "depends_on_id"
    add_product_block_relation_between_products_by_id(conn, in_use_by_id, depends_on_id)
    ```
    """

    conn.execute(
        sa.text(
            """
                INSERT INTO product_block_relations (in_use_by_id, depends_on_id)
                VALUES (:in_use_by_id, :depends_on_id)
            """
        ),
        {
            "in_use_by_id": in_use_by_id,
            "depends_on_id": depends_on_id,
        },
    )


def remove_product_block_relation_between_products_by_id(
    conn: sa.engine.Connection, in_use_by_id: UUID | UUIDstr, depends_on_id: UUID | UUIDstr
) -> None:
    """Remove product block relation by id.

    Args:
        conn: DB connection as available in migration main file.
        in_use_by_id: ID of the product block that uses another product block.
        depends_on_id: ID of the product block that is used as dependency.

    Usage:
        >>> in_use_by_id = "in_use_by_id"
        >>> depends_on_id = "depends_on_id"
        >>> remove_product_block_relation_between_products_by_id(
            conn, in_use_by_id, depends_on_id
        )
    """

    conn.execute(
        sa.text(
            """
                DELETE FROM product_block_relations
                WHERE in_use_by_id=:in_use_by_id AND depends_on_id=:depends_on_id
            """
        ),
        {
            "in_use_by_id": in_use_by_id,
            "depends_on_id": depends_on_id,
        },
    )


def delete_resource_type_by_id(conn: sa.engine.Connection, id: UUID | UUIDstr) -> None:
    """Delete resource type by resource type id.

    Args:
        conn: DB connection as available in migration main file.
        id: ID of the resource type to delete.

    Usage:
    ```python
    resource_type_id = "id"
    delete_resource_type_by_id(conn, resource_type_id)
    ```
    """
    conn.execute(sa.text("DELETE FROM resource_types WHERE resource_type_id=:id"), {"id": id})


def delete_resource_types_from_product_blocks(conn: sa.engine.Connection, delete: dict) -> None:
    """Delete resource type from product blocks.

    Note: the resource_type itself will not be deleted.

    Args:
        conn: DB connection as available in migration main file
        delete: dict of product_blocks and resource_types names that you want to unlink

    Example:
        >>> obsolete_stuff = {
            "ProductBlockName1": {
                "resource_type1": "Resource description"
            },
            "ProductBlockName2": {
                "resource_type1": "Resource description",
                "resource_type1": "Resource description"
            }
        }
        >>> delete_resource_types_from_product_blocks(conn, obsolete_stuff)
    """
    for product_block_name, resource_types in delete.items():
        conn.execute(
            sa.text(
                """DELETE FROM product_block_resource_types
                   USING resource_types
                   WHERE product_block_id = (SELECT product_block_id FROM product_blocks WHERE name=:product_block_name) AND
                     resource_types.resource_type_id = product_block_resource_types.resource_type_id AND
                     resource_types.resource_type = ANY(:obsolete_resource_types)"""
            ),
            {
                "product_block_name": product_block_name,
                "obsolete_resource_types": list(resource_types.keys()),
            },
        )


def delete_resource_types(conn: sa.engine.Connection, delete: Iterable) -> None:
    """Delete a resource type and it's occurrences in product blocks.

    Args:
        conn: DB connection as available in migration main file
        delete: list of resource_type names you want to delete

    Example:
        >>> obsolete_stuff = ["name_1", "name_2"]
        >>> delete_resource_types(conn, obsolete_stuff)
    """
    conn.execute(
        sa.text(
            """DELETE FROM product_block_resource_types
               USING resource_types
               WHERE resource_types.resource_type_id = product_block_resource_types.resource_type_id
                 AND resource_types.resource_type = ANY(:obsolete)"""
        ),
        {"obsolete": tuple(delete)},
    )
    conn.execute(sa.text("DELETE FROM resource_types WHERE resource_type in :obsolete;"), {"obsolete": list(delete)})


def delete_products_by_tag(conn: sa.engine.Connection, name: str) -> None:
    conn.execute(sa.text("""DELETE FROM products p WHERE p.name=:name"""), {"name": name})


def delete_product(conn: sa.engine.Connection, name: str) -> None:
    """Delete a product and it's occurrences in workflows and product_blocks.

    Args:
        conn: DB connection as available in migration main file
        name: a product name you want to delete

    Example:
        >>> obsolete_stuff = "name_1"
        >>> delete_product(conn, obsolete_stuff)
    """
    conn.execute(
        sa.text(
            """
            WITH deleted_p AS (
                DELETE FROM products WHERE name=:name
                RETURNING  product_id
            ),
            deleted_p_pb AS (
                DELETE FROM product_product_blocks WHERE product_id IN (SELECT product_id FROM deleted_p)
            ),
            deleted_pb_rt AS (
                DELETE FROM products_workflows WHERE product_id IN (SELECT product_id FROM deleted_p)
            )
            SELECT * from deleted_p;
            """
        ),
        {"name": name},
    )


def delete_product_block(conn: sa.engine.Connection, name: str) -> None:
    """Delete a product block and it's occurrences in resource types and products.

    Args:
        conn: DB connection as available in migration main file
        name: a product_block name you want to delete

    Example:
        >>> obsolete_stuff = "name_1"
        >>> delete_product_block(conn, obsolete_stuff)
    """
    conn.execute(
        sa.text(
            """
            WITH deleted_pb AS (
                DELETE FROM product_blocks WHERE name=:name
                RETURNING  product_block_id
            ),
            deleted_p_pb AS (
                DELETE FROM product_product_blocks WHERE product_block_id IN (SELECT product_block_id FROM deleted_pb)
            ),
            deleted_pb_rt AS (
                DELETE FROM product_block_resource_types WHERE product_block_id IN (SELECT product_block_id FROM deleted_pb)
            )
            SELECT * from deleted_pb;
            """
        ),
        {"name": name},
    )


def delete_workflow(conn: sa.engine.Connection, name: str) -> None:
    """Delete a workflow and it's occurrences in products.

    Note: the cascading delete rules in postgres will also ensure removal from `products_workflows`.

    Args:
        conn: DB connection as available in migration main file
        name: a workflow name you want to delete

    Example:
        >>> obsolete_stuff = "name_1"
        >>> delete_workflow(conn, obsolete_stuff)
    """

    conn.execute(
        sa.text(
            """
                DELETE
                FROM workflows
                WHERE name = :name;
            """
        ),
        {"name": name},
    )


def delete_resource_type(conn: sa.engine.Connection, resource_type: str) -> None:
    """Delete a resource type and it's occurrences in product blocks and products.

    Args:
        conn: DB connection as available in migration main file
        resource_type: a resource_type name you want to delete

    Example:
        >>> resource_type = "name_1"
        >>> delete_product_block(conn, resource_type)
    """
    conn.execute(
        sa.text(
            """
            WITH deleted_pb AS (
                DELETE FROM resource_types WHERE resource_type=:resource_type
                RETURNING  resource_type_id
            ),
            deleted_pb_rt AS (
                DELETE FROM product_block_resource_types WHERE resource_type_id IN (SELECT resource_type_id FROM deleted_pb)
            )
            SELECT * from deleted_pb;
            """
        ),
        {"resource_type": resource_type},
    )


def delete(conn: sa.engine.Connection, obsolete: dict) -> None:
    """Delete multiple products, product_blocks, resources, and workflows.

    Args:
        conn: DB connection as available in migration main file
        obsolete: a dict with everything you want to delete

    Example:
        >>> obsolete = [
                "products": [
                    "Example Product",
                    "Example Product 2"
                ],
                "product_blocks": [
                    "Example Product Block",
                    "Example Product Block 2"
                ],
                "resources": [
                        "resource_type4,
                        "resource_type5"
                ],
                "workflows": [
                    "workflow_name_a",
                    "workflow_name_b",
                ]
            ]
    """
    if "resource_types" in obsolete:
        for res_type in obsolete["resource_types"]:
            delete_resource_type(conn, res_type)

    if "product_blocks" in obsolete:
        for product_block_name in obsolete["product_blocks"]:
            delete_product_block(conn, product_block_name)

    if "products" in obsolete:
        for product in obsolete["products"]:
            delete_product(conn, product)

    if "workflows" in obsolete:
        for workflow in obsolete["workflows"]:
            delete_workflow(conn, workflow)


#
# Helpers for migrating to the new domain model relations as introduced in 0.3.3
#


def convert_resource_type_relations_to_instance_relations(
    conn: sa.engine.Connection, resource_type_id: UUID | UUIDstr, domain_model_attr: str, cleanup: bool = True
) -> None:
    """Move resouce type relations to instance type relations using resource type id.

    Note: It removes the resource type relations after moving! (comment out the second execute to try without the removal)

    Args:
        conn: DB connection as available in migration main file.
        resource_type_id: ID of the resource type that you want to move to instance relations.
        domain_model_attr: Name of the domain model attribute that connects the product blocks together.
        cleanup: remove old resource type relations after the migrate?

    Usage:
        >>> resource_type_id = "id"
        >>> domain_model_attr = "domain_model_attr"
        >>> convert_resource_type_relation_to_instance_relations(
            conn, resource_type_id, domain_model_attr
        )
    """
    conn.execute(
        sa.text(
            """
            INSERT INTO subscription_instance_relations (in_use_by_id, depends_on_id, order_id, domain_model_attr)
            WITH dependencies AS (
                SELECT siv.value AS subscription_id, siv.subscription_instance_id AS in_use_by_instance_id, si.product_block_id
                FROM subscription_instance_values AS siv
                LEFT JOIN subscription_instances AS si on siv.subscription_instance_id = si.subscription_instance_id
                WHERE siv.resource_type_id=:resource_type_id
            )
            SELECT
                in_use_by_instance_id AS in_use_by_id,
                sii.subscription_instance_id AS depends_on_id,
                (row_number() OVER (PARTITION BY in_use_by_instance_id) - 1) AS order_id,
                :domain_model_attr AS domain_model_attr
            FROM subscription_instances AS sii
            INNER JOIN dependencies AS dep ON sii.subscription_id=uuid(dep.subscription_id) ON CONFLICT DO NOTHING
            """
        ),
        {
            "resource_type_id": resource_type_id,
            "domain_model_attr": domain_model_attr,
        },
    )

    if cleanup:
        conn.execute(
            sa.text(
                """
                DELETE FROM subscription_instance_values
                WHERE resource_type_id=:resource_type_id
                """
            ),
            {"resource_type_id": resource_type_id},
        )


def convert_instance_relations_to_resource_type_relations_by_domain_model_attr(
    conn: sa.engine.Connection, domain_model_attr: str, resource_type_id: UUID | UUIDstr, cleanup: bool = True
) -> None:
    """Move instance type relations to resouce type relations by domain model attribute.

    Note: It removes the instance relations after moving! Use the `cleanup` argument if you don't want this

    Args:
        conn: DB connection as available in migration main file.
        domain_model_attr: Name of the domain model attribute that connects the product blocks together.
        resource_type_id: ID of the resource type that you want to move the instance relations to.
        cleanup: remove old instance relations after the migrate?

    Usage:
        >>> domain_model_attr = "domain_model_attr"
        >>> resource_type_id = "id"
        >>> convert_instance_relations_to_resource_type_relations_by_domain_model_attr(
            conn, domain_model_attr, resource_type_id
        )
    """
    conn.execute(
        sa.text(
            """
                INSERT INTO subscription_instance_values (subscription_instance_id, resource_type_id, value)
                WITH instance_relations AS (
                    SELECT in_use_by_id, depends_on_id FROM subscription_instance_relations
                    WHERE domain_model_attr=:domain_model_attr
                )
                SELECT ir.in_use_by_id AS subscription_instance_id, :resource_type_id AS resource_type_id, si.subscription_id AS value
                from subscription_instances as si
                inner join instance_relations as ir on si.subscription_instance_id=ir.depends_on_id
            """
        ),
        {
            "domain_model_attr": domain_model_attr,
            "resource_type_id": resource_type_id,
        },
    )

    if cleanup:
        conn.execute(
            sa.text("DELETE FROM subscription_instance_relations WHERE domain_model_attr=:attr"),
            {"attr": domain_model_attr},
        )


def backfill_resource_type_with_default(
    conn: sa.engine.Connection, resource_type_id: UUID, product_block_name: str, value: Any
) -> None:
    conn.execute(
        sa.text(
            """
            INSERT INTO subscription_instance_values (subscription_instance_id, resource_type_id, value)
            SELECT si.subscription_instance_id AS subscription_instance_id, :resource_type_id AS resource_type_id, :value AS value
            FROM subscription_instances AS si
                JOIN product_blocks pb on si.product_block_id = pb.product_block_id
                WHERE pb.name = :product_block_name;
            """
        ),
        {
            "resource_type_id": resource_type_id,
            "product_block_name": product_block_name,
            "value": value,
        },
    )


def remove_resource_type_from_subscription_instance(conn: sa.engine.Connection, resource_type_name: str) -> None:
    resource_type_id = get_resource_type_id_by_name(conn, resource_type_name)

    conn.execute(
        sa.text("""DELETE FROM subscription_instance_values WHERE resource_type_id=:resource_type_id"""),
        {"resource_type_id": resource_type_id},
    )
