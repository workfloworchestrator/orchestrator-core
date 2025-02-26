"""Helper script to rewrite your orchestrator codebase for orchestrator-core 2.0.0.

Refer to the 2.0 migration guide documentation for background.
"""

import re
import sys
from pathlib import Path
from typing import Iterable

from orchestrator.devtools.scripts.shared import (
    find_and_remove_aliases,
    has_word,
    insert_import,
    migrate,
    move_import,
    remove_imports,
    replace_words,
)


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


def migrate_file(f: Path) -> bool:
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


if __name__ == "__main__":
    try:
        _target_dir = Path(sys.argv[1])
        assert _target_dir.is_dir()
    except Exception:
        print("Need a directory as parameter")
        sys.exit(1)

    sys.exit(0 if migrate(_target_dir, migrate_file) else 1)
