import json

from deepdiff import DeepDiff


def assert_no_diff(expected, actual, exclude_paths=None):
    diff = DeepDiff(expected, actual, ignore_order=True, exclude_paths=exclude_paths)
    prettydiff = f"Difference: {json.dumps(diff, indent=2, default=lambda x: str(x))}"

    assert diff == {}, f"Difference between expected and actual output\n{prettydiff}"


# By default Pydantic v2 includes documentation urls in the errors
URL_MISSING = {"url": "https://errors.pydantic.dev/2.4/v/missing"}
URL_STR_TYPE = {"url": "https://errors.pydantic.dev/2.4/v/string_type"}
URL_PARSING = {"url": "https://errors.pydantic.dev/2.4/v/uuid_parsing"}
URL_VALUE = {"url": "https://errors.pydantic.dev/2.4/v/value_error"}
