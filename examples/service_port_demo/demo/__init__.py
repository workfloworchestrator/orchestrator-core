from orchestrator import OrchestratorCore


def load_demo(app: OrchestratorCore) -> None:
    print("LOADING DEMO...")
    import demo.products
    import demo.workflows
