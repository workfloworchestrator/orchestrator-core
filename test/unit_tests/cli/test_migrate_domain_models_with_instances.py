import json

from sqlalchemy import select, text

from orchestrator.cli.database import migrate_domain_models
from orchestrator.db import db
from orchestrator.db.models import ResourceTypeTable, SubscriptionInstanceValueTable
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.domain.base import ProductBlockModel, SubscriptionModel
from orchestrator.services.resource_types import get_resource_types
from orchestrator.types import SubscriptionLifecycle
from test.unit_tests.fixtures.products.product_blocks.product_block_one import DummyEnum


def test_migrate_domain_models_new_product_block(
    test_product_type_one, test_product_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class TestBlock(ProductBlockModel, product_block_name="test block", lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
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

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert "new_block" not in subscription.block.model_dump()

    test_expected_before_upgrade()

    assert len(upgrade_sql) == 5
    assert len(downgrade_sql) == 5

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    new_model: ProductTypeOneForTestNew = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert new_model.new_block
    assert new_model.new_block.str_field
    assert new_model.new_block.str_field == "test"

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_new_product_block_on_product_block(
    test_product_type_one, test_product_block_one, product_one_subscription_1, test_product_sub_block_one
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class TestBlock(ProductBlockModel, product_block_name="test block", lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        str_field: str
        int_field: int
        list_field: list[int]
        enum_field: DummyEnum
        new_block: TestBlock

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
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

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert "new_block" not in subscription.block.model_dump()

    test_expected_before_upgrade()

    assert len(upgrade_sql) == 6
    assert len(downgrade_sql) == 5

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    new_model: ProductTypeOneForTestNew = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert new_model.block.new_block
    assert new_model.block.new_block.str_field
    assert new_model.block.new_block.str_field == "test"

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_new_resource_type(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        int_field: int
        str_field: str
        list_field: list[int]
        enum_field: DummyEnum
        new_int_field: int

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"new_int_field": {"ProductBlockOneForTest": "1", "description": "test new int field type"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 4

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert "new_int_field" not in subscription.block.model_dump()

        new_int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "new_int_field"])
        assert not new_int_field_resource

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    updated_subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert updated_subscription.block
    assert updated_subscription.block.new_int_field == 1

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_new_product_block_and_resource_type(
    test_product_type_one, test_product_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class TestBlock(ProductBlockModel, product_block_name="test block", lifecycle=[SubscriptionLifecycle.ACTIVE]):
        str_field: str
        new_str_field: str

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        new_block: TestBlock
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps(
        {
            "test block": {"description": "test block description", "tag": "test_block_tag"},
            "str_field": {"test block": "test"},
            "new_str_field": {"description": "new str field desc", "test block": "new test"},
        }
    )
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert "new_block" not in subscription.block.model_dump()

    test_expected_before_upgrade()

    assert len(upgrade_sql) == 8
    assert len(downgrade_sql) == 9

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    new_model: ProductTypeOneForTestNew = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert new_model.new_block
    assert new_model.new_block.str_field
    assert new_model.new_block.str_field == "test"
    assert new_model.new_block.new_str_field == "new test"

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_update_resource_type(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        str_field: str
        int_field: int
        enum_field: DummyEnum
        new_list_field: list[int]

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    updates = json.dumps({"resource_types": {"list_field": "new_list_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, updates=updates)

    assert len(upgrade_sql) == 1
    assert "UPDATE" in upgrade_sql[0]
    assert len(downgrade_sql) == 1
    assert "UPDATE" in downgrade_sql[0]

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert subscription.block.list_field == [10, 20, 30]
        assert "new_int_field" not in subscription.block.model_dump()

        new_int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "new_int_field"])
        assert not new_int_field_resource

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    updated_subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert updated_subscription.block.new_list_field == [10, 20, 30]

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_create_and_rename_resource_type(test_product_type_one, product_one_subscription_1):
    _, _, ProductTypeOneForTest = test_product_type_one

    class SubBlockOneForTestNewResource(
        ProductBlockModel, product_block_name="SubBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        int_field: int
        str_field: str
        new_list_field: list[int]

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTestNewResource
        sub_block_2: SubBlockOneForTestNewResource
        sub_block_list: list[SubBlockOneForTestNewResource]
        str_field: str
        int_field: int
        enum_field: DummyEnum
        new_list_field: list[int]

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"new_list_field": {"SubBlockOneForTest": "5"}})
    updates = json.dumps({"resource_types": {"list_field": "new_list_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=inputs, updates=updates)

    assert len(upgrade_sql) == 3
    assert [sql_stmt for sql_stmt in upgrade_sql if "UPDATE" in sql_stmt]
    assert len(downgrade_sql) == 3
    assert [sql_stmt for sql_stmt in downgrade_sql if "UPDATE" in sql_stmt]

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert subscription.block.list_field == [10, 20, 30]
        assert "new_int_field" not in subscription.block.model_dump()
        assert "new_int_field" not in subscription.block.sub_block.model_dump()

        new_int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "new_int_field"])
        assert not new_int_field_resource

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    updated_instance = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert updated_instance.block.new_list_field == [10, 20, 30]
    assert updated_instance.block.sub_block.new_list_field == [5]

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_create_and_rename_and_delete_resource_type(
    test_product_type_sub_list_union,
    product_sub_list_union_subscription_1,
):
    _, _, ProductSubListUnion = test_product_type_sub_list_union

    class SubBlockOneForTestChanged(
        ProductBlockModel, product_block_name="SubBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        changed_int_field: int

    class SubBlockTwoForTestChanged(
        ProductBlockModel, product_block_name="SubBlockTwoForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        int_field_2: int
        changed_int_field: int

    class ProductBlockWithListUnionForTestNew(
        ProductBlockModel,
        product_block_name="ProductBlockWithListUnionForTest",
        lifecycle=[SubscriptionLifecycle.ACTIVE],
    ):
        list_union_blocks: list[SubBlockTwoForTestChanged | SubBlockOneForTestChanged]
        changed_int_field: int
        str_field: str
        list_field: list[int]

    class ProductSubListUnionTest(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_block: ProductBlockWithListUnionForTestNew

    SUBSCRIPTION_MODEL_REGISTRY["ProductSubListUnion"] = ProductSubListUnionTest

    inputs = json.dumps({"changed_int_field": {"SubBlockOneForTest": "5", "SubBlockTwoForTest": "2"}})
    updates = json.dumps({"resource_types": {"int_field": "changed_int_field"}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=inputs, updates=updates)

    assert len(upgrade_sql) == 5
    assert [sql_stmt for sql_stmt in upgrade_sql if "UPDATE" in sql_stmt]
    assert len(downgrade_sql) == 3
    assert [sql_stmt for sql_stmt in downgrade_sql if "UPDATE" in sql_stmt]

    def test_expected_before_upgrade():
        subscription = ProductSubListUnion.from_subscription(product_sub_list_union_subscription_1)
        assert subscription.test_block.int_field == 1
        assert subscription.test_block.list_union_blocks[1].int_field == 1
        assert "int_field" not in subscription.test_block.list_union_blocks[0].model_dump()
        assert "changed_int_field" not in subscription.test_block.model_dump()
        assert "changed_int_field" not in subscription.test_block.list_union_blocks[0].model_dump()
        assert "changed_int_field" not in subscription.test_block.list_union_blocks[1].model_dump()

        new_int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "new_int_field"])
        assert not new_int_field_resource

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    updated_subscription = ProductSubListUnionTest.from_subscription(product_sub_list_union_subscription_1)
    assert updated_subscription.test_block.changed_int_field == 1
    assert updated_subscription.test_block.list_union_blocks[0].changed_int_field == 2
    assert updated_subscription.test_block.list_union_blocks[1].changed_int_field == 1
    assert "int_field" not in updated_subscription.test_block.model_dump()
    assert "int_field" not in updated_subscription.test_block.list_union_blocks[0].model_dump()
    assert "int_field" not in updated_subscription.test_block.list_union_blocks[1].model_dump()

    int_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "int_field"])
    assert not int_field_resource

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_remove_product(test_product_type_one, product_one_subscription_1):
    _, _, ProductTypeOneForTest = test_product_type_one

    del SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"]

    inputs = json.dumps({"force_delete_products": "no"})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs)

    assert len(upgrade_sql) == 7
    assert len(downgrade_sql) == 0

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTest


def test_migrate_domain_models_remove_fixed_input(
    test_product_type_one, test_product_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, ProductBlockOneForTest = test_product_block_one

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 1
    assert len(downgrade_sql) == 1

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert not subscription.test_fixed_input

    test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert "test_fixed_input" not in subscription.model_dump()

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_remove_product_block(test_product_type_one, product_one_subscription_1):
    _, _, ProductTypeOneForTest = test_product_type_one

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 0

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    assert subscription.block
    assert subscription.block.int_field

    int_field_resource: list[ResourceTypeTable] = get_resource_types(
        filters=[ResourceTypeTable.resource_type == "int_field"]
    )
    int_field_instance_values = db.session.scalars(
        select(SubscriptionInstanceValueTable).where(
            SubscriptionInstanceValueTable.resource_type_id == int_field_resource[0].resource_type_id
        )
    ).all()
    assert len(int_field_instance_values) == 3

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert "block" not in subscription.model_dump()

    int_field_instance_values = db.session.scalars(
        select(SubscriptionInstanceValueTable).where(
            SubscriptionInstanceValueTable.resource_type_id == int_field_resource[0].resource_type_id
        )
    ).all()
    assert len(int_field_instance_values) == 0

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()


def test_migrate_domain_models_remove_resource_type(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTest(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        int_field: int
        str_field: str
        enum_field: DummyEnum

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTest

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    upgrade_sql, downgrade_sql = migrate_domain_models("example", True)

    assert len(upgrade_sql) == 4
    assert len(downgrade_sql) == 0

    subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
    assert subscription.block.list_field

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert "list_field" not in subscription.block.model_dump()

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()


def test_migrate_domain_models_update_block_resource_type(
    test_product_type_one, test_product_sub_block_one, product_one_subscription_1
):
    _, _, ProductTypeOneForTest = test_product_type_one
    _, _, SubBlockOneForTest = test_product_sub_block_one

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTest
        sub_block_2: SubBlockOneForTest
        sub_block_list: list[SubBlockOneForTest]
        update_str_field: str
        int_field: int
        list_field: list[int]
        enum_field: DummyEnum

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps(
        {
            "update_str_field": {"description": "test"},
            "updates": {"block_resource_types": {"ProductBlockOneForTest": {"str_field": "update_str_field"}}},
        }
    )
    updates = json.dumps({"block_resource_types": {"ProductBlockOneForTest": {"str_field": "update_str_field"}}})
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=inputs, updates=updates)

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert subscription.block.str_field
        assert "update_str_field" not in subscription.block.model_dump()

        new_str_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "update_str_field"])
        assert not new_str_field_resource
        return subscription.block.str_field

    assert len(upgrade_sql) == 3
    assert len(downgrade_sql) == 4

    str_field_value = test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert subscription.block.update_str_field == str_field_value

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()


def test_migrate_domain_models_rename_and_update_block_resource_type(test_product_type_one, product_one_subscription_1):
    _, _, ProductTypeOneForTest = test_product_type_one

    class SubBlockOneForTesUpdated(
        ProductBlockModel, product_block_name="SubBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        int_field: int
        other_str_field: str

    class ProductBlockOneForTestUpdated(
        ProductBlockModel, product_block_name="ProductBlockOneForTest", lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        sub_block: SubBlockOneForTesUpdated
        sub_block_2: SubBlockOneForTesUpdated
        sub_block_list: list[SubBlockOneForTesUpdated]
        update_str_field: str
        int_field: int
        list_field: list[int]
        enum_field: DummyEnum

    class ProductTypeOneForTestNew(SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        test_fixed_input: bool
        block: ProductBlockOneForTestUpdated

    SUBSCRIPTION_MODEL_REGISTRY["TestProductOne"] = ProductTypeOneForTestNew

    inputs = json.dumps({"update_str_field": {"description": "test"}})
    updates = json.dumps(
        {
            "resource_types": {"str_field": "other_str_field"},
            "block_resource_types": {"ProductBlockOneForTest": {"other_str_field": "update_str_field"}},
        }
    )
    upgrade_sql, downgrade_sql = migrate_domain_models("example", True, inputs=inputs, updates=updates)

    def test_expected_before_upgrade():
        subscription = ProductTypeOneForTest.from_subscription(product_one_subscription_1)
        assert subscription.block.str_field
        assert "update_str_field" not in subscription.block.model_dump()

        new_str_field_resource = get_resource_types(filters=[ResourceTypeTable.resource_type == "update_str_field"])
        assert not new_str_field_resource
        return subscription.block.str_field

    assert len(upgrade_sql) == 6
    assert len(downgrade_sql) == 5

    str_field_value = test_expected_before_upgrade()

    for stmt in upgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    subscription = ProductTypeOneForTestNew.from_subscription(product_one_subscription_1)
    assert subscription.block.update_str_field == str_field_value

    for stmt in downgrade_sql:
        db.session.execute(text(stmt))
    db.session.commit()

    test_expected_before_upgrade()
