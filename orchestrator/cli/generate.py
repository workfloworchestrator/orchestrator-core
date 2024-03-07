# Copyright 2019-2020 SURF, ESnet.
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

# ruff: noqa: S603
import subprocess
from pathlib import Path

import structlog
import typer
import yaml
from jinja2 import Environment, FileSystemLoader

from orchestrator.cli.generator.generator.helpers import get_variable
from orchestrator.cli.generator.generator.migration import generate_product_migration
from orchestrator.cli.generator.generator.product import generate_product
from orchestrator.cli.generator.generator.product_block import generate_product_blocks
from orchestrator.cli.generator.generator.settings import product_generator_settings as settings
from orchestrator.cli.generator.generator.unittest import generate_unit_tests
from orchestrator.cli.generator.generator.workflow import generate_workflows

logger = structlog.getLogger(__name__)

app: typer.Typer = typer.Typer()


def read_config(config_file: Path) -> dict:
    try:
        with open(config_file) as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exception:
                logger.error("failed to parse configuration file", config_file=str(config_file))
                raise exception
    except FileNotFoundError as exception:
        logger.error("configuration file not found", config_file=str(config_file))
        raise exception


def write_file(path: Path, content: str, append: bool, force: bool) -> None:
    try:
        if not path.parent.exists():
            logger.info("creating missing folder(s)", path=str(path.parent))
            path.parent.mkdir(parents=True, exist_ok=True)
        if not force and path.exists():
            action = "append" if append else "overwrite"
            logger.warning(f"file already exists, rerun with --force if you want to {action}", path=str(path))
            return

        mode = "a" if append else "w"
        with open(path, mode) as writer:
            writer.write(content)
    except Exception as exception:
        logger.error("failed to write file", path=str(path), message=str(exception))
    else:
        logger.info("wrote file", path=str(path), append=append, force=force)


def ruff(content: str) -> str:
    ruff_check = ["ruff", "check", "--isolated", "--line-length", "120", "--select", "ALL", "--fix-only", "-"]
    ruff_format = ["ruff", "format", "--isolated", "--line-length", "120", "-"]
    try:
        process = subprocess.run(ruff_check, capture_output=True, check=True, text=True, input=content)
        process = subprocess.run(ruff_format, capture_output=True, check=True, text=True, input=process.stdout)
    except subprocess.CalledProcessError as exc:
        logger.warning("ruff error", cmd=exc.cmd, returncode=exc.returncode, stderr=exc.stderr)
    else:
        content = process.stdout
    return content


def create_context(config_file: Path, dryrun: bool, force: bool, python_version: str, tdd: bool | None = False) -> dict:
    def writer(path: Path, content: str, append: bool = False) -> None:
        content = ruff(content) if path.suffix == ".py" else content
        if dryrun:
            logger.info("preview file", path=str(path), append=append, force=force, dryrun=dryrun)
            typer.echo(f"# {path}")
            typer.echo(content)
        else:
            write_file(path, content, append=append, force=force)

    search_path = (settings.CUSTOM_TEMPLATES, Path(__file__).parent / "generator" / "templates")
    environment = Environment(loader=FileSystemLoader(search_path), autoescape=True, keep_trailing_newline=True)

    config = read_config(config_file)
    config["variable"] = get_variable(config)
    for pb in config["product_blocks"]:
        pb["variable"] = get_variable(pb)

    return {
        "config": config,
        "environment": environment,
        "python_version": python_version,
        "tdd": tdd,
        "writer": writer,
    }


# Couple of shared parameters since Typer doesn't have an option to do this at the root level
# Discussion: https://github.com/tiangolo/typer/issues/153


ConfigFile = typer.Option(..., "--config-file", "-cf", help="The configuration file")
DryRun = typer.Option(True, help="Dry run")
TestDrivenDevelopment = typer.Option(True, "--tdd", help="Force test driven development with failing asserts")
Force = typer.Option(False, "--force", "-f", help="Force overwrite of existing files")
PythonVersion = typer.Option("3.11", "--python-version", "-p", help="Python version for generated code")
FolderPrefix = typer.Option("", "--folder-prefix", "-fp", help="Folder prefix, e.g. <folder-prefix>/workflows")
CustomTemplates = typer.Option("", "--custom-templates", "-ct", help="Custom templates folder")


@app.command(help="Create product from configuration file")
def product(
    config_file: Path = ConfigFile,
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
    config_file: Path = ConfigFile,
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
    config_file: Path = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    tdd: bool = TestDrivenDevelopment,
    folder_prefix: Path = FolderPrefix,
    custom_templates: Path = CustomTemplates,
) -> None:
    settings.FOLDER_PREFIX = folder_prefix
    settings.CUSTOM_TEMPLATES = custom_templates
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version, tdd=tdd)

    generate_workflows(context)


@app.command(help="Create unit tests from configuration file")
def unit_tests(
    config_file: Path = ConfigFile,
    dryrun: bool = DryRun,
    force: bool = Force,
    python_version: str = PythonVersion,
    tdd: bool = TestDrivenDevelopment,
) -> None:
    context = create_context(config_file, dryrun=dryrun, force=force, python_version=python_version, tdd=tdd)

    generate_unit_tests(context)


@app.command(help="Create migration from configuration file")
def migration(
    config_file: Path = ConfigFile,
    python_version: str = PythonVersion,
) -> None:
    context = create_context(config_file, dryrun=False, force=True, python_version=python_version)

    generate_product_migration(context)
