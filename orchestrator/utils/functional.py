# Copyright 2019-2020 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import itertools
from typing import Callable, Iterable, List, Optional, Sequence, Set, TypeVar, Union

import more_itertools
import structlog

logger = structlog.get_logger(__name__)


def first_available_or_next(values: Iterable[int], start: int = 0) -> int:
    """Return first available value or the next logical value.

    >>> first_available_or_next([0, 1, 3])
    2
    >>> first_available_or_next([0, 1, 2, 3])
    4
    >>> first_available_or_next([1, 2, 3])
    0
    >>> first_available_or_next([])
    0

    >>> first_available_or_next([0, 1, 3], start=11)
    11
    >>> first_available_or_next([0, 1, 3], start=4)
    4
    >>> first_available_or_next([], 22)
    22
    >>> first_available_or_next([1, 100, 101], 33)
    33
    >>> first_available_or_next([11, 22, 33, 44, 55], 33)
    34

    Args:
        values: an iterable of integer values.
        start: set starting value.

    Returns:
        First available value or next logical one.

    """
    # +2 -> One +1 to get as many consecutive values up to and including the max+1 value. Another +1 for one extra because range is exclusive.
    stop = max(values, default=0) + 2
    if start >= stop:
        stop = start + 1
    return min(set(range(start, stop)) - set(values))


def orig(func: Callable) -> Callable:
    """Return the function wrapped by one or more decorators.

    Args:
        func: step function

    Returns:
        Undecorated step function for testing purposes.

    """
    f = func
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__

    return f


def join_cs(*args: Union[Iterable[str], str]) -> str:
    """Return comma separated string from one or more comma separated strings or iterables of strings.

    It deals with empty strings and properly inserting comma's.

    See: `test_join_cs` for examples.

    Args:
        args: One or more comma separated strings or iterables that should be joined.

    Returns:
        A comma separated string.

    """

    def to_iterable(value: Union[Iterable[str], str]) -> Iterable[str]:
        if isinstance(value, str):
            return filter(None, value.split(","))
        return value

    return ",".join(itertools.chain(*map(to_iterable, args)))


def expand_ranges(ranges: Sequence[Sequence[int]], inclusive: bool = False) -> List[int]:
    """Expand sequence of range definitions into sorted and deduplicated list of individual values.

    A range definition is either a:

    * one element sequence -> an individual value.
    * two element sequence -> a range of values (either inclusive or exclusive).

    >>> expand_ranges([[1], [2], [10, 12]])
    [1, 2, 10, 11]
    >>> expand_ranges([[1], [2], [10, 12]], inclusive=True)
    [1, 2, 10, 11, 12]
    >>> expand_ranges([[]])
    Traceback (most recent call last):
        ...
    ValueError: Expected 1 or 2 element list for range definition. Got f0 element list instead.

    Resulting list is sorted::

        >>> expand_ranges([[100], [1, 4]], inclusive=True)
        [1, 2, 3, 4, 100]

    Args:
        ranges: sequence of range definitions
        inclusive: are the stop values of the range definition inclusive or exclusive.

    Returns:
        Sorted deduplicated list of individual values.

    Raises:
        ValueError: if range definition is not a one or two element sequence.

    """
    values: Set[int] = set()
    for r in ranges:
        if len(r) == 2:
            values.update(range(r[0], r[1] + (1 if inclusive else 0)))
        elif len(r) == 1:
            values.add(r[0])
        else:
            raise ValueError(f"Expected 1 or 2 element list for range definition. Got f{len(r)} element list instead.")
    return sorted(values)


T = TypeVar("T")


def as_t(value: Optional[T]) -> T:
    """Cast `value` to non-Optional.

    One often needs to assign a value that was typed as being `Optional` to a variable that is typed non-Optional. MyPy
    rightfully takes issue with these assignments (strict Optional checking is default since MyPy 0.600) unless we
    have explicitely determined these values to be not `None`. The most succinct way to do that is using an `assert`
    statement::

        x: Optional[int] = 7
        assert x is not None
        y: int = x

    However that gets tedious pretty fast. One might be inclined to turn off strict Optional checking. However that
    would be a bad decision; None values will percolate through data structures and cause issue at locations far from
    where they originally came from. A better solution would be to fail right where the issue occurred but using a
    somewhat more convenient syntax.

    Some languages such as Kotlin provide the `as` operator:

    .. code-block:: kotlin

        val x: Int? = 7  // ? declaring the Int to be nullable
        val y: Int = x as Int

    That is the inspiration for this function. `t` referring to the type being wrapped in an `Optional`. Hence `as_t`
    meaning `as the non-Optional type`.

    The above Python example now becomes::

        x: Optional[int] = 7
        y: int = as_t(x)

    `as_t` checks whether te value passed to it is not `None`, satisfying MyPy. If it happens to be `None` it raises a
    `ValueError`, satisfying our requirement to fail at the location where we require the value to be not None and not
    somewhere far down the code path.

    Args:
        value: `Optional` value to be casted to non-Optional

    Returns:
        non-Optional value.

    Raises:
        ValueError: in case `value` is `None`

    """
    if value is None:
        raise ValueError("Trying to cast a value to non-Optional type failed due to value being None.")
    return value


def ireplace(iterable: Iterable[T], old: T, new: T) -> Iterable[T]:
    """Replace one or more occurrences of a specific value in an iterable with another value.

    The 'i' prefix indicates 'iterable' and is there to distinguish it from other similar functions.

    >>> list(ireplace(["1-10", "", "22"], "", "0"))
    ['1-10', '0', '22']

    Args:
        iterable: The iterable that needs to have a specific value replaced for all its occurrences.
        old: The value in the iterable to replace.
        new: The value to replace `old` with.

    Returns:
        A new iterable with `old` values replaced by `new` values

    """
    yield from more_itertools.replace(iterable, lambda v: v == old, [new])


def to_ranges(i: Iterable[int]) -> Iterable[range]:
    """Convert a sorted iterable of ints to an iterable of range objects.

    IMPORTANT: the iterable passed in should be sorted and not contain duplicate elements.

    Examples::
        >>> list(to_ranges([2, 3, 4, 5, 7, 8, 9, 45, 46, 47, 49, 51, 53, 54, 55, 56, 57, 58, 59, 60, 61]))
        [range(2, 6), range(7, 10), range(45, 48), range(49, 50), range(51, 52), range(53, 62)]

    Args:
        i: sorted iterable

    Yields:
        range object for each consecutive set of integers

    """
    # The trick here is the key function (the lambda one) that calculates the difference between an element of the
    # iterable `i` and its corresponding enumeration value. For consecutive values in the iterable, this difference
    # will be the same! All these values (those with the same difference) are grouped by the `groupby` function. We
    # return the first and last element to construct a `range` object
    for _, g in itertools.groupby(enumerate(i), lambda t: t[1] - t[0]):
        group = list(g)
        yield range(group[0][1], group[-1][1] + 1)
