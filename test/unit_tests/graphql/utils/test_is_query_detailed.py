# Copyright 2019-2026 SURF, GÉANT.
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

from unittest.mock import MagicMock

import pytest
from strawberry.types.nodes import FragmentSpread, InlineFragment, SelectedField

from orchestrator.core.graphql.utils import is_query_detailed, is_querying_page_data

is_test_query_detailed = is_query_detailed(("basic", "name"))


def _field(name: str, *selections, alias: str | None = None) -> SelectedField:
    return SelectedField(name=name, directives={}, arguments={}, alias=alias, selections=list(selections))


def _fragment(*selections) -> FragmentSpread:
    return FragmentSpread(name="fragment", type_condition="graphql type", directives={}, selections=list(selections))


def _inline(*selections) -> InlineFragment:
    return InlineFragment(
        type_condition="SubscriptionInterfaceSearchConnection", directives={}, selections=list(selections)
    )


def _page(*selections) -> SelectedField:
    return _field("subscriptions", _field("page", *selections), _field("pageInfo", _field("totalItems")))


@pytest.mark.parametrize(
    "root, expected",
    [
        pytest.param(_page(_field("basic"), _field("name")), False, id="basic-fields"),
        pytest.param(_page(_fragment(_field("basic"), _field("name"))), False, id="basic-fragment-fields"),
        pytest.param(_page(_field("detailed"), _field("not basic")), True, id="detailed-fields"),
        pytest.param(_page(_fragment(_field("detailed"), _field("not basic"))), True, id="detailed-fragment-fields"),
        pytest.param(
            _page(_field("basic"), _field("name"), _field("detailed"), _field("not basic")),
            True,
            id="basic-and-detailed-fields",
        ),
    ],
)
def test_is_test_query_detailed_reads_page(root, expected):
    assert is_test_query_detailed(MagicMock(selected_fields=[root])) is expected


@pytest.mark.parametrize(
    "root, expected",
    [
        pytest.param(
            _field("subscriptions", _field("searchEdges", _field("node", _field("basic")))),
            False,
            id="search-edges-basic",
        ),
        pytest.param(
            _field("subscriptions", _field("searchEdges", _field("node", _field("detailed")))),
            True,
            id="search-edges-detailed",
        ),
        pytest.param(
            _field(
                "subscriptions",
                _field("page", _field("detailed")),
                _field("searchEdges", _field("node", _field("basic"))),
            ),
            True,
            id="detail-in-page-only",
        ),
        pytest.param(
            _field(
                "subscriptions",
                _field("page", _field("basic"), alias="a"),
                _field("page", _field("detailed"), alias="b"),
            ),
            True,
            id="aliased-page",
        ),
        pytest.param(_field("subscription", _field("basic"), _field("detailed")), True, id="single-entity"),
    ],
)
def test_is_test_query_detailed_reads_entity_selections(root, expected):
    assert is_test_query_detailed(MagicMock(selected_fields=[root])) is expected


@pytest.mark.parametrize(
    "root, expected",
    [
        pytest.param(_field("subscriptions", _fragment(_field("page", _field("basic")))), False, id="page-in-fragment"),
        pytest.param(_field("subscriptions", _inline(_field("page", _field("basic")))), False, id="page-in-inline"),
        pytest.param(
            _field("subscriptions", _fragment(_field("page", _field("detailed")))), True, id="detail-in-fragment"
        ),
        pytest.param(
            _field("subscriptions", _fragment(_field("searchEdges", _field("node", _field("basic"))))),
            False,
            id="search-edges-in-fragment",
        ),
    ],
)
def test_is_test_query_detailed_reads_connection_fragments(root, expected):
    assert is_test_query_detailed(MagicMock(selected_fields=[root])) is expected


@pytest.mark.parametrize(
    "root, expected",
    [
        pytest.param(_field("subscriptions", _field("page", _field("basic"))), True, id="page"),
        pytest.param(_field("subscriptions", _fragment(_field("page", _field("basic")))), True, id="page-in-fragment"),
        pytest.param(_field("subscriptions", _inline(_field("page", _field("basic")))), True, id="page-in-inline"),
        pytest.param(_field("subscriptions", _field("pageInfo", _field("totalItems"))), False, id="no-page"),
    ],
)
def test_is_querying_page_data(root, expected):
    assert is_querying_page_data(MagicMock(selected_fields=[root])) is expected
