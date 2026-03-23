# Copyright 2019-2020 SURF, GÉANT.
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

import pytest

from orchestrator.config.assignee import Assignee


class TestAssignee:
    def test_has_exactly_4_members(self) -> None:
        assert len(Assignee) == 4

    @pytest.mark.parametrize(
        "member,expected_value",
        [
            (Assignee.NOC, "NOC"),
            (Assignee.SYSTEM, "SYSTEM"),
            (Assignee.CHANGES, "CHANGES"),
            (Assignee.KLANTSUPPORT, "KLANTSUPPORT"),
        ],
        ids=["NOC", "SYSTEM", "CHANGES", "KLANTSUPPORT"],
    )
    def test_member_has_correct_string_value(self, member: Assignee, expected_value: str) -> None:
        assert member == expected_value

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("NOC", Assignee.NOC),
            ("SYSTEM", Assignee.SYSTEM),
            ("CHANGES", Assignee.CHANGES),
            ("KLANTSUPPORT", Assignee.KLANTSUPPORT),
        ],
        ids=["NOC", "SYSTEM", "CHANGES", "KLANTSUPPORT"],
    )
    def test_roundtrip_from_string(self, raw: str, expected: Assignee) -> None:
        assert Assignee(raw) is expected

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            Assignee("INVALID")

    def test_is_subclass_of_str(self) -> None:
        assert issubclass(Assignee, str)

    @pytest.mark.parametrize(
        "member",
        list(Assignee),
        ids=[m.value for m in Assignee],
    )
    def test_member_is_str_instance(self, member: Assignee) -> None:
        assert isinstance(member, str)
