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

import pytest

from orchestrator.core import begin, step
from orchestrator.core.beta.parallel import map_parallel, parallel
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.workflow import (
    Step,
    StepImportance,
    Success,
    callback_step,
    conditional,
    done,
    focussteps,
    init,
    make_step_function,
    step_group,
    workflow,
)
from pydantic_forms.core import FormPage
from pydantic_forms.types import FormGenerator, State


@step("Step A")
def _step_a() -> dict:
    return {"a": 1}


@step("Step B")
def _step_b() -> dict:
    return {"b": 2}


def test_steps_without_branching_have_no_branches() -> None:
    """A step that doesn't fan out has no branches and no sub steps."""
    assert _step_a.branching is None
    assert _step_a.sub_steps is None


# -- parallel group names are unique --


def test_duplicate_group_name_at_top_level_raises() -> None:
    """Two parallel blocks with the same name are rejected when the workflow is built."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Same group'\]"):

        @workflow()
        def duplicate_top_level_wf():
            return (
                init
                >> parallel("Same group", begin >> _step_a, begin >> _step_b)
                >> parallel("Same group", begin >> _step_a, begin >> _step_b)
                >> done
            )


def test_duplicate_group_name_nested_in_branch_raises() -> None:
    """A nested parallel block that reuses an outer group name is rejected."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Outer'\]"):

        @workflow()
        def duplicate_nested_wf():
            return (
                init
                >> parallel(
                    "Outer",
                    begin >> _step_a >> parallel("Outer", begin >> _step_a, begin >> _step_b),
                    begin >> _step_b,
                )
                >> done
            )


def test_duplicate_group_name_across_parallel_and_map_parallel_raises() -> None:
    """parallel() and map_parallel() share the group-name namespace of a workflow."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Shared name'\]"):

        @workflow()
        def duplicate_map_parallel_wf():
            return (
                init
                >> parallel("Shared name", begin >> _step_a, begin >> _step_b)
                >> map_parallel("Shared name", "items", begin >> _step_a)
                >> done
            )


def test_duplicate_group_name_inside_map_parallel_template_raises() -> None:
    """A duplicate inside a map_parallel template is found by walking the template."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Repeated'\]"):

        @workflow()
        def duplicate_in_template_wf():
            return (
                init
                >> map_parallel(
                    "Repeated",
                    "items",
                    begin >> parallel("Repeated", begin >> _step_a, begin >> _step_b),
                )
                >> done
            )


def test_duplicate_group_name_reported_once_per_name() -> None:
    """A name used three times is reported once, not once per extra occurrence."""
    with pytest.raises(ValueError, match=r"Duplicate parallel group name\(s\) \['Trio'\]"):

        @workflow()
        def triple_duplicate_wf():
            return (
                init
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> parallel("Trio", begin >> _step_a, begin >> _step_b)
                >> done
            )


# -- typed step metadata --


class _Form(FormPage):
    answer: int


def _form_generator(state: State) -> FormGenerator:
    """A form generator that yields ``_Form``, the shape ``make_step_function`` expects for ``form``."""
    user_input = yield _Form
    return user_input.model_dump()


async def _retry_allow(_context) -> bool:
    return True


async def _resume_allow(_context) -> bool:
    return True


def _step_attributes(step_fn: Step) -> tuple:
    """Everything a rewrap has to copy, in a form that compares by identity for the callables."""
    return (
        step_fn.name,
        step_fn.form,
        step_fn.assignee,
        step_fn.resume_auth_callback,
        step_fn.retry_auth_callback,
        step_fn.importance,
        step_fn.branching,
        step_fn.sub_steps,
        step_fn.is_callback_step,
    )


@pytest.mark.parametrize(
    "rewrap",
    [
        lambda step_fn: conditional(lambda _state: True)(step_fn)[0],
        lambda step_fn: focussteps("sub")(step_fn)[0],
    ],
    ids=["conditional", "focussteps"],
)
@pytest.mark.parametrize(
    "step_fn_factory",
    [
        pytest.param(
            lambda: make_step_function(
                lambda state: Success(state),
                "Plain",
                _form_generator,
                Assignee.NOC,
                resume_auth_callback=_resume_allow,
                retry_auth_callback=_retry_allow,
                importance=StepImportance.HIGH,
            ),
            id="plain-step",
        ),
        pytest.param(
            lambda: parallel("Wrapped group", begin >> _step_a, begin >> _step_b),
            id="parallel-step",
        ),
        pytest.param(
            lambda: map_parallel("Wrapped map", "items", begin >> _step_a),
            id="map-parallel-step",
        ),
        pytest.param(
            lambda: step_group("Wrapped group", begin >> _step_a),
            id="step-group",
        ),
    ],
)
def test_wrapping_a_step_copies_every_step_attribute(rewrap, step_fn_factory) -> None:
    """Conditional and steplens (and so focussteps) keep all Step attributes, including both auth callbacks."""
    step_fn = step_fn_factory()

    wrapped = rewrap(step_fn)

    assert _step_attributes(wrapped) == _step_attributes(step_fn)


def test_step_group_and_callback_step_expose_their_sub_steps() -> None:
    """step_group stores its steps on the Step, so the tree walk reaches them; callback_step is one too."""
    # given
    inner = begin >> _step_a

    # when
    group = step_group("Group", inner)
    cb = callback_step("Callback", action_step=_step_a, validate_step=_step_b)

    # then
    # The group's own Enter step and the given steps, followed by its Exit step.
    assert group.sub_steps is not None
    assert [s.name for s in group.sub_steps] == ["Group - Enter", "Step A", "Group - Exit"]
    assert group.branching is None
    assert not group.is_callback_step

    assert cb.is_callback_step
    assert cb.sub_steps is not None
    assert [s.name for s in cb.sub_steps] == [
        "Callback - Enter",
        "Callback - Create endpoint",
        "Step A",
        "Callback - Await callback",
        "Step B",
        "Callback - Cleanup callback step",
        "Callback - Exit",
    ]


def test_focussteps_keeps_the_retry_auth_callback() -> None:
    """Focussteps zooms its input state, but the step it represents keeps its authorization callbacks."""
    step_fn = make_step_function(
        lambda state: Success(state),
        "Authorized",
        retry_auth_callback=_retry_allow,
        resume_auth_callback=_resume_allow,
    )

    wrapped = focussteps("sub")(step_fn)[0]

    assert wrapped.retry_auth_callback is _retry_allow
    assert wrapped.resume_auth_callback is _resume_allow
