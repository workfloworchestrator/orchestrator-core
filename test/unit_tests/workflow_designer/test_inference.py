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

from orchestrator.core.workflow_designer.inference import infer_outputs
from orchestrator.core.workflow_designer.type_refs import TypeRef
from pydantic_forms.types import State


def literal_keys(zone: str) -> State:
    record = "automation"
    count: int = compute()
    return {"zone": zone, "record": record, "count": count, "ok": zone == "x", "label": f"{zone}!", "__hidden": 1}


def compute() -> int:
    return 1


def branches(flag: bool) -> State:
    if flag:
        return {"a": 1, "b": "x"}
    return {"a": 2}


def falls_off_end(flag: bool) -> State:  # type: ignore[return]  # noqa: RET503 - the implicit None return is tested
    if flag:
        return {"a": 1}


def always_raises_otherwise(flag: bool) -> State:
    if flag:
        return {"a": 1}
    raise ValueError("no")


def nested_function_returns_are_ignored() -> State:
    def helper():
        return {"not_mine": 1}

    return {"mine": helper()}


def spread(state: State) -> State:
    return {**state, "extra": True}


def dynamic() -> State:
    result = {"a": 1}
    return result  # noqa: RET504 - returning a variable instead of a literal is what is being tested


def returns_nothing() -> None:
    compute()


@pytest.mark.parametrize(
    ("func", "expected", "known"),
    [
        pytest.param(
            literal_keys,
            {
                "zone": (TypeRef(kind="str"), True),
                "record": (TypeRef(kind="str"), True),
                "count": (TypeRef(kind="int"), True),
                "ok": (TypeRef(kind="bool"), True),
                "label": (TypeRef(kind="str"), True),
            },
            True,
            id="literal-keys-and-value-types",
        ),
        pytest.param(
            branches,
            {"a": (TypeRef(kind="int"), True), "b": (TypeRef(kind="str"), False)},
            True,
            id="intersection-of-branches",
        ),
        pytest.param(falls_off_end, {"a": (TypeRef(kind="int"), False)}, True, id="implicit-none-return"),
        pytest.param(always_raises_otherwise, {"a": (TypeRef(kind="int"), True)}, True, id="raise-is-not-a-return"),
        pytest.param(nested_function_returns_are_ignored, {"mine": (TypeRef(), True)}, True, id="nested-def"),
        pytest.param(spread, {"extra": (TypeRef(kind="bool"), True)}, False, id="spread-is-unknown"),
        pytest.param(dynamic, {}, False, id="returned-variable-is-unknown"),
        pytest.param(returns_nothing, {}, True, id="no-return"),
    ],
)
def test_infer_outputs(func, expected, known):
    params = {"zone": TypeRef(kind="str"), "flag": TypeRef(kind="bool")}

    inference = infer_outputs(func, params)

    assert {output.key: (output.type, output.guaranteed) for output in inference.outputs} == expected
    assert inference.known is known
