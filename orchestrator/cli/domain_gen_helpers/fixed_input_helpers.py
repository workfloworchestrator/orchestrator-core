from more_itertools import flatten
from sqlalchemy import select
from sqlalchemy.sql.expression import Delete, Insert, Update
from sqlalchemy.sql.selectable import ScalarSelect

from orchestrator.cli.domain_gen_helpers.helpers import sql_compile
from orchestrator.cli.domain_gen_helpers.product_helpers import get_product_id, get_product_ids
from orchestrator.cli.helpers.input_helpers import get_user_input
from orchestrator.cli.helpers.print_helpers import COLOR, print_fmt, str_fmt
from orchestrator.db import db
from orchestrator.db.models import FixedInputTable


def map_update_fixed_inputs(product_diffs: dict[str, dict[str, set[str]]]) -> dict[str, dict[str, str]]:
    """Map fixed inputs to update.

    Args:
        product_diffs: Dict with product differences.
            - key: product name
            - value: Dict with differences between model and database.
                - key: difference name, 'missing_fixed_inputs_in_model' and 'missing_fixed_inputs_in_db' are used to check if a fixed input can be renamed.
                - value: Set of fixed input names.

    Returns: Dict with updated fixed inputs mapped by product.
        key: product name.
        value: Dict with updated fixed inputs.
            - key: old fixed input name.
            - value: new fixed input name.
    """
    print_fmt("\nUpdate fixed inputs", flags=[COLOR.BOLD, COLOR.UNDERLINE])

    def rename_map(product_name: str, product_diff: dict[str, set[str]]) -> dict[str, str]:
        db_props = list(product_diff.get("missing_fixed_inputs_in_model", []))
        model_props = list(product_diff.get("missing_fixed_inputs_in_db", []))

        # If 1 field differs between model and db, ask if this is a renaming, otherwise delete/create all differing fields
        if len(db_props) == 1 and len(model_props) == 1:
            should_rename = get_user_input(
                "".join(
                    [
                        "Do you wish to rename fixed input ",
                        str_fmt(db_props[0], flags=[COLOR.MAGENTA]),
                        " to ",
                        str_fmt(model_props[0], flags=[COLOR.MAGENTA]),
                        " for product ",
                        str_fmt(product_name, flags=[COLOR.BOLD]),
                        "? [y/N]: ",
                    ]
                ),
                "N",
            )
            if should_rename == "y":
                product_diffs[product_name]["missing_fixed_inputs_in_model"] = set()
                product_diffs[product_name]["missing_fixed_inputs_in_db"] = set()
                return {db_props[0]: model_props[0]}
        return {}

    updates = {name: rename_map(name, diff) for name, diff in product_diffs.items()}
    return {k: v for k, v in updates.items() if v}


def generate_create_fixed_inputs_sql(
    fixed_inputs: dict[str, set[str]], inputs: dict[str, dict[str, str]], revert: bool = False
) -> list[str]:
    """Generate SQL to create fixed inputs.

    Args:
        fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.
        inputs: Optional Dict to prefill fixed input 'value' per product.
            - key: fixed input name.
            - value: Dict with prefilled value.
                - key: 'value' as key.
                - value: prefilled value.
        revert: boolean to create SQL string with value filled by the database.

    Returns: List of SQL to create fixed inputs.
    """
    print_fmt("\nCreate fixed inputs", flags=[COLOR.BOLD, COLOR.UNDERLINE])

    def create_fixed_input(fixed_input: str, product_names: set[str]) -> str:
        def create_product_insert_dict(product_name: str) -> dict[str, str | ScalarSelect]:
            product_id_sql = get_product_id(product_name)

            if revert:
                stmt = select(FixedInputTable.value).where(
                    FixedInputTable.name == fixed_input, FixedInputTable.product_id == product_id_sql
                )
                value = db.session.scalars(stmt).one()
            else:
                prompt = "".join(
                    [
                        "Supply fixed input value for product ",
                        str_fmt(product_name, flags=[COLOR.BOLD]),
                        " and fixed input ",
                        str_fmt(fixed_input, flags=[COLOR.MAGENTA]),
                        ": ",
                    ]
                )
                value = inputs.get(product_name, {}).get(fixed_input) or get_user_input(prompt)

            return {"name": fixed_input, "value": value, "product_id": product_id_sql}

        fixed_input_dicts = [create_product_insert_dict(product_name) for product_name in product_names]
        return str(sql_compile(Insert(FixedInputTable).values(fixed_input_dicts)))

    return [create_fixed_input(*item) for item in fixed_inputs.items()]


def generate_delete_fixed_inputs_sql(fixed_inputs: dict[str, set[str]]) -> list[str]:
    """Generate SQL to delete fixed inputs.

    Args:
        fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.

    Returns: List of SQL strings to delete fixed inputs.
    """

    def delete_fixed_input(fixed_input: str, product_names: set[str]) -> str:
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


def generate_update_fixed_inputs_sql(product_fixed_inputs: dict[str, dict[str, str]]) -> list[str]:
    """Generate SQL to update fixed inputs.

    Args:
        product_fixed_inputs: Dict with product names by fixed input.
            - key: fixed input value.
            - value: product names.

    Returns: List of SQL strings to update fixed inputs.
    """

    def update_fixed_inputs(product_name: str, fixed_inputs: dict[str, str]) -> list[str]:
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
