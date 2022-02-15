from typing import List, Union

from orchestrator.types import is_of_type


def test_is_of_type():
    """Some tests to see type checks are valid."""
    assert is_of_type(int, Union[int, str])
    assert is_of_type(int, Union[str, int])
    assert is_of_type(str, Union[int, str])
    assert is_of_type(str, Union[str, int])
    assert is_of_type(List[str], Union[str, int]) is False
