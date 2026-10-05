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

"""CLI of the workflow designer: `... workflow-designer scan-steps` and `... workflow-designer list-workflows`.

Both commands only read. Creating a designed workflow is left to the API, which validates the definition first.
"""

import json

import typer

app: typer.Typer = typer.Typer()


@app.command("scan-steps")
def scan_steps(
    as_json: bool = typer.Option(False, "--json", help="Print the full step descriptions as JSON, on one line"),
    usable_only: bool = typer.Option(False, "--usable-only", help="Leave out steps a designed workflow cannot use"),
    filter_text: str = typer.Option("", "--filter", help="Only steps whose id or name contains this text"),
) -> None:
    """Import all step packages and list the steps found, with their inputs and outputs."""
    from orchestrator.core.workflow_designer.discovery import discover_steps
    from orchestrator.core.workflow_designer.helper_steps import helper_step_infos

    needle = filter_text.lower()
    steps = [
        info
        for info in [*helper_step_infos().values(), *discover_steps().values()]
        if (info.usable or not usable_only) and (needle in info.id.lower() or needle in info.name.lower())
    ]
    if as_json:
        # One line, so it can be told apart from log output that may share stdout.
        typer.echo(json.dumps([info.model_dump(mode="json") for info in steps]))
        return

    for info in steps:
        inputs = ", ".join(f"{step_input.name}: {step_input.type.label}" for step_input in info.inputs) or "-"
        outputs = ", ".join(output.key for output in info.outputs if output.guaranteed) or "-"
        if not info.outputs_known:
            outputs += " (+ unknown)"
        status = "" if info.usable else f"  [unusable: {info.unusable_reason}]"
        typer.echo(f"{info.id}\n    {info.name}\n    in:  {inputs}\n    out: {outputs}{status}")
    typer.echo(f"\n{len(steps)} steps")


@app.command("list-workflows")
def list_designed_workflows() -> None:
    """List the designed workflows stored in the database."""
    from orchestrator.core.db import db
    from orchestrator.core.workflow_designer.service import list_workflows

    with db.database_scope():
        stored = list_workflows()
    for workflow in stored:
        steps = " >> ".join(step_ref.step_id.rpartition(":")[2] for step_ref in workflow.definition.steps)
        typer.echo(f"{workflow.definition.name} (v{workflow.version}, {workflow.process_count} processes): {steps}")
    typer.echo(f"\n{len(stored)} designed workflows")
