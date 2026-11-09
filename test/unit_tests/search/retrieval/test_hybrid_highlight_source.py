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

import pytest
from sqlalchemy import String, create_engine, func, literal, select

from orchestrator.core.search.retrieval.retrievers.hybrid import highlight_source_sql

_engine = create_engine("sqlite://")


def _evaluate(
    fuzzy_text: str | None, semantic_text: str | None, *, with_semantic: bool = True
) -> tuple[str | None, str | None]:
    """Return the (source, coalesced text) pair for the fuzzy and semantic highlight texts.

    ``with_semantic=False`` mirrors the retriever's single-source branch, where there is no semantic side.
    """
    fuzzy = literal(fuzzy_text, String)
    if with_semantic:
        semantic = literal(semantic_text, String)
        stmt = select(highlight_source_sql(fuzzy, semantic), func.coalesce(fuzzy, semantic))
    else:
        stmt = select(highlight_source_sql(fuzzy, None), fuzzy)
    with _engine.connect() as conn:
        source, text = conn.execute(stmt).one()
    return source, text


@pytest.mark.parametrize(
    "fuzzy_text,semantic_text,expected_source,expected_text",
    [
        pytest.param("UNIMAAS", "other", "fuzzy", "UNIMAAS", id="both-have-text-fuzzy-wins"),
        pytest.param("", "other", "fuzzy", "", id="empty-fuzzy-text-is-not-null"),
        pytest.param(None, "other", "semantic", "other", id="fuzzy-null-falls-back-to-semantic"),
        pytest.param(None, None, None, None, id="neither-has-text"),
    ],
)
def test_highlight_source_follows_coalesce(fuzzy_text, semantic_text, expected_source, expected_text):
    source, text = _evaluate(fuzzy_text, semantic_text)
    assert (source, text) == (expected_source, expected_text)


@pytest.mark.parametrize(
    "fuzzy_text,expected_source,expected_text",
    [
        pytest.param("UNIMAAS", "fuzzy", "UNIMAAS", id="fuzzy-text"),
        pytest.param(None, None, None, id="no-fuzzy-text"),
    ],
)
def test_highlight_source_without_semantic_source(fuzzy_text, expected_source, expected_text):
    source, text = _evaluate(fuzzy_text, None, with_semantic=False)
    assert (source, text) == (expected_source, expected_text)
