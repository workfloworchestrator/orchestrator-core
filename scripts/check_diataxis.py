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
import sys
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.front_matter import front_matter_plugin

KINDS = {"tutorial", "how-to", "reference", "explanation", "mixed"}

VERBOSITY_ENV = "DIATAXIS_VERBOSITY"
DEFAULT_VERBOSITY = 1
MAX_VERBOSITY = 3

COMMENT_PREFIX = "<!--"
COMMENT_SUFFIX = "-->"
COMMENT_KEY = "diataxis:"

MARKDOWN = MarkdownIt("commonmark").use(front_matter_plugin)


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


def page_kind(tokens: list[Token]) -> str | None:
    r"""Return the `diataxis` value from the YAML front matter, '' if it's empty, or None if it's missing.

    >>> page_kind(MARKDOWN.parse("---\ndiataxis: how-to\nhide:\n  - toc\n---\n# Title\n"))
    'how-to'
    >>> page_kind(MARKDOWN.parse("---\n# tutorial | how-to\ndiataxis:\n---\n"))
    ''
    >>> page_kind(MARKDOWN.parse("# Title\n")) is None
    True
    >>> page_kind(MARKDOWN.parse("---\nhide: [toc\n---\n")) is None  # invalid YAML
    True
    """
    front_matter = next((token.content for token in tokens if token.type == "front_matter"), "")
    try:
        meta: Any = yaml.safe_load(front_matter)
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict) or "diataxis" not in meta:
        return None
    return "" if meta["diataxis"] is None else str(meta["diataxis"])


def section_kind(token: Token | None) -> str | None:
    r"""Return the kind from a `<!-- diataxis: ... -->` HTML block token, or None if it isn't one.

    >>> section_kind(MARKDOWN.parse("<!-- diataxis: tutorial -->\n")[0])
    'tutorial'
    >>> section_kind(MARKDOWN.parse("<!-- diataxis: -->\n")[0])
    ''
    >>> section_kind(MARKDOWN.parse("<!-- something else -->\n")[0]) is None
    True
    >>> section_kind(None) is None
    True
    """
    if token is None or token.type != "html_block":
        return None
    text = token.content.strip()
    if not (text.startswith(COMMENT_PREFIX) and text.endswith(COMMENT_SUFFIX)):
        return None
    body = text.removeprefix(COMMENT_PREFIX).removesuffix(COMMENT_SUFFIX).strip()
    return body.removeprefix(COMMENT_KEY).strip() if body.startswith(COMMENT_KEY) else None


def headings(tokens: list[Token]) -> list[tuple[int, str, str | None]]:
    r"""Return (line number, heading, section kind) for each top-level heading.

    Headings nested in blockquotes, lists or (CommonMark-indented) admonition and tab bodies belong to the enclosing
    section, so only headings at nesting level 0 count. The label must be on the line directly after the heading.

    >>> headings(MARKDOWN.parse("# A\n<!-- diataxis: tutorial -->\n\n## B\n"))
    [(1, '# A', 'tutorial'), (4, '## B', None)]
    >>> headings(MARKDOWN.parse("# A\n\n<!-- diataxis: tutorial -->\n"))  # not directly after the heading
    [(1, '# A', None)]
    >>> headings(MARKDOWN.parse("```\n# not a heading\n```\n> ## quoted\n"))
    []
    >>> headings(MARKDOWN.parse("Setext\n======\n<!-- diataxis: how-to -->\n"))
    [(1, '# Setext', 'how-to')]
    """
    return [
        (
            start + 1,
            f"{'#' * int(token.tag[1:])} {tokens[i + 1].content}",
            section_kind(label) if label is not None and label.map and label.map[0] == end else None,
        )
        for i, token in enumerate(tokens)
        if token.type == "heading_open" and token.level == 0 and token.map
        for start, end in [token.map]
        for label in [tokens[i + 3] if i + 3 < len(tokens) else None]
    ]


def check_file(path: Path) -> list[tuple[str, int | None, str]]:
    """Return (status, line number, heading) for the page label and every section label."""
    tokens = MARKDOWN.parse(path.read_text(encoding="utf-8"))
    return [(status(page_kind(tokens)), None, "")] + [
        (status(kind), lineno, heading) for lineno, heading, kind in headings(tokens)
    ]


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
