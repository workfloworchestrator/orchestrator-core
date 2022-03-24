from orchestrator import OrchestratorCore


def load_demo(app: OrchestratorCore) -> None:
    import demo.products
    import demo.workflows
