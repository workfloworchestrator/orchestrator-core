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
from typing import Dict, Optional

import typer
import yaml
from jinja2 import Environment, FileSystemLoader

from orchestrator.cli.generator.generator.product import generate_product

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


@app.command(help="Create product from configuration file")
def product(
    config_file: str = typer.Argument(None, help="The configuration file"),
    dryrun: bool = typer.Option(True, help="Dry run"),
    force: bool = typer.Option(False, help="Force overwrite of existing files"),
    python_version: str = typer.Option("3.9", "--python-version", "-p", help="Python version for generated code"),
) -> None:
    def writer(path: str, content: str, append: bool = False) -> None:
        if dryrun:
            typer.echo(path)
            typer.echo(content)
        else:
            write_file(path, content, append=append, force=force)

    environment = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "generator", "templates")), autoescape=True
    )

    context = {
        "config": read_config(config_file),
        "environment": environment,
        "writer": writer,
    }

    generate_product(context)


@app.command(help="Create product blocks from configuration file")
def product_blocks() -> None:
    pass


@app.command(help="Create workflows from configuration file")
def workflows() -> None:
    pass


@app.command(help="Create unit tests from configuration file")
def unit_tests() -> None:
    pass
