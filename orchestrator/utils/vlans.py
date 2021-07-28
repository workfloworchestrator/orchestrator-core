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


from __future__ import annotations

import operator
from collections import abc
from functools import reduce
from typing import AbstractSet, Any, Iterable, Iterator, List, Optional, Sequence, Tuple, Union, cast

from more_itertools import first, last

from orchestrator.utils.functional import expand_ranges, to_ranges


class VlanRanges(abc.Set):
    """Represent VLAN ranges.

    This class is quite liberal in what it accepts as valid VLAN ranges. All of:

    - overlapping ranges
    - ranges with start value > stop value
    - ranges with extraneous whitespace

    are all accepted and normalized to a canonical value.

    Examples::

        # These are all equivalent
        VlanRanges("4,10-12,11-14")
        VlanRanges("4,  ,11 - 14, 10-  12")
        VlanRanges("4,10-14")
        VlanRanges([4, 10, 11, 12, 13, 14])
        VlanRanges([[4], [10,12], [11,14]])
        VlanRanges([(4, 4), (10, 14)])

    """

    _vlan_ranges: Tuple[range, ...]

    def __init__(self, val: Optional[Union[str, int, Iterable[int], Sequence[Sequence[int]]]] = None) -> None:
        # The idea is to bring all acceptable values to one canonical intermediate format: the `Sequence[Sequence[
        # int]]`. Where the inner sequence is either a one or two element sequence. The one element sequence
        # represents a single VLAN, the two element sequence represents a VLAN range.
        #
        # An example of this intermediate format is::
        #
        #     vlans = [[5], [10, 12]]
        #
        # That example represents 4 VLANs, namely: 5, 10, 11, 12. The latter three VLANs are encode as a range.
        #
        # This intermediate format happens to be the format as accepted by :func:`expand_ranges`. This function has
        # the advantage of deduplicating overlapping ranges or VLANs specified more than once. In addition its return
        # value can be use as input to the :func:`to_ranges` function.
        vlans: Sequence[Sequence[int]] = []
        if val is None:
            self._vlan_ranges = ()
            return
        elif isinstance(val, str):
            if val.strip() != "":
                # This might look complex, but it does handle strings such as `"  3, 4, 6-9, 4, 8 - 10"`
                try:
                    vlans = list(map(lambda s: list(map(int, s.strip().split("-"))), val.split(",")))
                except ValueError:
                    raise ValueError(f"{val} could not be converted to a {self.__class__.__name__} object.")
        elif isinstance(val, int):
            vlans = [[val]]
        elif isinstance(val, abc.Sequence):
            if len(val) > 0:
                if isinstance(first(val), int):
                    vlans = list(map(lambda x: [x], val))
                elif isinstance(first(val), abc.Sequence):
                    vlans = cast(Sequence[Sequence[int]], val)
                else:
                    raise ValueError(f"{val} could not be converted to a {self.__class__.__name__} object.")
        elif isinstance(val, abc.Iterable):
            vlans = list(map(lambda x: [x], val))  # type: ignore
        else:
            raise ValueError(f"{val} could not be converted to a {self.__class__.__name__} object.")

        er = expand_ranges(vlans, inclusive=True)
        if er and not (first(er) >= 0 and last(er) <= 4096):
            raise ValueError(f"{val} is out of range (0-4096).")

        self._vlan_ranges = tuple(to_ranges(er))

    def to_list_of_tuples(self) -> List[Tuple[int, int]]:
        """Construct list of tuples representing the VLAN ranges.

        Example::

            >>> VlanRanges("10 - 12, 8").to_list_of_tuples()
            [(8, 8), (10, 12)]

        Returns:
            The VLAN ranges as contained in this object.

        """
        # `range` objects have an exclusive `stop`. VlanRanges is expressed using terms that use an inclusive stop,
        # which is one less then the exclusive one we use for the internal representation. Hence the `-1`
        return [(vr.start, vr.stop - 1) for vr in self._vlan_ranges]

    def __contains__(self, key: object) -> bool:
        return any(map(lambda range_from_self: key in range_from_self, self._vlan_ranges))

    def __iter__(self) -> Iterator[int]:
        # The power of choosing proper abstractions: `range` objects already define an __iter__ method. Hence all we
        # need to do, is delegated to them.
        for vr in self._vlan_ranges:
            yield from vr

    def __len__(self) -> int:
        """Return the number of VLANs represented by this VlanRanges object.

        Returns:
            Number of VLAN's

        """
        return sum(len(r) for r in self._vlan_ranges)

    def __str__(self) -> str:
        # `range` objects have an exclusive `stop`. VlanRanges is expressed using terms that use an inclusive stop,
        # which is one less then the exclusive one we use for the internal representation. Hence the `-1`
        return ",".join(str(vr.start) if len(vr) == 1 else f"{vr.start}-{vr.stop - 1}" for vr in self._vlan_ranges)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({str(self.to_list_of_tuples())})"

    def __json__(self) -> str:
        return str(self)

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            return False
        return self._vlan_ranges == o._vlan_ranges

    def __hash__(self) -> int:
        return hash(self._vlan_ranges)

    def __sub__(self, other: Union[int, AbstractSet[Any]]) -> VlanRanges:
        if isinstance(other, int):
            new_set = set(self)
            new_set.remove(other)
            return VlanRanges(new_set)
        else:
            return VlanRanges(set(self) - set(other))

    def __and__(self, other: AbstractSet[Any]) -> VlanRanges:
        return VlanRanges(set(self) & set(other))

    def __or__(self, other: AbstractSet[Any]) -> VlanRanges:
        return VlanRanges(set(self) | set(other))

    def __xor__(self, other: AbstractSet[Any]) -> VlanRanges:
        return VlanRanges(set(self) ^ set(other))

    def isdisjoint(self, other: Iterable[Any]) -> bool:
        return set(self).isdisjoint(other)

    def union(self, *others: AbstractSet[Any]) -> VlanRanges:
        return reduce(operator.__or__, others, self)

    @classmethod
    def __get_validators__(cls) -> Iterator:
        yield cls.validate

    @classmethod
    def validate(cls, v: Optional[Union[str, int, Iterable[int], Sequence[Sequence[int]]]]) -> VlanRanges:
        # The constructor of VlanRanges performs the validations.
        if isinstance(v, VlanRanges):
            return v
        return cls(v)
