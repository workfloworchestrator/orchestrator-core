from types import SimpleNamespace
from typing import cast

import orchestrator.cli.migrate_workflows as migrate_workflows
from orchestrator.workflows import LazyWorkflowInstance


def _state():
    return {"workflows_to_add": [], "workflows_to_delete": []}


def _workflows() -> dict[str, LazyWorkflowInstance]:
    return cast(dict[str, LazyWorkflowInstance], {"create_my_product": object()})


def _patch_add_workflow(monkeypatch, description: str) -> None:
    monkeypatch.setattr(
        migrate_workflows,
        "db",
        SimpleNamespace(session=SimpleNamespace(scalars=lambda _: ["my_product_type"])),
    )
    menu_choices = iter(["my_product_type", "create_my_product"])
    monkeypatch.setattr(migrate_workflows, "_prompt_user_menu", lambda *_args, **_kwargs: next(menu_choices))
    monkeypatch.setattr(
        migrate_workflows, "get_workflow", lambda _: SimpleNamespace(target=SimpleNamespace(value="CREATE"))
    )
    monkeypatch.setattr(migrate_workflows, "get_user_input", lambda *_args, **_kwargs: description)


def test_add_workflow_requires_description(monkeypatch):
    _patch_add_workflow(monkeypatch, description="")
    result = migrate_workflows._add_workflow(_workflows(), _state())
    assert result == _state()


def test_add_workflow_adds_description(monkeypatch):
    _patch_add_workflow(monkeypatch, description="Create my product")
    result = migrate_workflows._add_workflow(_workflows(), _state())
    assert result["workflows_to_add"] == [
        {
            "name": "create_my_product",
            "target": "CREATE",
            "description": "Create my product",
            "product_type": "my_product_type",
        }
    ]
