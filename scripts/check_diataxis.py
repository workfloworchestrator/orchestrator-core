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

The amount of output is controlled by the DIATAXIS_VERBOSITY environment variable:

    0   no output
    1   totals only (default)
    2   totals per file
    3   every page and section label
"""

import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

KINDS = {"tutorial", "how-to", "reference", "explanation", "mixed"}

VERBOSITY_ENV = "DIATAXIS_VERBOSITY"
DEFAULT_VERBOSITY = 1
MAX_VERBOSITY = 3

FRONT_MATTER_KEY = re.compile(r"^diataxis:\s*(?P<kind>\S*)\s*$")
HEADING = re.compile(r"^#{1,6}\s+\S")
SECTION_COMMENT = re.compile(r"^<!--\s*diataxis:\s*(?P<kind>.*?)\s*-->\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def status(kind: str | None) -> str:
    """Return a fixed-width OK/FAIL report for one label.

    >>> status("tutorial")
    'OK   (tutorial)'
    >>> status(None)
    'FAIL (missing)'
    >>> status("")
    'FAIL (empty)'
    >>> status("bogus")
    "FAIL (invalid: 'bogus')"
    """
    if kind is None:
        return "FAIL (missing)"
    if not kind:
        return "FAIL (empty)"
    if kind not in KINDS:
        return f"FAIL (invalid: {kind!r})"
    return f"OK   ({kind})"


def split_front_matter(lines: list[str]) -> tuple[list[str], int]:
    """Return the front matter lines and the index of the first body line.

    >>> split_front_matter(["---", "diataxis: how-to", "---", "# Title"])
    (['diataxis: how-to'], 3)
    >>> split_front_matter(["# Title"])
    ([], 0)
    >>> split_front_matter(["---", "diataxis: how-to"])  # unterminated front matter
    ([], 0)
    """
    if not lines or lines[0].strip() != "---":
        return [], 0
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    return (lines[1:end], end + 1) if end is not None else ([], 0)


def headings(lines: list[str], start: int) -> Iterator[tuple[int, str, str | None]]:
    """Yield (line number, heading, section kind) for each heading outside code fences.

    >>> list(headings(["# A", "<!-- diataxis: tutorial -->", "## B"], 0))
    [(1, '# A', 'tutorial'), (3, '## B', None)]
    >>> list(headings(["```", "# not a heading", "```"], 0))
    []
    """
    in_fence = False
    for i in range(start, len(lines)):
        line = lines[i]
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and HEADING.match(line):
            match = SECTION_COMMENT.match(lines[i + 1]) if i + 1 < len(lines) else None
            yield i + 1, line.strip(), match["kind"] if match else None


def check_file(path: Path) -> list[tuple[str, int | None, str]]:
    """Return (status, line number, heading) for the page label and every section label."""
    lines = path.read_text(encoding="utf-8").splitlines()
    front_matter, body_start = split_front_matter(lines)
    page_kind = next((m["kind"] for line in front_matter if (m := FRONT_MATTER_KEY.match(line))), None)

    results: list[tuple[str, int | None, str]] = [(status(page_kind), None, "")]
    for lineno, heading, kind in headings(lines, body_start):
        results.append((status(kind), lineno, heading))
    return results


def verbosity() -> int:
    """Read DIATAXIS_VERBOSITY, clamped to 0..MAX_VERBOSITY, falling back to DEFAULT_VERBOSITY."""
    raw = os.environ.get(VERBOSITY_ENV, "").strip()
    if not raw:
        return DEFAULT_VERBOSITY
    try:
        return max(0, min(MAX_VERBOSITY, int(raw)))
    except ValueError:
        print(f"{VERBOSITY_ENV}={raw!r} is not a number, using {DEFAULT_VERBOSITY}", file=sys.stderr)
        return DEFAULT_VERBOSITY


def main(argv: list[str]) -> int:
    level = verbosity()
    paths = [Path(arg) for arg in argv] or sorted(Path("docs").rglob("*.md"))
    reports = [(path, check_file(path)) for path in paths if path.suffix == ".md"]

    checked = sum(len(results) for _, results in reports)
    failed = sum(sum(result.startswith("FAIL") for result, _, _ in results) for _, results in reports)

    if level >= MAX_VERBOSITY:
        for path, results in reports:
            print(f"{results[0][0]:<30} {path}")
            for result, lineno, heading in results[1:]:
                print(f"  {result:<28} L{lineno:<5} {heading}")
    elif level == 2:
        for path, results in reports:
            file_failed = sum(result.startswith("FAIL") for result, _, _ in results)
            print(f"{len(results):>4} checked, {file_failed:>4} FAIL  {path}")

    if level >= 1:
        print(f"\n{len(reports)} pages, {checked} labels checked, {checked - failed} OK, {failed} FAIL")
        if level == 1:
            print(f"Set {VERBOSITY_ENV}=2 for per-file totals, {MAX_VERBOSITY} for every label, or 0 to silence.")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
