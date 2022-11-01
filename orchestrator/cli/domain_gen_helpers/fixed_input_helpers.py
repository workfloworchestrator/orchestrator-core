from typing import Dict, List, Set, Union

from more_itertools import flatten
from sqlalchemy.orm import Query
from sqlalchemy.sql.expression import Delete, Insert, Update

from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.product_helpers import get_product_id, get_product_ids
from orchestrator.db.models import FixedInputTable


def map_update_fixed_inputs(product_diffs: Dict[str, Dict[str, Set[str]]]) -> Dict[str, Dict[str, str]]:
    """Map fixed inputs to update.

    Args:
        - product_diffs: Dict with product differences.
            - key: product name
            - value: Dict with differences between model and database.
                - key: difference name, 'missing_fixed_inputs_in_model' and 'missing_fixed_inputs_in_db' are used to check if a fixed input can be renamed.
                - value: Set of fixed input names.

    Returns: Dict with updated fixed inputs mapped by product.
        - key: product name.
        - value: Dict with updated fixed inputs.
            - key: old fixed input name.
            - value: new fixed input name.
    """
    print("--- UPDATE FIXED INPUT DECISIONS ('N'= create and delete) ---")  # noqa: T001, T201

    def should_rename(product_name: str, product_diff: Dict[str, Set[str]]) -> Dict[str, str]:
        db_props = list(product_diff.get("missing_fixed_inputs_in_model", []))
        model_props = list(product_diff.get("missing_fixed_inputs_in_db", []))

        if len(db_props) == 1 and len(model_props) == 1:
            should_rename = get_user_input(
                f"rename fixed input {db_props} to {model_props} for product ['{product_name}'] (y/N): ",
                "n",
            )
            if should_rename == "y":
                product_diffs[product_name]["missing_fixed_inputs_in_model"] = set()
                product_diffs[product_name]["missing_fixed_inputs_in_db"] = set()
                return {db_props[0]: model_props[0]}
        return {}

    updates = {name: should_rename(name, diff) for name, diff in product_diffs.items()}
    return {k: v for k, v in updates.items() if v}


def generate_create_fixed_inputs_sql(
    fixed_inputs: Dict[str, Set[str]], inputs: Dict[str, Dict[str, str]], revert: bool = False
) -> List[str]:
    """Generate SQL to create fixed inputs.

    Args:
        - fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.
        - inputs: Optional Dict to prefill fixed input 'value' per product.
            - key: fixed input name.
            - value: Dict with prefilled value.
                - key: 'value' as key.
                - value: prefilled value.
        - revert: boolean to create SQL string with value filled by the database.

    Returns: List of SQL to create fixed inputs.
    """

    def create_fixed_input(fixed_input: str, product_names: Set[str]) -> str:
        def create_product_insert_dict(product_name: str) -> Dict[str, Union[str, Query]]:
            product_id_sql = get_product_id(product_name)

            if revert:
                value = (
                    FixedInputTable.query.where(
                        FixedInputTable.name == fixed_input, FixedInputTable.product_id == product_id_sql
                    )
                    .with_entities(FixedInputTable.value)
                    .one()
                )[0]
            else:
                print(f"--- PRODUCT ['{product_name}'] FIXED INPUT ['{fixed_input}'] ---")  # noqa: T001, T201
                value = inputs.get(product_name, {}).get(fixed_input) or get_user_input("Fixed input value: ")

            return {"name": fixed_input, "value": value, "product_id": product_id_sql}

        fixed_input_dicts = [create_product_insert_dict(product_name) for product_name in product_names]
        return str(sql_compile(Insert(FixedInputTable).values(fixed_input_dicts)))

    return [create_fixed_input(*item) for item in fixed_inputs.items()]


def generate_delete_fixed_inputs_sql(fixed_inputs: Dict[str, Set[str]]) -> List[str]:
    """Generate SQL to delete fixed inputs.

    Args:
        - fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.

    Returns: List of SQL strings to delete fixed inputs.
    """

    def delete_fixed_input(fixed_input: str, product_names: Set[str]) -> str:
        product_ids_sql = get_product_ids(product_names)
        return str(
            sql_compile(
                Delete(FixedInputTable).where(
                    FixedInputTable.product_id.in_(product_ids_sql),
                    FixedInputTable.name == fixed_input,
                )
            )
        )

    return [delete_fixed_input(*item) for item in fixed_inputs.items()]


def generate_update_fixed_inputs_sql(product_fixed_inputs: Dict[str, Dict[str, str]]) -> List[str]:
    """Generate SQL to update fixed inputs.

    Args:
        - product_fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.

    Returns: List of SQL strings to update fixed inputs.
    """

    def update_fixed_inputs(product_name: str, fixed_inputs: Dict[str, str]) -> List[str]:
        product_id_sql = get_product_id(product_name)

        def update_fixed_input(old_name: str, new_name: str) -> str:
            return sql_compile(
                Update(FixedInputTable)
                .where(
                    FixedInputTable.product_id == (product_id_sql),
                    FixedInputTable.name == old_name,
                )
                .values(name=new_name)
            )

        return [update_fixed_input(*fixed_input) for fixed_input in fixed_inputs.items()]

    return list(flatten([update_fixed_inputs(*item) for item in product_fixed_inputs.items()]))
