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

# PEP 810 (Python 3.15+): these imports become lazy automatically.
# On <3.15 this variable is silently ignored; __getattr__ below handles deferral.
__lazy_modules__ = [
    "orchestrator.core.app",
    "orchestrator.core.settings",
    "orchestrator.core.workflow",
]


def __getattr__(name: str) -> object:
    """PEP 562 lazy attribute access (Python 3.11-3.14 fallback)."""
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
