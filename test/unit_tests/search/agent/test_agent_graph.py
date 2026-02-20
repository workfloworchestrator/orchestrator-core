from orchestrator.search.agent.planner import Planner
from orchestrator.search.agent.skill_runner import SkillRunner
from orchestrator.search.agent.skills import SKILLS


def test_planner_creation():
    """Test that Planner can be created."""
    planner = Planner(model="openai:gpt-4", skills=SKILLS, debug=False)
    assert planner.model == "openai:gpt-4"
    assert planner.skills == SKILLS


def test_skill_runner_creation():
    """Test that SkillRunner can be created for each skill."""
    for _action, skill in SKILLS.items():
        runner = SkillRunner(skill=skill, model="openai:gpt-4", debug=False)
        assert runner.skill == skill
        assert runner.model == "openai:gpt-4"
