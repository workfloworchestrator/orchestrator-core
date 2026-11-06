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

"""The committed snapshots of the benchmark's corpus and generated queries, and how they are rendered."""

import pytest
from inline_snapshot import external_file

from test.benchmarks.search.corpus import build_corpus
from test.benchmarks.search.perturb import Category, LabelledQuery, generate_queries
from test.benchmarks.search.profiles.network_services import NetworkServicesProfile
from test.benchmarks.search.settings import BASELINE, CORPUS_SIZE, GENERATED_PER_CATEGORY, SEED
from test.benchmarks.search.snapshot import SHOWN_EXPECTED, render_corpus, render_queries


@pytest.fixture(scope="module")
def corpus():
    return build_corpus(NetworkServicesProfile(), SEED, CORPUS_SIZE)


def _description(corpus):
    return f"The `{corpus.profile}` profile with random seed {corpus.seed}: {len(corpus.entities)} entities."


def test_corpus_is_unchanged(corpus):
    assert render_corpus(corpus, _description(corpus)) == external_file(BASELINE / "corpus.md", format=".txt")


def test_generated_queries_are_unchanged(corpus):
    queries = generate_queries(corpus, GENERATED_PER_CATEGORY, SEED)
    page = render_queries(queries, _description(corpus))
    assert page == external_file(BASELINE / "generated_queries.md", format=".txt")


def _cells(line):
    """The cells of a rendered table row, without their padding."""
    return [cell.strip() for cell in line.removeprefix("| ").removesuffix(" |").split(" | ")]


# The cases the snapshots do not cover: no value in the corpus has a pipe, and no query expects exactly as many
# entities as are shown.
@pytest.mark.parametrize(
    "expected,cells",
    [
        pytest.param(("a|b",), ["1", "a\\|b"], id="pipe escaped"),
        pytest.param(
            tuple(f"k{i}" for i in range(SHOWN_EXPECTED)),
            [str(SHOWN_EXPECTED), ", ".join(f"k{i}" for i in range(SHOWN_EXPECTED))],
            id="exactly shown",
        ),
    ],
)
def test_render_queries_row(expected, cells):
    page = render_queries([LabelledQuery("q", Category.EXACT, expected)], "")

    assert _cells(page.splitlines()[-1]) == ["exact", "`q`", *cells]
