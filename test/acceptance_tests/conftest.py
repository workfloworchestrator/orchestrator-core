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


from uuid import uuid4

import pytest
import sqlalchemy as sa
import structlog

from orchestrator.db import db, init_database
from orchestrator.migrations.helpers import (
    create_product_blocks,
    create_products,
    create_workflow,
    delete_workflow,
    ensure_default_workflows,
)
from orchestrator.settings import AppSettings
from orchestrator.targets import Target

logger = structlog.get_logger(__name__)


product_name = "Test Product"
product_block_name = "Test Product Block"

new_products = {
    product_name: {
        "product_id": uuid4(),
        "product_type": "TestProduct",
        "description": product_name,
        "tag": "TESTP",
        "status": "active",
        "product_block_ids": [],
    },
}

new_product_blocks = {
    product_block_name: {
        "product_block_id": uuid4(),
        "description": product_block_name,
        "tag": "TESTP",
        "status": "active",
        "resource_types": {
            "an_int": "An integer",
            "a_str": "A string",
            "a_bool": "A bool",
            "an_uuid": "An UUID",
            "an_ipv4": "An IPv4",
            "an_ipv6": "An IPv6",
        },
    },
}

new_workflows = [
    {
        "name": "create_test_product",
        "target": Target.CREATE,
        "description": "Create Test Product",
        "product_type": "TestProduct",
    },
]


@pytest.fixture(scope="session")
def new_test_product():
    settings = AppSettings()
    init_database(settings)
    conn = db.engine.connect()

    product_block_ids = create_product_blocks(conn, new_product_blocks)
    new_products[product_name]["product_block_ids"] = product_block_ids.values()
    create_products(conn, new_products)
    for workflow in new_workflows:
        create_workflow(conn, workflow)
    ensure_default_workflows(conn)

    yield None

    for workflow in new_workflows:
        delete_workflow(conn, workflow["name"])

    conn.execute(
        sa.text(
            "delete from processes_subscriptions where subscription_id in (select subscription_id from subscriptions where product_id in (select product_id from products where name = :name))"
        ),
        name=product_name,
    )
    conn.execute(
        sa.text("delete from subscriptions where product_id in (select product_id from products where name = :name)"),
        name=product_name,
    )

    conn.execute(sa.text("DELETE FROM products WHERE name = :name"), name=product_name)

    for product_block_name in new_product_blocks.keys():
        conn.execute(sa.text("DELETE FROM product_blocks WHERE name = :name"), name=product_block_name)

    db.session.flush()
