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

from pathlib import Path


def absolute_path(path: str) -> str:
    file = Path(__file__).resolve().parent / "data" / path
    return str(file)


def create_main():
    with open("main.py", "w") as fp:
        fp.write(
            "from orchestrator.core import OrchestratorCore\n"
            "from orchestrator.core.cli.main import app as core_cli\n"
            "from orchestrator.core.settings import AppSettings\n"
            "\n"
            "app = OrchestratorCore(base_settings=AppSettings())\n"
            'if __name__ == "__main__":\n'
            "    core_cli()\n"
        )
