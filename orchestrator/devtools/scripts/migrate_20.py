"""Helper script to rewrite your orchestrator codebase for orchestrator-core 2.0.0.

Refer to the 2.0 migration guide documentation for background.
"""

import re
import sys
from pathlib import Path
from subprocess import run
from typing import Iterable


def remove_imports(text: str, module: str, symbol: str) -> tuple[str, bool]:
    """Find imports and remove them.

    Assumes code is formatted through Black to keep the regex somewhat readable.
    """
    text_orig = text

    # single import from module (may have a #comment) -> remove line
    rgx = r"(from %s import \b%s\b(\s*#[^\n]*)*\n)" % (re.escape(module), symbol)
    text = re.sub(rgx, "", text)

    # middle or last of multiple imports from module -> strip symbol
    rgx = r"(from %s import .+)(, \b%s\b)" % (re.escape(module), symbol)
    text = re.sub(rgx, r"\1", text)

    # first of multiple imports from same module -> strip symbol
    rgx = r"(from %s import )\b%s\b, " % (re.escape(module), symbol)
    text = re.sub(rgx, r"\1", text)

    # multiline import -> remove line with symbol
    rgx_verbose = r"""(?P<before>^from\s%s\simport\s*\([^\n]*\n(?:^[^\n]+,\n)*)
                      (^\s*\b%s\b,[^\n]*\n)
                      (?P<after>(?:^[^\n]+,\n)*\)[^\n]*$)"""
    text = re.sub(rgx_verbose % (re.escape(module), symbol), r"\g<before>\g<after>", text, flags=re.M | re.X)
    return text, text_orig != text


def insert_import(text: str, import_stmt: str) -> str:
    # Find the first import line and add our line above that
    # Rely on ruff & black for formatting
    return re.sub(r"(^(?:from .+|import .+)$)", f"{import_stmt}\n" + r"\1", text, count=1, flags=re.M)


def find_and_remove_aliases(text: str, symbol: str) -> tuple[str, list[str]]:
    """In the given text find aliases of the given symbol and remove them.

    Return updated text and aliases removed.
    """
    rgx = r"(\b%s as (\w+))" % (symbol,)
    aliases = [aliasgroup for fullgroup, aliasgroup in re.findall(rgx, text)]
    newtext = re.sub(rgx, symbol, text)
    return newtext, aliases


def replace_words(text: str, words: list[str], replace: str) -> str:
    rgx = r"\b(%s)\b" % ("|".join(words),)
    return re.sub(rgx, replace, text)


def has_word(text: str, word: str) -> bool:
    return bool(re.search(r"\b%s\b" % (word,), text))


def rewrite_subscription_instance_lists(f: Path) -> list[str]:
    """Rewrite all SubscriptionInstanceList occurrences in a file and fix the imports.

    Refer to the "SubscriptionInstanceList" section in the 2.0 migration guide for details.

    Returns:
        names of any replaced SI Lists.
    """
    text = text_orig = f.read_text()
    sil = "SubscriptionInstanceList"
    if not has_word(text, sil):
        return []

    # Remove aliases in imports and in usages
    text, aliases = find_and_remove_aliases(text, sil)
    text = replace_words(text, aliases, sil) if aliases else text

    # Remove imports
    text, _changed = remove_imports(text, "orchestrator.domain.base", sil)

    # Replace SubscriptionInstanceList classes with types
    rgx = (
        r"^\s*class (?P<name>\w+)\([^)]*SubscriptionInstanceList\[(?P<type>(?:\w+|Union\[[\s\w,]+\]))\][^)]*\):\n"
        r"(?:^\s+min_items = (?P<min_items>(?:\w+|\d+))\n)*"
        r"(?:^\s+max_items = (?P<max_items>(?:\w+|\d+))\n)*"
    )

    def replace_si_list(match: re.Match) -> str:
        subscript_type = match.group("type")
        result = "\n%s = Annotated[list[%s], Len(%s)]\n"

        def len_params() -> Iterable[str]:
            if min_items := match.group("min_items"):
                yield f"min_length={min_items}"
            if max_items := match.group("max_items"):
                yield f"max_length={max_items}"

        return result % (match.group("name"), subscript_type, ", ".join(len_params()))

    names = [match[0] for match in re.findall(rgx, text, flags=re.M)]
    text = re.sub(rgx, replace_si_list, text, flags=re.M)

    symbols = {
        "Len": "from annotated_types import Len",
        "Annotated": "from typing import Annotated",
    }

    for symbol, import_stmt in symbols.items():
        if has_word(text_orig, symbol):
            # Assumes that if the symbol is already in the file, it was also imported
            continue
        if not has_word(text, symbol):
            # Not every symbol may be necessary
            continue
        text = insert_import(text, import_stmt)

    with f.open(mode="w"):
        f.write_text(text)
    return names


def move_import(f: Path, symbol: str, old_module: str, new_module: str) -> bool:
    text = f.read_text()
    text, changed = remove_imports(text, old_module, symbol)
    if not changed:
        return False
    text = insert_import(text, f"from {new_module} import {symbol}")
    with f.open(mode="w"):
        f.write_text(text)
    return True


re_serializable_property = re.compile(r"^(\s+)(@serializable_property)([^\n]*)\n", flags=re.MULTILINE)


def replace_serializable_props(f: Path) -> bool:
    """Replace @serializable_property with pydantic's @computed_field and updates imports.

    As an example, this changes:

      @serializable_property
      def title():
        ...

    To:

      @computed_field  # type: ignore[misc]
      @property
      def title():
        ...

    The type:ignore is recommended by pydantic to silence mypy; if you don't use mypy it's not needed.
    """
    text = f.read_text()
    text, changed = remove_imports(text, "orchestrator.domain.base", "serializable_property")
    if not changed:
        return False
    text = insert_import(text, "from pydantic import computed_field")
    text = re_serializable_property.sub(r"\1@computed_field  # type: ignore[misc]\3\1@property\n", text)
    with f.open(mode="w"):
        f.write_text(text)
    return True


def migrate_file(f: Path) -> int:
    imports = {
        "SI": move_import(f, "SI", "orchestrator.domain.base", "orchestrator.types"),
        "VlanRanges": move_import(f, "VlanRanges", "orchestrator.utils.vlans", "nwastdlib.vlans"),
        "ReadOnlyField_forms": move_import(f, "ReadOnlyField", "pydantic_forms.core", "pydantic_forms.validators"),
        "ReadOnlyField_core": move_import(f, "ReadOnlyField", "orchestrator.forms", "pydantic_forms.validators"),
        "pydantic BaseSettings": move_import(f, "BaseSettings", "pydantic", "pydantic_settings"),
    }
    lines = []
    if replaced_lists := ", ".join(rewrite_subscription_instance_lists(f)):
        lines.append(f"replaced subscription instance lists [{replaced_lists}]")
    if replace_serializable_props(f):
        lines.append("replaced serializable properties")
    lines.extend([f"Moved {k} import" for k, v in imports.items() if v])

    if lines:
        formatted_lines = "\n".join(f" - {line}" for line in lines)
        print(f"Updated {f.name:50s}\n{formatted_lines}")

    return bool(lines)


def run_tool(*args: str) -> bool:
    cmd = " ".join(args)
    try:
        r = run(args, capture_output=True)  # noqa: S603
        if r.returncode == 0:
            return True
        print(f"{cmd} failed:", r.stdout, r.stderr)
    except FileNotFoundError:
        print(f"{cmd }failed: could not find executable in the current venv")
    return False


def migrate(target_dir: Path) -> bool:
    abs_path = str(target_dir.resolve())

    def run_tools() -> bool:
        return run_tool("ruff", "--fix", abs_path) and run_tool("black", "--quiet", abs_path)

    print(f"\n### Verifing files in {abs_path}... ", end="")
    if not run_tools():
        print("Failed to verify files, aborting migration. Please resolve the errors.")
        return False
    print("Ok")

    files_migrated = files_checked = 0
    print(f"\n### Migrating files in {abs_path}")
    try:
        for f in target_dir.glob("**/*.py"):
            if migrate_file(f):
                files_migrated += 1
            files_checked += 1
    except KeyboardInterrupt:
        print("Interrupted...")

    print(f"\n### Migrated {files_migrated}/{files_checked} files in {abs_path}")

    print(f"\n### Formatting files in {abs_path}")
    return run_tools()


if __name__ == "__main__":
    try:
        _target_dir = Path(sys.argv[1])
        assert _target_dir.is_dir()
    except Exception:
        print("Need a directory as parameter")
        sys.exit(1)

    sys.exit(0 if migrate(_target_dir) else 1)
