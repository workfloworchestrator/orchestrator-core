from more_itertools.more import one
from more_itertools.recipes import first_true
from sqlalchemy import not_, select
from sqlalchemy.orm import joinedload

from orchestrator.db import ProductTable, WorkflowTable, db
from orchestrator.db.models import FixedInputTable
from orchestrator.services import products
from orchestrator.services.products import get_products
from orchestrator.targets import Target
from orchestrator.utils.fixed_inputs import fixed_input_configuration as fi_configuration
from orchestrator.workflows import ALL_WORKFLOWS


def test_all_workflows_have_matching_targets_and_descriptions():
    for key, lazy_wf in ALL_WORKFLOWS.items():
        workflow = lazy_wf.instantiate()
        db_workflow = db.session.scalars(WorkflowTable.select().where(WorkflowTable.name == key)).first()
        if db_workflow:
            # Test workflows might not exist in the database
            assert workflow.target == db_workflow.target
            assert workflow.name == db_workflow.name
            assert workflow.description == db_workflow.description


def test_all_products_have_at_least_one_workflow():
    prods_without_wf = db.session.scalars(
        select(ProductTable).where(not_(ProductTable.workflows.any())).with_only_columns(ProductTable.name)
    ).all()
    assert len(prods_without_wf) == 0, (
        f"These products do not have a workflow " f"associated with them: {', '.join(prods_without_wf)}."
    )


def test_all_non_system_workflows_have_at_least_one_product(generic_product_1):
    wfs_without_prod = db.session.scalars(
        WorkflowTable.select()
        .where(WorkflowTable.target != Target.SYSTEM, not_(WorkflowTable.products.any()))
        .with_only_columns(WorkflowTable.name)
    ).all()

    assert len(wfs_without_prod) == 0, (
        f"These workflows do not have a product " f"associated with them: {', '.join(wfs_without_prod)}."
    )


def test_all_active_products_have_a_modify_note():
    """Note: when fail: create a migration for the new product with `helpers/create_missing_modify_note_workflows()`."""
    modify_workflow = db.session.scalars(WorkflowTable.select().where(WorkflowTable.name == "modify_note")).first()

    products = get_products(filters=[ProductTable.status == "active"])
    result = [product.name for product in products if modify_workflow not in product.workflows]
    assert not len(result), f"These products do not have a modify_note workflow {', '.join(result)}."


def test_db_fixed_input_config():
    fixed_input_configuration = fi_configuration()

    product_tags = products.get_tags()
    fixed_inputs = db.session.scalars(select(FixedInputTable).options(joinedload(FixedInputTable.product))).all()

    data = {"fixed_inputs": [], "by_tag": {}}
    for tag in product_tags:
        data["by_tag"][tag] = []

    for fi in fixed_inputs:
        fi_data = first_true(
            fixed_input_configuration["fixed_inputs"], None, lambda i: i["name"] == fi.name  # noqa: B023
        )
        assert fi_data, fi
        assert fi.value in fi_data["values"], fi

        tag_data = {one(fi) for fi in fixed_input_configuration["by_tag"][fi.product.tag]}
        tag_data_required = {one(fi) for fi in fixed_input_configuration["by_tag"][fi.product.tag] if fi[one(fi)]}
        assert tag_data, fi
        assert not {fi.name for fi in fi.product.fixed_inputs} - set(tag_data), fi.product.name
        assert not set(tag_data_required) - {fi.name for fi in fi.product.fixed_inputs}, fi.product.name
