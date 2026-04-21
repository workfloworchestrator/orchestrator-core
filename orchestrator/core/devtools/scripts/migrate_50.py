"""Helper script to rewrite import statements in your orchestrator.

As the Orchestrator core has moved to a namespace packaging format, all import statements related to the orchestrator
must be modified.
"""

import re
import sys
from pathlib import Path

from orchestrator.core.devtools.scripts.shared import migrate


def migrate_file(f: Path) -> bool:
    """Replace all orchestrator module imports."""
    text = f.read_text()
    text_orig = text
    # First, we replace all "from orchestrator." with "from orchestrator.core."
    rgx = r"from orchestrator\.(.+)"
    text = re.sub(rgx, r"from orchestrator.core.\1", text)

    # Then, replace all "import orchestrator." with "import orchestrator.core."
    rgx = r"import orchestrator\.(.+)"
    text = re.sub(rgx, r"import orchestrator.core.\1", text)

    was_updated = text_orig != text
    if was_updated:
        print(f"Updated {f.name:50s}")
        with f.open(mode="w"):
            f.write_text(text)
    return was_updated


if __name__ == "__main__":
    try:
        _target_dir = Path(sys.argv[1])
        assert _target_dir.is_dir()
    except Exception:
        print("Need a directory as parameter")
        sys.exit(1)

    sys.exit(0 if migrate(_target_dir, migrate_file) else 1)
