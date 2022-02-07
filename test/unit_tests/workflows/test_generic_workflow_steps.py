from orchestrator.config.assignee import Assignee
from orchestrator.forms import FormPage
from orchestrator.utils.functional import orig
from orchestrator.workflow import begin, done, inputstep, step, workflow
from orchestrator.workflows.steps import unsync
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_suspended,
    resume_workflow,
    run_workflow,
)


def test_resume_workflow():
    @step("Test step 1")
    def fakestep1():
        return {"steden": ["Utrecht"], "stad": "Amsterdam"}

    @inputstep("Wait for me step 2", assignee=Assignee.SYSTEM)
    def waitforme(steden, stad):
        class WaitForm(FormPage):
            stad: str

        user_input = yield WaitForm
        meer = [*steden, stad]
        return {**user_input.dict(), "steden": meer}

    @step("Test step 3")
    def fakestep3(steden):
        meer = [*steden, "Leiden"]
        return {"steden": meer}

    @workflow("Test wf", target="Target.CREATE")
    def testwf():
        return begin >> fakestep1 >> waitforme >> fakestep3 >> done

    with WorkflowInstanceForTests(testwf, "testwf"):
        # The process and step_log from run_workflow can be used to resume it with resume_workflow
        result, process, step_log = run_workflow("testwf", {})
        assert_suspended(result)
        result, step_log = resume_workflow(process, step_log, {"stad": "Maastricht"})
        assert_complete(result)


def test_unsync(generic_subscription_1):
    result = orig(unsync)(generic_subscription_1)
    # Test is backup is available
    assert result["__old_subscriptions__"][generic_subscription_1]["description"] == "Generic Subscription One"
    assert result["__old_subscriptions__"][generic_subscription_1]["insync"] is True
    # Test if subscription will be set to insync = False:
    assert result["subscription"].insync is False
