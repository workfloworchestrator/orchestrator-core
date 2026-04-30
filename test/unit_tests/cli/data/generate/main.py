from orchestrator.core import OrchestratorCore
from orchestrator.core.cli.main import app as core_cli
from orchestrator.core.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())
if __name__ == "__main__":
    core_cli()
