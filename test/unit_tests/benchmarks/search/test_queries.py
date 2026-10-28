# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import Category
from test.benchmarks.search.profiles.generic import GenericProfile
from test.benchmarks.search.queries import expand, load_handwritten


@pytest.fixture(scope="module")
def corpus():
    return build_corpus(GenericProfile(), 1, 0)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("plain", "plain"),
        ("{id:a}", "12345678-aaaa"),
        ("{id8:a}", "12345678"),
        ("x {id8:a} y {id:b}", "x 12345678 y 99999999-bbbb"),
    ],
)
def test_expand(text, expected):
    assert expand(text, {"a": "12345678-aaaa", "b": "99999999-bbbb"}) == expected


def test_expand_unknown_entity_raises():
    with pytest.raises(KeyError):
        expand("{id:zzz}", {})


def test_handwritten_queries_are_valid_for_the_generic_profile(corpus):
    queries = load_handwritten(corpus)

    assert len(queries) >= 25
    assert {Category.NEGATIVE, Category.IDENTIFIER, Category.TYPO} <= {query.category for query in queries}
    assert all(query.note for query in queries)


@pytest.mark.parametrize(
    "yaml_text,message",
    [
        ("- {query: x, category: exact, expected: [nope], note: n}", "unknown entities"),
        ("- {query: x, category: exact, expected: [ams001a-rt01]}", "needs a note"),
        ("- {query: x, category: bogus, note: n}", "bogus"),
    ],
)
def test_load_handwritten_rejects_bad_queries(corpus, tmp_path, yaml_text, message):
    path = tmp_path / "q.yaml"
    path.write_text(yaml_text)

    with pytest.raises(ValueError, match=message):
        load_handwritten(corpus, path)
