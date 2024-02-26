import json
from unittest import mock

from deepdiff import DeepDiff


def assert_no_diff(expected, actual, exclude_paths=None):
    diff = DeepDiff(expected, actual, ignore_order=True, exclude_paths=exclude_paths)
    prettydiff = f"Difference: {json.dumps(diff, indent=2, default=lambda x: str(x))}"

    assert diff == {}, f"Difference between expected and actual output\n{prettydiff}"


# By default Pydantic v2 includes documentation urls in the errors.
# Update these urls when upgrading Pydantic.
URL_MISSING = {"url": mock.ANY}
URL_STR_TYPE = {"url": mock.ANY}
URL_PARSING = {"url": mock.ANY}
URL_VALUE = {"url": mock.ANY}
