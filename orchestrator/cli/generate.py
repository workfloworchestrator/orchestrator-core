# Copyright 2019-2020 SURF.
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
import os
from pathlib import Path
from typing import Dict, Optional

import typer
import yaml
from jinja2 import Environment, FileSystemLoader

from orchestrator.cli.generator.generator.migration import generate_product_migration
from orchestrator.cli.generator.generator.product import generate_product
from orchestrator.cli.generator.generator.product_block import generate_product_blocks
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.cli.generator.generator.unittest import generate_unit_tests
from orchestrator.cli.generator.generator.workflow import generate_workflows

app: typer.Typer = typer.Typer()


def read_config(config_file: str) -> Optional[Dict]:
    try:
        with open(config_file) as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError:
                typer.echo("Failed to parse configuration file.")
    except FileNotFoundError:
        typer.echo(f'File "{config_file}" not found')

    return None


def write_file(path: str, content: str, append: bool, force: bool) -> None:
    typer.echo(path)
    try:
        if not force and os.path.exists(path):
            typer.echo(f"Path {path} already exists. Rerun with the --force flag if you want to overwrite")
            return

        mode = "a" if append else "w"
        with open(f"{path}", mode) as writer:
            writer.write(content)
    except FileNotFoundError:
        typer.echo(f"Writing to {path} failed")


def create_context(
    config_file: str, dryrun: bool, force: bool, python_version: str, tdd: Optional[bool] = False
) -> Dict:
    def writer(path: str, content: str, append: bool = False) -> None:
        if dryrun:
            typer.echo(path)
            typer.echo(content)
        else:
            write_file(path, content, append=append, force=force)

    environment = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "generator", "templates")), autoescape=True
    )

    config = read_config(config_file)

    return {
        "config": config,
        "environment": environment,
        "python_version": python_version,
        "tdd": tdd,
        "writer": writer,
    }


# Couple of shared parameters since Typer doesn't have an option to do this at the root level
# Discussion: https://github.com/tiangolo/typer/issues/153


ConfigFile = typer.Option(None, "--config-file", "-cf", help="The configuration file")
DryRun = typer.Option(True, help="Dry run")
TestDrivenDevelopment = typer.Option(True, "--tdd", help="Force test driven development with failing asserts")
Force = typer.Option(False, "--force", "-f", help="Force overwrite of existing files")
PythonVersion = typer.Option("3.9", "--python-version", "-p", help="Python version for generated code")
FolderPrefix = typer.Option("", "--folder-prefix", "-fp", help="Folder prefix, e.g. <folder-prefix>/workflows")


@app.command(help="Create product from configuration file")
def product(
    config_file: str = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    folder_prefix: Path = FolderPrefix,
) -> None:
    settings.FOLDER_PREFIX = folder_prefix
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version)

    generate_product(context)


@app.command(help="Create product blocks from configuration file")
def product_blocks(
    config_file: str = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    folder_prefix: Path = FolderPrefix,
) -> None:
    settings.FOLDER_PREFIX = folder_prefix
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version)

    generate_product_blocks(context)


@app.command(help="Create workflows from configuration file")
def workflows(
    config_file: str = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    tdd: bool = TestDrivenDevelopment,
    folder_prefix: Path = FolderPrefix,
) -> None:
    settings.FOLDER_PREFIX = folder_prefix
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version, tdd=tdd)

    generate_workflows(context)


@app.command(help="Create unit tests from configuration file")
def unit_tests(
    config_file: str = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    tdd: bool = TestDrivenDevelopment,
) -> None:
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version, tdd=tdd)

    generate_unit_tests(context)


@app.command(help="Create migration from configuration file")
def migration(
    config_file: str = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
) -> None:
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version)

    generate_product_migration(context)
