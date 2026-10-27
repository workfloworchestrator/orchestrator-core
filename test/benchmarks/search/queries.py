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

"""Hand-written queries, kept in YAML next to this file: the intended ranking behaviour, written down."""

import re
from collections.abc import Mapping
from pathlib import Path

import yaml

from test.benchmarks.search.corpus import Corpus
from test.benchmarks.search.perturb import Category, LabelledQuery

HANDWRITTEN = Path(__file__).parent / "queries" / "handwritten.yaml"

# `{id:KEY}` is the entity's full id, `{id8:KEY}` its first 8 characters: ids are derived, so they cannot be written out.
PLACEHOLDER = re.compile(r"\{(id|id8):([^}]+)\}")


def expand(text: str, ids: Mapping[str, str]) -> str:
    """`text` with its id placeholders filled from `ids`, which maps entity keys to ids.

    Raises:
        KeyError: When a placeholder names an unknown entity.
    """

    def fill(match: re.Match[str]) -> str:
        kind, key = match.groups()
        return ids[key] if kind == "id" else ids[key][:8]

    return PLACEHOLDER.sub(fill, text)


def load_handwritten(corpus: Corpus, path: Path = HANDWRITTEN) -> list[LabelledQuery]:
    """The hand-written queries, with placeholders filled.

    Raises:
        ValueError: When a query expects an entity that the corpus does not hold, or has no note.
    """
    by_key = corpus.by_key
    ids = {key: str(entity.entity_id) for key, entity in by_key.items()}
    queries = [
        LabelledQuery(
            text=expand(raw["query"], ids),
            category=Category(raw["category"]),
            expected=tuple(raw.get("expected", [])),
            note=raw.get("note", ""),
        )
        for raw in yaml.safe_load(path.read_text())
    ]
    for query in queries:
        if unknown := set(query.expected) - by_key.keys():
            raise ValueError(f"Query {query.text!r} expects unknown entities {sorted(unknown)}")
        if not query.note:
            raise ValueError(f"Query {query.text!r} needs a note on the intended behaviour")
    return queries
