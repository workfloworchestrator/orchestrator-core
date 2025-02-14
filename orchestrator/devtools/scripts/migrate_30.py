"""Helper script to rewrite import statements in your orchestrator.

Since types have been externalised in `pydantic_forms`, they were re-imported in `orchestrator.types` for backwards
compatibility. These import statements have been removed, and therefore need to be updated in orchestrator
implementations.
"""

import sys
from pathlib import Path

from orchestrator.devtools.scripts.shared import migrate, move_import


def migrate_file(f: Path) -> bool:
    imports = {
        "JSON": move_import(f, "JSON", "orchestrator.types", "pydantic_forms.types"),
        "AcceptData": move_import(f, "AcceptData", "orchestrator.types", "pydantic_forms.types"),
        "AcceptItemType": move_import(f, "AcceptItemType", "orchestrator.types", "pydantic_forms.types"),
        "FormGenerator": move_import(f, "FormGenerator", "orchestrator.types", "pydantic_forms.types"),
        "FormGeneratorAsync": move_import(f, "FormGeneratorAsync", "orchestrator.types", "pydantic_forms.types"),
        "InputForm": move_import(f, "InputForm", "orchestrator.types", "pydantic_forms.types"),
        "InputFormGenerator": move_import(f, "InputFormGenerator", "orchestrator.types", "pydantic_forms.types"),
        "InputStepFunc": move_import(f, "InputStepFunc", "orchestrator.types", "pydantic_forms.types"),
        "SimpleInputFormGenerator": move_import(
            f, "SimpleInputFormGenerator", "orchestrator.types", "pydantic_forms.types"
        ),
        "State": move_import(f, "State", "orchestrator.types", "pydantic_forms.types"),
        "StateInputFormGenerator": move_import(
            f, "StateInputFormGenerator", "orchestrator.types", "pydantic_forms.types"
        ),
        "StateInputFormGeneratorAsync": move_import(
            f, "StateInputFormGeneratorAsync", "orchestrator.types", "pydantic_forms.types"
        ),
        "StateInputStepFunc": move_import(f, "StateInputStepFunc", "orchestrator.types", "pydantic_forms.types"),
        "StateSimpleInputFormGenerator": move_import(
            f, "StateSimpleInputFormGenerator", "orchestrator.types", "pydantic_forms.types"
        ),
        "SubscriptionMapping": move_import(f, "SubscriptionMapping", "orchestrator.types", "pydantic_forms.types"),
        "SummaryData": move_import(f, "SummaryData", "orchestrator.types", "pydantic_forms.types"),
        "UUIDstr": move_import(f, "UUIDstr", "orchestrator.types", "pydantic_forms.types"),
        "strEnum": move_import(f, "strEnum", "orchestrator.types", "pydantic_forms.types"),
    }
    lines = []
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
