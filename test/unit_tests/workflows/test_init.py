import pytest

from orchestrator.workflows import ALL_WORKFLOWS, LazyWorkflowInstance, get_workflow


@pytest.fixture(autouse=True)
def _clean_all_workflows():
    """Snapshot and restore ALL_WORKFLOWS to prevent global state leaks."""
    original = ALL_WORKFLOWS.copy()
    yield
    ALL_WORKFLOWS.clear()
    ALL_WORKFLOWS.update(original)


class TestLazyWorkflowInstance:
    def test_relative_module_not_found(self):
        lwi = LazyWorkflowInstance(".nonexistent_module_xyz", "some_fn")
        with pytest.raises(ValueError, match="does not exist or has invalid imports"):
            lwi.instantiate()

    def test_absolute_module_not_found(self):
        lwi = LazyWorkflowInstance("fake.nonexistent.module.xyz", "some_fn")
        with pytest.raises(ValueError, match="does not exist or has invalid imports"):
            lwi.instantiate()

    def test_str(self):
        lwi = LazyWorkflowInstance(".some_pkg", "some_fn_str")
        assert str(lwi) == ".some_pkg.some_fn_str"

    def test_repr(self):
        lwi = LazyWorkflowInstance(".some_pkg", "some_fn_repr")
        assert repr(lwi) == "LazyWorkflowInstance('.some_pkg','some_fn_repr')"


class TestGetWorkflow:
    def test_not_found_returns_none(self):
        result = get_workflow("nonexistent_workflow_xyz_12345")
        assert result is None
