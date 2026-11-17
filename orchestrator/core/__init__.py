# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""This is the orchestrator workflow engine."""

from importlib.metadata import version

__version__: str = version("orchestrator-core")

# PEP 810 (Python 3.15+): listed modules become lazy automatically, so importing
# this package no longer pays the full app-stack cost at CLI startup.
# On Python <3.15, __lazy_modules__ is silently ignored by the interpreter; the
# __getattr__ below (PEP 562, supported since Python 3.7) provides equivalent
# deferred loading and is what actually eliminates the eager import cost on current
# Python versions.  Both mechanisms together keep CLI startup fast today and will
# stay correct after the 3.15 upgrade.
# PEP 810: https://peps.python.org/pep-0810/
# PEP 562: https://peps.python.org/pep-0562/
__lazy_modules__ = [
    "orchestrator.core.app",
    "orchestrator.core.settings",
    "orchestrator.core.workflow",
]


def __getattr__(name: str) -> object:
    """Defer heavy submodule imports until their attributes are first accessed.

    This is the active mechanism for Python <3.15.  It prevents ``orchestrator.core.app``
    (and the full FastAPI/Strawberry/SQLAlchemy stack it pulls in) from loading just
    because the CLI does ``import orchestrator.core``.

    See: https://peps.python.org/pep-0562/
    """
    if name in ("app_settings", "llm_settings"):
        from orchestrator.core.settings import app_settings, llm_settings

        globals()["app_settings"] = app_settings
        globals()["llm_settings"] = llm_settings
        return globals()[name]
    if name == "OrchestratorCore":
        from orchestrator.core.app import OrchestratorCore

        globals()["OrchestratorCore"] = OrchestratorCore
        return OrchestratorCore
    if name in ("begin", "conditional", "done", "focussteps", "inputstep", "retrystep", "step", "steplens", "workflow"):
        from orchestrator.core import workflow as _wf

        for attr in (
            "begin",
            "conditional",
            "done",
            "focussteps",
            "inputstep",
            "retrystep",
            "step",
            "steplens",
            "workflow",
        ):
            globals()[attr] = getattr(_wf, attr)
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "OrchestratorCore",
    "app_settings",
    "llm_settings",
    "step",
    "inputstep",
    "workflow",
    "retrystep",
    "begin",
    "done",
    "conditional",
    "focussteps",
    "steplens",
]
