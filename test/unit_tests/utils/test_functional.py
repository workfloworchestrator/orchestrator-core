import functools

import pytest

from orchestrator.utils.functional import (
    as_t,
    expand_ranges,
    first_available_or_next,
    ireplace,
    join_cs,
    orig,
    to_ranges,
)


def test_join_cs():
    assert join_cs("") == ""
    assert join_cs([]) == ""
    assert join_cs(()) == ""

    assert join_cs("", []) == ""
    assert join_cs([], "") == ""
    assert join_cs("", ()) == ""
    assert join_cs((), "") == ""

    assert join_cs("a") == "a"
    assert join_cs(["a"]) == "a"
    assert join_cs(("a",)) == "a"

    assert join_cs("a", "b") == "a,b"
    assert join_cs(["a"], ["b"]) == "a,b"
    assert join_cs(["a"], ("b",)) == "a,b"

    assert join_cs("a,,b") == "a,b"

    assert join_cs("a,b") == "a,b"
    assert join_cs(["a", "b"]) == "a,b"
    assert join_cs(("a", "b")) == "a,b"

    assert join_cs("a,b", ["c", "d"]) == "a,b,c,d"
    assert join_cs(["a", "b"], "c,d") == "a,b,c,d"
    assert join_cs(("a", "b"), "c,d") == "a,b,c,d"

    assert join_cs("a,b", ["c", "d"], ("e", "f")) == "a,b,c,d,e,f"

    with pytest.raises(TypeError):
        join_cs(1, 2)

    with pytest.raises(TypeError):
        join_cs([1])


def test_first_available_or_next():
    assert first_available_or_next([0, 1, 3]) == 2
    assert first_available_or_next([0, 1, 2, 3]) == 4
    assert first_available_or_next([1, 2, 3]) == 0
    assert first_available_or_next([]) == 0

    assert first_available_or_next([0, 1, 3], start=11) == 11
    assert first_available_or_next([0, 1, 3], start=4) == 4
    assert first_available_or_next([], 22) == 22
    assert first_available_or_next([1, 100, 101], 33) == 33
    assert first_available_or_next([11, 22, 33, 44, 55], 33) == 34


def test_expand_ranges():
    assert expand_ranges([[1], [2], [10, 12]]) == [1, 2, 10, 11]
    assert expand_ranges([[1], [2], [10, 12]], inclusive=True) == [1, 2, 10, 11, 12]
    assert expand_ranges([[1], [2], [10, 12]], inclusive=True) == [1, 2, 10, 11, 12]
    assert expand_ranges([]) == []

    # sorted
    assert expand_ranges([[100], [1, 4]], inclusive=True) == [1, 2, 3, 4, 100]

    # deduplicated
    assert expand_ranges([[1, 5], [3, 5]], inclusive=True) == [1, 2, 3, 4, 5]

    with pytest.raises(ValueError):
        expand_ranges([[]])

    with pytest.raises(ValueError):
        expand_ranges([[2, 100, 3]])


def test_as_t():
    # Don't know how to check type annotations at runtime yet. Hence test only basic functionality of `as_t` and not
    # the casting of Optional[T] to just T
    x: int | None = 7
    y: int = as_t(x)
    assert y == 7
    with pytest.raises(ValueError):
        as_t(None)


def test_ireplace():
    assert list(ireplace(["1-10", "", "22"], "", "0")) == ["1-10", "0", "22"]

    # Values are tested in their entirety, hence "10" won't be replaced in the value "1-10"
    assert list(ireplace(["1-10", "", "22"], "10", "999")) == ["1-10", "", "22"]


def test_to_ranges():
    assert list(to_ranges([1, 2, 3])) == [range(1, 4)]
    assert list(to_ranges([])) == []
    assert list(to_ranges([0])) == [range(0, 1)]
    assert list(to_ranges([1, 2, 3, 7, 8, 9, 100, 200, 201, 202])) == [
        range(1, 4),
        range(7, 10),
        range(100, 101),
        range(200, 203),
    ]


def test_orig():
    def func():
        pass

    @functools.wraps(func)
    def wrapper():
        return func()

    @functools.wraps(wrapper)
    def super_wrapper():
        return wrapper()

    assert orig(wrapper) == func
    assert orig(super_wrapper) == func
