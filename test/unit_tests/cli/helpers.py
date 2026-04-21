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
