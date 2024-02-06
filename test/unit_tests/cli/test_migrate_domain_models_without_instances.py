import json

from sqlalchemy import select, text

from orchestrator.cli.database import migrate_domain_models
from orchestrator.db import db
from orchestrator.db.models import ProductTable, ResourceTypeTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductBlockModel
from orchestrator.services.resource_types import get_resource_types
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def test_migrate_domain_models_new_product(test_product_type_one, test_product_sub_block_one_db):
    _, _, ProductTypeOneForTest = test_product_type_one
    inputs = {
        "TestProductOne": {
            "description": "test description",
            "tag": "test_tag",
            "product_type": "test_type",
            "test_fixed_input": "test value",
        },
        "ProductBlockOneForTest": {"description": "product block description", "tag": "test_block_tag"},
        "int_field": {"ProductBlockOneForTest": "1"},
        "str_field": {"ProductBlockOneForTest": "test"},
        "list_field": {"description": "list field desc", "ProductBlockOneForTest": "list test"},
        "enum_field": {"description": "an enum", "ProductBlockOneForTest": str(DummyEnum.FOO)},
    }
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=json.dumps(inputs))

    assert len(upgrade_sql) == 11
    assert len(downgrade_sql) == 20

    def fetch_product_ids(product_name):
        return db.session.scalars(select(ProductTable.product_id).where(ProductTable.name == product_name)).all()

    product_ids = fetch_product_ids("TestProductOne")
    assert not product_ids

    temp_product = ProductTable(
        name="TestProductOne",
        description=inputs["TestProductOne"]["description"],
        product_type=inputs["TestProductOne"]["product_type"],
        tag=inputs["TestProductOne"]["tag"],
        status="active",
    )
    db.session.add(temp_product)
    db.session.commit()

    expected_old_diff = {
        "TestProductOne": {
            "missing_fixed_inputs_in_db": {"test_fixed_input"},
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {
                    "missing_product_blocks_in_db": {"SubBlockOneForTest"},
                    "missing_resource_types_in_db": {"int_field", "list_field", "str_field", "enum_field"},
                }
            },
            "missing_product_blocks_in_db": {"ProductBlockOneForTest"},
        }
    }

    diff = ProductTypeOneForTest.diff_product_in_database(temp_product.product_id)
    assert diff == expected_old_diff

    db.session.delete(temp_product)
    db.session.commit()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    product_ids = fetch_product_ids("TestProductOne")
    assert len(product_ids)
    diff = ProductTypeOneForTest.diff_product_in_database(product_ids[0])
    assert diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    product_ids = fetch_product_ids("TestProductOne")
    assert not product_ids


def test_migrate_domain_models_new_fixed_input(test_product_one, test_product_type_one, test_product_block_one):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        new_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"TestProductOne": {"new_fixed_input": "test"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    expected_old_diff = {"TestProductOne": {"missing_fixed_inputs_in_db": {"new_fixed_input"}}}

    assert len(upgrade_sql) == 1
    assert len(downgrade_sql) == 1

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_rename_fixed_input(test_product_one, test_product_type_one, test_product_block_one):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        changed_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    updates = json.dumps({"fixed_inputs": {"TestProductOne": {"test_fixed_input": "changed_fixed_input"}}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, updates=updates)

    expected_old_diff = {
        "TestProductOne": {
            "missing_fixed_inputs_in_db": {"changed_fixed_input"},
            "missing_fixed_inputs_in_model": {"test_fixed_input"},
        }
    }

    assert len(upgrade_sql) == 1
    assert len(downgrade_sql) == 1

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_new_product_block(test_product_one, test_product_type_one, test_product_block_one):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class TestBlock(ProductBlockModel, product_block_name="test block", lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        new_block: TestBlock
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps(
        {
            "test block": {"description": "test block description", "tag": "test_block_tag"},
            "str_field": {"test block": "test"},
        }
    )
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {"test block": {"missing_resource_types_in_db": {"str_field"}}},
            "missing_product_blocks_in_db": {"test block"},
        }
    }

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 5

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_new_product_block_on_product_block(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    _, _, SubBlockOneForTest = test_product_sub_block_one

    class TestBlock(ProductBlockModel, product_block_name="test block", lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str

    class ProductBlockOneForTestUpdated(ProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        str_field: str
        int_field: int
        list_field: list[int]
        enum_field: DummyEnum
        new_block: TestBlock

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps(
        {
            "test block": {"description": "test block description", "tag": "test_block_tag"},
            "str_field": {"test block": "test"},
        }
    )
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {"missing_product_blocks_in_db": {"test block"}},
                "test block": {"missing_resource_types_in_db": {"str_field"}},
            }
        }
    }

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 5

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_new_resource_type(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(ProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        int_field: int
        str_field: str
        enum_field: DummyEnum
        list_field: list[int]
        new_int_field: int

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"new_int_field": {"ProductBlockOneForTest": 1, "description": "test new int field type"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {"missing_resource_types_in_db": {"new_int_field"}}
            }
        }
    }

    assert len(upgrade_sql) == 2
    assert len(downgrade_sql) == 4

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_rename_resource_type(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(ProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        str_field: str
        int_field: int
        enum_field: DummyEnum
        new_list_field: list[int]

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    updates = json.dumps({"resource_types": {"list_field": "new_list_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, updates=updates)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {
                    "missing_resource_types_in_db": {"new_list_field"},
                    "missing_resource_types_in_model": {"list_field"},
                }
            }
        }
    }

    assert len(upgrade_sql) == 1
    assert "UPDATE" in upgrade_sql[0]
    assert len(downgrade_sql) == 1
    assert "UPDATE" in downgrade_sql[0]

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_rename_and_relate_resource_type(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class SubBlockOneForTestNewResource(SubBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field: int
        str_field: str
        new_list_field: list[int]  # add/relate renamed resource type to block

    class ProductBlockOneForTestUpdated(ProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTestNewResource
        sub_block_2: SubBlockOneForTestNewResource
        sub_block_list: list[SubBlockOneForTestNewResource]
        str_field: str
        int_field: int
        enum_field: DummyEnum
        new_list_field: list[int]  # renamed from 'list_field'

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"new_list_field": {"SubBlockOneForTest": "test"}})
    updates = json.dumps({"resource_types": {"list_field": "new_list_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs, updates)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {
                    "missing_resource_types_in_db": {"new_list_field"},
                    "missing_resource_types_in_model": {"list_field"},
                },
                "SubBlockOneForTest": {"missing_resource_types_in_db": {"new_list_field"}},
            }
        }
    }

    assert len(upgrade_sql) == 2
    assert [sql_stmt for sql_stmt in upgrade_sql if "UPDATE" in sql_stmt]
    assert len(downgrade_sql) == 3
    assert [sql_stmt for sql_stmt in downgrade_sql if "UPDATE" in sql_stmt]

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    downgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert downgrade_diff == expected_old_diff


def test_migrate_domain_models_rename_and_relate_and_remove_resource_type(
    test_product_sub_list_union,
    test_product_type_sub_list_union,
    test_product_block_with_list_union,
    test_product_sub_block_one,
    test_product_sub_block_two,
):
    _, ProductSubListUnionProvisioning, _ = test_product_type_sub_list_union
    _, _, ProductBlockWithListUnionForTest = test_product_block_with_list_union
    _, _, SubBlockOneForTest = test_product_sub_block_one
    _, _, SubBlockTwoForTest = test_product_sub_block_two

    class SubBlockOneForTestChanged(SubBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        changed_int_field: int

    class SubBlockTwoForTestChanged(SubBlockTwoForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        int_field_2: int
        changed_int_field: int

    class ProductBlockWithListUnionForTestNew(
        ProductBlockWithListUnionForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        list_union_blocks: list[SubBlockTwoForTestChanged | SubBlockOneForTestChanged]
        changed_int_field: int
        str_field: str
        list_field: list[int]

    class ProductSubListUnionTest(ProductSubListUnionProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockWithListUnionForTestNew

    SUBSCRIPTION_MODEL_REGISTRY["ProductSubListUnion"] = ProductSubListUnionTest

    inputs = json.dumps({"changed_int_field": {"SubBlockOneForTest": "test", "SubBlockTwoForTest": "test"}})
    updates = json.dumps({"resource_types": {"int_field": "changed_int_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs, updates)

    expected_old_diff = {
        "ProductSubListUnion": {
            "missing_in_depends_on_blocks": {
                "ProductBlockWithListUnionForTest": {
                    "missing_resource_types_in_db": {"changed_int_field"},
                    "missing_resource_types_in_model": {"int_field"},
                },
                "SubBlockOneForTest": {
                    "missing_resource_types_in_db": {"changed_int_field"},
                    "missing_resource_types_in_model": {"int_field", "str_field"},
                },
                "SubBlockTwoForTest": {"missing_resource_types_in_db": {"changed_int_field"}},
            }
        }
    }

    assert len(upgrade_sql) == 4
    assert [sql_stmt for sql_stmt in upgrade_sql if "UPDATE" in sql_stmt]
    assert len(downgrade_sql) == 3
    assert [sql_stmt for sql_stmt in downgrade_sql if "UPDATE" in sql_stmt]

    before_diff = ProductSubListUnionTest.diff_product_in_database(test_product_sub_list_union)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductSubListUnionTest.diff_product_in_database(test_product_sub_list_union)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()


def test_migrate_domain_models_update_block_resource_type(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(ProductBlockOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        str_field: str
        enum_field: DummyEnum
        new_int_field: int
        list_field: list[int]

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"new_int_field": {"description": "test new int field type"}})
    updates = json.dumps({"block_resource_types": {"ProductBlockOneForTest": {"int_field": "new_int_field"}}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=inputs, updates=updates)

    expected_old_diff = {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {
                    "missing_resource_types_in_db": {"new_int_field"},
                    "missing_resource_types_in_model": {"int_field"},
                }
            }
        }
    }

    def test_expected_before_upgrade():
        before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
        assert before_diff == expected_old_diff
        int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "int_field"])
        new_int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "new_int_field"])
        assert int_field_resource
        assert not new_int_field_resource

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 4

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    upgrade_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert upgrade_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_remove_product(test_product_one, test_product_type_one):
    _, _, ProductTypeOneForTest = test_product_type_one
    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"]

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 7
    assert len(downgrade_sql) == 0

    before_diff = ProductTypeOneForTest.diff_product_in_database(test_product_one)
    assert before_diff == {}

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    product_ids = db.session.scalars(select(ProductTable.product_id).where(ProductTable.name == "TestProductOne")).all()
    assert not product_ids

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest


def test_migrate_domain_models_remove_fixed_input(test_product_one, test_product_type_one, test_product_block_one):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    expected_old_diff = {"TestProductOne": {"missing_fixed_inputs_in_model": {"test_fixed_input"}}}

    assert len(upgrade_sql) == 1
    assert len(downgrade_sql) == 1

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == expected_old_diff


def test_migrate_domain_models_remove_product_block(test_product_one, test_product_type_one):
    _, _, ProductTypeOneForTest = test_product_type_one

    class ProductTypeOneForTestNew(ProductTypeOneForTest, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 0

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == {"TestProductOne": {"missing_product_blocks_in_model": {"ProductBlockOneForTest"}}}

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()


def test_migrate_domain_models_remove_resource_type(
    test_product_one, test_product_type_one, test_product_block_one, test_product_sub_block_one
):
    _, ProductTypeOneForTestProvisioning, _ = test_product_type_one
    _, ProductBlockOneForTestProvisioning, _ = test_product_block_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTest(ProductBlockOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        int_field: int
        str_field: str
        enum_field: DummyEnum

    class ProductTypeOneForTestNew(ProductTypeOneForTestProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 4
    assert len(downgrade_sql) == 0

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == {
        "TestProductOne": {
            "missing_in_depends_on_blocks": {
                "ProductBlockOneForTest": {"missing_resource_types_in_model": {"list_field"}}
            }
        }
    }

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    before_diff = ProductTypeOneForTestNew.diff_product_in_database(test_product_one)
    assert before_diff == {}

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()
