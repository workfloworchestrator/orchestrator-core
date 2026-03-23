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

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import RelationshipDirection, joinedload, selectinload, subqueryload
from sqlalchemy.orm.strategies import SubqueryLoader

from orchestrator.db.loaders import AttrLoader, _join_attr_loaders, _relation_type_to_loader_func, _split_path


def _make_relationship(direction: RelationshipDirection, strategy=None) -> MagicMock:
    """Build a mock RelationshipProperty with the given direction and strategy."""
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


class TestSplitPath:
    def test_single_segment_yields_one_field(self):
        result = list(_split_path("instances"))
        assert result == ["instances"]

    def test_two_segments_yields_two_fields(self):
        result = list(_split_path("instances.product_block"))
        assert result == ["instances", "product_block"]

    def test_three_segments_yields_three_fields(self):
        result = list(_split_path("a.b.c"))
        assert result == ["a", "b", "c"]

    def test_empty_string_yields_one_empty_string(self):
        result = list(_split_path(""))
        assert result == [""]

    def test_preserves_field_names_exactly(self):
        result = list(_split_path("subscription_id.resource_type"))
        assert result == ["subscription_id", "resource_type"]

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("a", ["a"]),
            ("a.b", ["a", "b"]),
            ("a.b.c", ["a", "b", "c"]),
            ("a.b.c.d", ["a", "b", "c", "d"]),
        ],
        ids=["one", "two", "three", "four"],
    )
    def test_parametrized_split(self, path: str, expected: list):
        assert list(_split_path(path)) == expected


class TestRelationTypeToLoaderFunc:
    def test_manytoone_returns_joinedload(self):
        rel = _make_relationship(RelationshipDirection.MANYTOONE)
        result = _relation_type_to_loader_func(rel)
        assert result is joinedload

    def test_onetomany_without_subquery_returns_selectinload(self):
        rel = _make_relationship(RelationshipDirection.ONETOMANY)
        result = _relation_type_to_loader_func(rel)
        assert result is selectinload

    def test_manytomany_without_subquery_returns_selectinload(self):
        rel = _make_relationship(RelationshipDirection.MANYTOMANY)
        result = _relation_type_to_loader_func(rel)
        assert result is selectinload

    def test_onetomany_with_subquery_strategy_returns_subqueryload(self):
        subquery_strategy = MagicMock(spec=SubqueryLoader)
        rel = _make_relationship(RelationshipDirection.ONETOMANY, strategy=subquery_strategy)
        result = _relation_type_to_loader_func(rel)
        assert result is subqueryload

    def test_manytomany_with_subquery_strategy_returns_subqueryload(self):
        subquery_strategy = MagicMock(spec=SubqueryLoader)
        rel = _make_relationship(RelationshipDirection.MANYTOMANY, strategy=subquery_strategy)
        result = _relation_type_to_loader_func(rel)
        assert result is subqueryload

    def test_unrecognized_direction_raises_type_error(self):
        rel = MagicMock()
        rel.direction = MagicMock()  # Not a valid RelationshipDirection enum value
        # Force the match/case to fall through by giving a direction that won't match any case
        rel.direction.__eq__ = lambda self, other: False
        # We patch the match statement by using a sentinel object not in the enum
        rel.direction = object()  # Not an enum member → match falls through
        with pytest.raises(TypeError, match="Unrecognized relationship direction"):
            _relation_type_to_loader_func(rel)

    @pytest.mark.parametrize(
        "direction, strategy, expected_fn",
        [
            (RelationshipDirection.MANYTOONE, None, joinedload),
            (RelationshipDirection.ONETOMANY, None, selectinload),
            (RelationshipDirection.MANYTOMANY, None, selectinload),
        ],
        ids=["manytoone->joined", "onetomany->selectin", "manytomany->selectin"],
    )
    def test_parametrized_direction_mapping(self, direction, strategy, expected_fn):
        rel = _make_relationship(direction, strategy)
        result = _relation_type_to_loader_func(rel)
        assert result is expected_fn


class TestJoinAttrLoaders:
    def test_empty_list_returns_none(self):
        assert _join_attr_loaders([]) is None

    def test_single_loader_calls_loader_fn_with_attr(self):
        mock_attr = MagicMock(name="attr")
        mock_load_result = MagicMock(name="load_result")
        mock_loader_fn = MagicMock(name="loader_fn", return_value=mock_load_result)
        loader = _make_attr_loader(loader_fn=mock_loader_fn, attr=mock_attr)

        result = _join_attr_loaders([loader])

        mock_loader_fn.assert_called_once_with(mock_attr)
        assert result is mock_load_result

    def test_single_loader_returns_load_object(self):
        mock_load_result = MagicMock()
        loader = _make_attr_loader(loader_fn=MagicMock(return_value=mock_load_result))
        result = _join_attr_loaders([loader])
        assert result is mock_load_result

    def test_two_loaders_chains_second_onto_first(self):
        first_load = MagicMock(name="first_load")
        second_load = MagicMock(name="second_load")
        chained_load = MagicMock(name="chained_load")

        first_loader_fn = MagicMock(name="first_loader_fn", return_value=first_load)
        first_loader_fn.__name__ = "selectinload"

        second_loader_fn = MagicMock(name="second_loader_fn", return_value=second_load)
        second_loader_fn.__name__ = "joinedload"

        # When chaining: first_load.joinedload(second_attr) should be called
        first_load.joinedload = MagicMock(return_value=chained_load)

        second_attr = MagicMock(name="second_attr")
        loaders = [
            _make_attr_loader(loader_fn=first_loader_fn, attr=MagicMock()),
            _make_attr_loader(loader_fn=second_loader_fn, attr=second_attr),
        ]

        result = _join_attr_loaders(loaders)

        first_load.joinedload.assert_called_once_with(second_attr)
        assert result is chained_load

    def test_three_loaders_chains_all(self):
        """Verify the reduce logic chains three loaders correctly."""
        first_load = MagicMock(name="first_load")
        second_load = MagicMock(name="second_load")
        third_load = MagicMock(name="third_load")

        first_loader_fn = MagicMock(name="first_fn", return_value=first_load)
        first_loader_fn.__name__ = "selectinload"

        second_loader_fn = MagicMock(name="second_fn")
        second_loader_fn.__name__ = "joinedload"

        third_loader_fn = MagicMock(name="third_fn")
        third_loader_fn.__name__ = "selectinload"

        second_attr = MagicMock(name="second_attr")
        third_attr = MagicMock(name="third_attr")

        # first_load.joinedload(second_attr) -> second_load
        first_load.joinedload = MagicMock(return_value=second_load)
        # second_load.selectinload(third_attr) -> third_load
        second_load.selectinload = MagicMock(return_value=third_load)

        loaders = [
            _make_attr_loader(loader_fn=first_loader_fn, attr=MagicMock()),
            _make_attr_loader(loader_fn=second_loader_fn, attr=second_attr),
            _make_attr_loader(loader_fn=third_loader_fn, attr=third_attr),
        ]

        result = _join_attr_loaders(loaders)

        first_load.joinedload.assert_called_once_with(second_attr)
        second_load.selectinload.assert_called_once_with(third_attr)
        assert result is third_load

    def test_chaining_uses_loader_fn_name_for_getattr(self):
        """chain_loader_func uses getattr(final_loader, next.loader_fn.__name__) — verify the name is used."""
        first_load = MagicMock(name="first_load")
        first_loader_fn = MagicMock(return_value=first_load)
        first_loader_fn.__name__ = "selectinload"

        second_loader_fn = MagicMock()
        second_loader_fn.__name__ = "subqueryload"

        second_attr = MagicMock(name="second_attr")
        chained = MagicMock()
        first_load.subqueryload = MagicMock(return_value=chained)

        loaders = [
            _make_attr_loader(loader_fn=first_loader_fn, attr=MagicMock()),
            _make_attr_loader(loader_fn=second_loader_fn, attr=second_attr),
        ]

        result = _join_attr_loaders(loaders)

        first_load.subqueryload.assert_called_once_with(second_attr)
        assert result is chained


class TestAttrLoader:
    def test_attr_loader_is_named_tuple(self):
        fn = MagicMock()
        attr = MagicMock()
        model = MagicMock()
        loader = AttrLoader(loader_fn=fn, attr=attr, next_model=model)
        assert loader.loader_fn is fn
        assert loader.attr is attr
        assert loader.next_model is model

    def test_attr_loader_supports_unpacking(self):
        fn = MagicMock()
        attr = MagicMock()
        model = MagicMock()
        loader = AttrLoader(loader_fn=fn, attr=attr, next_model=model)
        unpacked_fn, unpacked_attr, unpacked_model = loader
        assert unpacked_fn is fn
        assert unpacked_attr is attr
        assert unpacked_model is model
