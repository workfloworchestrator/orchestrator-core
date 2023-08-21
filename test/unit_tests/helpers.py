import json

from deepdiff import DeepDiff


def assert_no_diff(expected, actual, exclude_paths=None):
    diff = DeepDiff(expected, actual, ignore_order=True, exclude_paths=exclude_paths)
    prettydiff = f"Difference: {json.dumps(diff, indent=2, default=lambda x: str(x))}"

    assert diff == {}, f"Difference between expected and actual output\n{prettydiff}"
