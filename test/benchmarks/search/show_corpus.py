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

"""Print a corpus as JSON, to see what the benchmark indexes.

    uv run python -m test.benchmarks.search.show_corpus --seed 2000 --size 20 --output corpus.json

The orchestrator logs to stdout on import, so write to a file with `--output` to get JSON only.
"""

import argparse
import json
from collections.abc import Sequence
from importlib import import_module
from pathlib import Path

from test.benchmarks.search.corpus import Corpus, Profile, build_corpus

DEFAULT_PROFILE = "test.benchmarks.search.profiles.generic:GenericProfile"
# The seed the benchmark runs with, so that the entities shown are the ones it indexes.
DEFAULT_SEED = 2000


def load_profile(path: str) -> Profile:
    """The profile class at `module:Class`, instantiated.

    Raises:
        ValueError: When `path` has no `:`.
    """
    module, separator, name = path.partition(":")
    if not separator:
        raise ValueError(f"Expected a profile as 'module:Class', got {path!r}")
    return getattr(import_module(module), name)()


def corpus_json(corpus: Corpus) -> str:
    """Every entity of `corpus`: its key, the facts queries are made from and the model that gets indexed."""
    entities = [
        {"key": entity.key, "facts": entity.facts, "model": entity.model.model_dump(mode="json")}
        for entity in corpus.entities
    ]
    return json.dumps({"profile": corpus.profile, "seed": corpus.seed, "entities": entities}, indent=2)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="the profile as module:Class")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--size", type=int, default=20, help="generated entities, on top of the anchors")
    parser.add_argument("--output", type=Path, help="write to this file instead of stdout")
    args = parser.parse_args(argv)

    text = corpus_json(build_corpus(load_profile(args.profile), args.seed, args.size))
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)  # noqa: T201


if __name__ == "__main__":
    main()
