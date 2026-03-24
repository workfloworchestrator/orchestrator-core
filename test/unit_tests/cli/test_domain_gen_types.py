import pytest

from orchestrator.cli.domain_gen_helpers.types import (
    BlockRelationDict,
    DomainModelChanges,
    DuplicateError,
    ModelUpdates,
)

# ---------------------------------------------------------------------------
# DomainModelChanges
# ---------------------------------------------------------------------------


def test_domain_model_changes_defaults() -> None:
    changes = DomainModelChanges()
    assert changes.create_products == {}
    assert changes.delete_products == set()
    assert changes.create_product_to_block_relations == {}
    assert changes.delete_product_to_block_relations == {}
    assert changes.create_product_blocks == {}
    assert changes.delete_product_blocks == set()
    assert changes.create_product_block_relations == {}
    assert changes.delete_product_block_relations == {}
    assert changes.create_product_fixed_inputs == {}
    assert changes.update_product_fixed_inputs == {}
    assert changes.delete_product_fixed_inputs == {}
    assert changes.create_resource_types == set()
    assert changes.rename_resource_types == {}
    assert changes.update_block_resource_types == {}
    assert changes.delete_resource_types == set()
    assert changes.create_resource_type_relations == {}
    assert changes.create_resource_type_instance_relations == {}
    assert changes.delete_resource_type_relations == {}


def test_domain_model_changes_with_values() -> None:
    changes = DomainModelChanges(
        delete_products={"ProductA"},
        create_resource_types={"rt_one", "rt_two"},
        rename_resource_types={"old_name": "new_name"},
    )
    assert "ProductA" in changes.delete_products
    assert changes.create_resource_types == {"rt_one", "rt_two"}
    assert changes.rename_resource_types == {"old_name": "new_name"}


def test_domain_model_changes_is_pydantic_model() -> None:
    from pydantic import BaseModel

    assert issubclass(DomainModelChanges, BaseModel)


# ---------------------------------------------------------------------------
# ModelUpdates
# ---------------------------------------------------------------------------


def test_model_updates_defaults() -> None:
    updates = ModelUpdates()
    assert updates.fixed_inputs == {}
    assert updates.resource_types == {}
    assert updates.block_resource_types == {}


def test_model_updates_with_values() -> None:
    updates = ModelUpdates(
        fixed_inputs={"product_a": {"field": "value"}},
        resource_types={"rt_a": "new_rt_a"},
        block_resource_types={"block_a": {"rt_x": "rt_y"}},
    )
    assert updates.fixed_inputs == {"product_a": {"field": "value"}}
    assert updates.resource_types == {"rt_a": "new_rt_a"}
    assert updates.block_resource_types == {"block_a": {"rt_x": "rt_y"}}


def test_model_updates_is_pydantic_model() -> None:
    from pydantic import BaseModel

    assert issubclass(ModelUpdates, BaseModel)


# ---------------------------------------------------------------------------
# BlockRelationDict
# ---------------------------------------------------------------------------


def test_block_relation_dict_structure() -> None:
    relation: BlockRelationDict = {"name": "MyBlock", "attribute_name": "my_block"}
    assert relation["name"] == "MyBlock"
    assert relation["attribute_name"] == "my_block"


# ---------------------------------------------------------------------------
# DuplicateError
# ---------------------------------------------------------------------------


def test_duplicate_error_is_exception() -> None:
    assert issubclass(DuplicateError, Exception)


def test_duplicate_error_message_propagation() -> None:
    with pytest.raises(DuplicateError, match="duplicate found"):
        raise DuplicateError("duplicate found")


def test_duplicate_error_can_be_caught_as_exception() -> None:
    try:
        raise DuplicateError("oops")
    except Exception as exc:
        assert str(exc) == "oops"
    else:
        pytest.fail("DuplicateError was not raised")
