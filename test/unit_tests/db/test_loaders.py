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

"""Tests for loader utilities: _split_path, _relation_type_to_loader_func (direction→strategy mapping), and _join_attr_loaders (reduce-based chaining)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import RelationshipDirection, joinedload, selectinload, subqueryload
from sqlalchemy.orm.strategies import SubqueryLoader

from orchestrator.db.loaders import AttrLoader, _join_attr_loaders, _relation_type_to_loader_func, _split_path


def _make_relationship(direction: RelationshipDirection, strategy=None) -> MagicMock:
    rel = MagicMock()
    rel.direction = direction
    rel.strategy = strategy if strategy is not None else MagicMock(spec=object)
    return rel


def _make_attr_loader(loader_fn=None, attr=None, next_model=None) -> AttrLoader:
    return AttrLoader(
        loader_fn=loader_fn or MagicMock(name="loader_fn"),
        attr=attr or MagicMock(name="attr"),
        next_model=next_model or MagicMock(name="next_model"),
    )


# --- _split_path ---


@pytest.mark.parametrize(
    "path,expected",
    [
        pytest.param("a", ["a"], id="single"),
        pytest.param("a.b", ["a", "b"], id="two"),
        pytest.param("a.b.c", ["a", "b", "c"], id="three"),
    ],
)
def test_split_path(path: str, expected: list[str]) -> None:
    assert list(_split_path(path)) == expected


# --- _relation_type_to_loader_func ---


@pytest.mark.parametrize(
    "direction,strategy,expected_fn",
    [
        pytest.param(RelationshipDirection.MANYTOONE, None, joinedload, id="manytoone-joined"),
        pytest.param(RelationshipDirection.ONETOMANY, None, selectinload, id="onetomany-selectin"),
        pytest.param(RelationshipDirection.MANYTOMANY, None, selectinload, id="manytomany-selectin"),
        pytest.param(
            RelationshipDirection.ONETOMANY,
            MagicMock(spec=SubqueryLoader),
            subqueryload,
            id="onetomany-subquery",
        ),
    ],
)
def test_relation_type_to_loader_func(
    direction: RelationshipDirection, strategy: object | None, expected_fn: object
) -> None:
    rel = _make_relationship(direction, strategy)
    assert _relation_type_to_loader_func(rel) is expected_fn


def test_unrecognized_direction_raises() -> None:
    rel = MagicMock()
    rel.direction = object()
    with pytest.raises(TypeError, match="Unrecognized relationship direction"):
        _relation_type_to_loader_func(rel)


# --- _join_attr_loaders ---


def test_join_attr_loaders_empty() -> None:
    assert _join_attr_loaders([]) is None


def test_join_attr_loaders_single() -> None:
    mock_attr = MagicMock()
    mock_result = MagicMock()
    mock_fn = MagicMock(return_value=mock_result)
    loader = _make_attr_loader(loader_fn=mock_fn, attr=mock_attr)
    assert _join_attr_loaders([loader]) is mock_result
    mock_fn.assert_called_once_with(mock_attr)


def test_join_attr_loaders_chaining() -> None:
    first_load = MagicMock()
    chained = MagicMock()

    first_fn = MagicMock(return_value=first_load)
    first_fn.__name__ = "selectinload"

    second_fn = MagicMock()
    second_fn.__name__ = "joinedload"

    second_attr = MagicMock()
    first_load.joinedload = MagicMock(return_value=chained)

    loaders = [
        _make_attr_loader(loader_fn=first_fn, attr=MagicMock()),
        _make_attr_loader(loader_fn=second_fn, attr=second_attr),
    ]

    assert _join_attr_loaders(loaders) is chained
    first_load.joinedload.assert_called_once_with(second_attr)
