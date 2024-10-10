import json
from unittest import mock

from deepdiff import DeepDiff


def assert_no_diff(expected, actual, exclude_paths=None):
    diff = DeepDiff(expected, actual, ignore_order=True, exclude_paths=exclude_paths)
    prettydiff = f"Difference: {json.dumps(diff, indent=2, default=lambda x: str(x))}"

    assert diff == {}, f"Difference between expected and actual output\n{prettydiff}"


def safe_delete_product_block_id(product_block_class):
    """Safely delete product_block_id from product block class if its defined.

    When a product block is not defined within a fixture function, the product_block_id
    is stored inside the class and is kept through multiple tests,
    which results in a foreign key error product block does not exist.
    """
    try:
        del product_block_class.product_block_id
    except AttributeError:
        pass


# By default Pydantic v2 includes documentation urls in the errors.
# Update these urls when upgrading Pydantic.
URL_MISSING = {"url": mock.ANY}
URL_STR_TYPE = {"url": mock.ANY}
URL_PARSING = {"url": mock.ANY}
URL_VALUE = {"url": mock.ANY}
