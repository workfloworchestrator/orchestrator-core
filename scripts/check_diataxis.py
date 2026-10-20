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

"""Report the Diátaxis classification of every docs page and section.

Prints OK/FAIL for the `diataxis:` front matter key of each page and for the `<!-- diataxis: ... -->` comment that
should follow each Markdown heading. See the Diátaxis section in CLAUDE.md for the conventions.

Always exits 0 for now: it reports progress, it doesn't enforce.

Usage: python scripts/check_diataxis.py [FILE ...]   (defaults to all of docs/**/*.md)
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path

KINDS = {"tutorial", "how-to", "reference", "explanation", "mixed"}

FRONT_MATTER_KEY = re.compile(r"^diataxis:\s*(?P<kind>\S*)\s*$")
HEADING = re.compile(r"^#{1,6}\s+\S")
SECTION_COMMENT = re.compile(r"^<!--\s*diataxis:\s*(?P<kind>.*?)\s*-->\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def status(kind: str | None) -> str:
    if kind is None:
        return "FAIL (missing)"
    if not kind:
        return "FAIL (empty)"
    if kind not in KINDS:
        return f"FAIL (invalid: {kind!r})"
    return f"OK   ({kind})"


def split_front_matter(lines: list[str]) -> tuple[list[str], int]:
    """Return the front matter lines and the index of the first body line."""
    if not lines or lines[0].strip() != "---":
        return [], 0
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    return (lines[1:end], end + 1) if end is not None else ([], 0)


def headings(lines: list[str], start: int) -> Iterator[tuple[int, str, str | None]]:
    """Yield (line number, heading, section kind) for each heading outside code fences."""
    in_fence = False
    for i in range(start, len(lines)):
        line = lines[i]
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and HEADING.match(line):
            match = SECTION_COMMENT.match(lines[i + 1]) if i + 1 < len(lines) else None
            yield i + 1, line.strip(), match["kind"] if match else None


def check_file(path: Path) -> tuple[int, int]:
    """Print the report for one file and return (checked, failed) counts."""
    lines = path.read_text(encoding="utf-8").splitlines()
    front_matter, body_start = split_front_matter(lines)
    page_kind = next((m["kind"] for line in front_matter if (m := FRONT_MATTER_KEY.match(line))), None)

    results = [status(page_kind)]
    print(f"{results[0]:<30} {path}")
    for lineno, heading, kind in headings(lines, body_start):
        results.append(status(kind))
        print(f"  {results[-1]:<28} L{lineno:<5} {heading}")

    return len(results), sum(result.startswith("FAIL") for result in results)


def main(argv: list[str]) -> int:
    paths = [Path(arg) for arg in argv] or sorted(Path("docs").rglob("*.md"))
    counts = [check_file(path) for path in paths if path.suffix == ".md"]
    checked, failed = sum(c for c, _ in counts), sum(f for _, f in counts)
    print(f"\n{len(counts)} pages, {checked} labels checked, {checked - failed} OK, {failed} FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
