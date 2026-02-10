# type: ignore

from uuid import UUID, uuid4

import pytest

from nwastdlib import const
from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.state import extract, form_inject_args, inject_args
from pydantic_forms.core import FormPage, post_form
from pydantic_forms.types import State

STATE = {"one": 1, "two": 2, "three": 3, "four": 4}


def test_extract():
    one, two, three, four = extract(("one", "two", "three", "four"), STATE)
    assert one == 1
    assert two == 2
    assert three == 3
    assert four == 4

    four, three, two, one = extract(("four", "three", "two", "one"), STATE)
    assert one == 1
    assert two == 2
    assert three == 3
    assert four == 4

    nothing = extract((), STATE)
    assert len(nothing) == 0


def test_extract_key_error():
    key = "I don't exist"
    with pytest.raises(KeyError) as excinfo:
        extract((key,), STATE)
        assert key in excinfo.value.args


def test_state() -> None:
    @inject_args
    def step_func_ok(one):
        assert one == STATE["one"]
        return {"prefix_id": 42}

    new_state = step_func_ok(STATE)
    assert "prefix_id" in new_state
    assert new_state["prefix_id"] == 42

    @inject_args
    def step_func_fail(i_am_not_in_the_state):
        return {}

    with pytest.raises(KeyError):
        step_func_fail(STATE)

    @inject_args
    def step_func_opt_arg(opt: str | None = None) -> None:
        assert opt is None

    step_func_opt_arg(STATE)

    @inject_args
    def step_func_default(default="bla"):
        assert default == "bla"

    step_func_default(STATE)

    step_func_const = inject_args(const({}))
    step_func_const(STATE)

    @inject_args
    def step_func_state(state, one):
        assert state == STATE
        assert one == STATE["one"]

    step_func_state(STATE)

    @inject_args
    def step_func_empty():
        pass

    step_func_state(STATE)


def test_inject_args(generic_product_1, generic_product_type_1) -> None:
    GenericProductOneInactive, GenericProduct = generic_product_type_1
    product_id = generic_product_1.product_id
    state = {"product": product_id, "customer_id": str(uuid4())}
    generic_sub = GenericProductOneInactive.from_product_id(
        product_id=state["product"], customer_id=state["customer_id"], status=SubscriptionLifecycle.INITIAL
    )
    generic_sub.pb_1.rt_1 = "test"
    generic_sub.pb_2.rt_2 = 42
    generic_sub.pb_2.rt_3 = "test2"

    generic_sub = SubscriptionModel.from_other_lifecycle(generic_sub, SubscriptionLifecycle.ACTIVE)

    generic_sub.save()

    @inject_args
    def step_existing(generic_sub: GenericProduct) -> State:
        assert generic_sub.subscription_id
        assert generic_sub.pb_1.rt_1 == "test"
        generic_sub.pb_1.rt_1 = "test string"
        return {"generic_sub": generic_sub}

    # Put `generic_sub` as an UUID in. Entire `generic_sub` object would have worked as well, but this way we will be
    # certain that if we end up with an entire `generic_sub` object in the step function, it will have been retrieved
    # from the database.
    state["generic_sub"] = generic_sub.subscription_id

    state_amended = step_existing(state)
    assert "generic_sub" in state_amended

    # Do we now have an entire object instead of merely a UUID
    assert isinstance(state_amended["generic_sub"], GenericProduct)

    # And does it have the modifcations from the step functions
    assert state_amended["generic_sub"].pb_1.rt_1 == "test string"

    # Test `rt_1` has been persisted to the database with the modifications from the step function.`
    fresh_generic_sub = GenericProduct.from_subscription(state_amended["generic_sub"].subscription_id)
    assert fresh_generic_sub.pb_1.rt_1 is not None


def test_inject_args_list(generic_product_1, generic_product_type_1) -> None:
    GenericProductOneInactive, GenericProduct = generic_product_type_1
    product_id = generic_product_1.product_id
    state = {"product": product_id, "customer_id": str(uuid4())}
    generic_sub = GenericProductOneInactive.from_product_id(
        product_id=state["product"], customer_id=state["customer_id"], status=SubscriptionLifecycle.INITIAL
    )
    generic_sub.pb_1.rt_1 = "test"
    generic_sub.pb_2.rt_2 = 42
    generic_sub.pb_2.rt_3 = "test2"

    generic_sub = SubscriptionModel.from_other_lifecycle(generic_sub, SubscriptionLifecycle.ACTIVE)

    generic_sub.save()

    @inject_args
    def step_existing(generic_sub: list[GenericProduct]) -> State:
        assert len(generic_sub) == 1
        assert generic_sub[0].subscription_id
        assert generic_sub[0].pb_1.rt_1 == "test"
        return {"generic_sub": generic_sub}

    # Put `generic_sub` as an UUID in. Entire `generic_sub` object would have worked as well, but this way we will be
    # certain that if we end up with an entire `generic_sub` object in the step function, it will have been retrieved
    # from the database.
    state["generic_sub"] = [generic_sub.subscription_id]

    state_amended = step_existing(state)
    assert "generic_sub" in state_amended
    assert len(state_amended["generic_sub"]) == 1

    # Do we now have an entire object instead of merely a UUID
    assert isinstance(state_amended["generic_sub"][0], GenericProduct)

    # And does it have the modifcations from the step functions
    assert state_amended["generic_sub"][0].pb_1.rt_1 is not None

    # Test `rt_1` has been persisted to the database with the modifications from the step function.`
    fresh_generic_sub = GenericProduct.from_subscription(state_amended["generic_sub"][0].subscription_id)
    assert fresh_generic_sub.pb_1.rt_1 is not None


def test_inject_args_optional(generic_product_1, generic_product_type_1) -> None:
    GenericProductOneInactive, GenericProduct = generic_product_type_1
    product_id = generic_product_1.product_id
    state = {"product": product_id, "customer_id": str(uuid4())}
    generic_sub = GenericProductOneInactive.from_product_id(
        product_id=state["product"], customer_id=state["customer_id"], status=SubscriptionLifecycle.INITIAL
    )
    generic_sub.pb_1.rt_1 = "test"
    generic_sub.pb_2.rt_2 = 42
    generic_sub.pb_2.rt_3 = "test2"

    generic_sub = SubscriptionModel.from_other_lifecycle(generic_sub, SubscriptionLifecycle.ACTIVE)

    generic_sub.save()

    @inject_args
    def step_existing(generic_sub: GenericProduct | None) -> State:
        assert generic_sub is not None, "Generic Sub IS NONE"
        assert generic_sub.subscription_id
        assert generic_sub.pb_1.rt_1 == "test"
        return {"generic_sub": generic_sub}

    with pytest.raises(AssertionError) as exc_info:
        step_existing(state)

    assert "Generic Sub IS NONE" in str(exc_info.value)

    # Put `light_path` as an UUID in. Entire `light_path` object would have worked as well, but this way we will be
    # certain that if we end up with an entire `light_path` object in the step function, it will have been retrieved
    # from the database.
    state["generic_sub"] = generic_sub.subscription_id

    state_amended = step_existing(state)
    assert "generic_sub" in state_amended

    # Do we now have an entire object instead of merely a UUID
    assert isinstance(state_amended["generic_sub"], GenericProduct)

    # And does it have the modifcations from the step functions
    assert state_amended["generic_sub"].pb_1.rt_1 is not None

    # Test `nso_service_id` has been persisted to the database with the modifications from the step function.`
    fresh_generic_sub = GenericProduct.from_subscription(state_amended["generic_sub"].subscription_id)
    assert fresh_generic_sub.pb_1.rt_1 is not None


def test_form_inject_args(generic_product_1, generic_product_type_1) -> None:
    GenericProductOneInactive, GenericProduct = generic_product_type_1
    product_id = generic_product_1.product_id
    state = {"product": product_id, "customer_id": str(uuid4())}
    generic_sub = GenericProductOneInactive.from_product_id(
        product_id=state["product"], customer_id=state["customer_id"], status=SubscriptionLifecycle.INITIAL
    )
    generic_sub.pb_1.rt_1 = "test"
    generic_sub.pb_2.rt_2 = 42
    generic_sub.pb_2.rt_3 = "test2"

    generic_sub = SubscriptionModel.from_other_lifecycle(generic_sub, SubscriptionLifecycle.ACTIVE)

    generic_sub.save()

    @form_inject_args
    def form_function(generic_sub: GenericProduct) -> State:
        assert generic_sub.subscription_id
        assert generic_sub.pb_1.rt_1 == "test"
        generic_sub.pb_1.rt_1 = "test string"

        class Form(FormPage):
            pass

        _ = yield Form
        return {"generic_sub": generic_sub}

    # Put `generic_sub` as an UUID in. Entire `generic_sub` object would have worked as well, but this way we will be
    # certain that if we end up with an entire `generic_sub` object in the step function, it will have been retrieved
    # from the database.
    state["generic_sub"] = generic_sub.subscription_id

    state_amended = post_form(form_function, state, [{}])
    assert "generic_sub" in state_amended

    # Do we now have an entire object instead of merely a UUID
    assert isinstance(state_amended["generic_sub"], GenericProduct)

    # And does it have the modifcations from the step functions
    assert state_amended["generic_sub"].pb_1.rt_1 == "test string"

    # Test `rt_1` has been persisted to the database with the modifications from the step function.`
    fresh_generic_sub = GenericProduct.from_subscription(state_amended["generic_sub"].subscription_id)
    assert fresh_generic_sub.pb_1.rt_1 is not None


def test_form_inject_args_simple(generic_product_1, generic_product_type_1) -> None:
    GenericProductOneInactive, GenericProduct = generic_product_type_1
    product_id = generic_product_1.product_id
    state = {"product": product_id, "customer_id": str(uuid4())}
    generic_sub = GenericProductOneInactive.from_product_id(
        product_id=state["product"], customer_id=state["customer_id"], status=SubscriptionLifecycle.INITIAL
    )
    generic_sub.pb_1.rt_1 = "test"
    generic_sub.pb_2.rt_2 = 42
    generic_sub.pb_2.rt_3 = "test2"

    generic_sub = SubscriptionModel.from_other_lifecycle(generic_sub, SubscriptionLifecycle.ACTIVE)

    generic_sub.save()

    @form_inject_args
    def form_function(generic_sub: GenericProduct) -> State:
        assert generic_sub.subscription_id
        assert generic_sub.pb_1.rt_1 == "test"
        generic_sub.pb_1.rt_1 = "test string"

        return {"generic_sub": generic_sub}

    # Put `generic_sub` as an UUID in. Entire `generic_sub` object would have worked as well, but this way we will be
    # certain that if we end up with an entire `generic_sub` object in the step function, it will have been retrieved
    # from the database.
    state["generic_sub"] = generic_sub.subscription_id

    state_amended = form_function(state)
    assert "generic_sub" in state_amended

    # Do we now have an entire object instead of merely a UUID
    assert isinstance(state_amended["generic_sub"], GenericProduct)

    # And does it have the modifcations from the step functions
    assert state_amended["generic_sub"].pb_1.rt_1 == "test string"

    # Test `rt_1` has been persisted to the database with the modifications from the step function.`
    fresh_generic_sub = GenericProduct.from_subscription(state_amended["generic_sub"].subscription_id)
    assert fresh_generic_sub.pb_1.rt_1 is not None


def test_uuid_parameter_with_string_uuid():
    # Test plain UUID parameter: providing a string should result in conversion to a UUID instance.

    @inject_args
    def step(uuid_param: UUID) -> State:
        # Return the UUID so we can inspect it
        return {"result": uuid_param}

    valid_uuid = uuid4()
    state = {"uuid_param": str(valid_uuid)}
    new_state = step(state)
    assert isinstance(new_state["result"], UUID)
    assert new_state["result"] == valid_uuid


def test_uuid_parameter_with_uuid_instance():
    # Test plain UUID parameter: providing a UUID instance should pass it through unchanged.

    @inject_args
    def step(uuid_param: UUID) -> State:
        return {"result": uuid_param}

    valid_uuid = uuid4()
    state = {"uuid_param": valid_uuid}
    new_state = step(state)
    assert isinstance(new_state["result"], UUID)
    assert new_state["result"] == valid_uuid


def test_uuid_parameter_missing_key():
    # Test that if the key for a UUID parameter is missing, a KeyError is raised.

    @inject_args
    def step(uuid_param: UUID) -> State:
        return {"result": uuid_param}

    state = {}  # key missing
    with pytest.raises(KeyError) as excinfo:
        step(state)

    assert "Could not find key 'uuid_param' in state. for function" in str(excinfo.value)


def test_uuid_parameter_invalid_value():
    # Test that an invalid UUID string raises a ValueError.

    @inject_args
    def step(uuid_param: UUID) -> State:
        return {"result": uuid_param}

    state = {"uuid_param": "not-a-valid-uuid"}
    with pytest.raises(ValueError) as excinfo:
        step(state)

    assert f"Could not convert value 'not-a-valid-uuid' to {UUID}" in str(excinfo.value)


def test_list_of_uuid_parameter_with_string():
    # Test list[UUID] parameter: providing a list of valid UUID strings.

    @inject_args
    def step(uuid_list: list[UUID]) -> State:
        return {"result": uuid_list}

    valid_uuid = uuid4()
    state = {"uuid_list": [str(valid_uuid)]}
    new_state = step(state)
    result = new_state["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], UUID)
    assert result[0] == valid_uuid


def test_list_of_uuid_parameter_with_uuid_instance():
    # Test list[UUID] parameter: providing a list with a UUID instance.

    @inject_args
    def step(uuid_list: list[UUID]) -> State:
        return {"result": uuid_list}

    valid_uuid = uuid4()
    state = {"uuid_list": [valid_uuid]}
    new_state = step(state)
    result = new_state["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], UUID)
    assert result[0] == valid_uuid


def test_list_of_uuid_parameter_invalid_value():
    # Test list[UUID] parameter: an invalid element in the list should cause a ValueError.

    @inject_args
    def step(uuid_list: list[UUID]) -> State:
        return {"result": uuid_list}

    state = {"uuid_list": ["invalid-uuid"]}
    with pytest.raises(ValueError) as excinfo:
        step(state)

    assert f"Could not convert value '['invalid-uuid']' to {list[UUID]}" in str(excinfo.value)


def test_optional_uuid_parameter_with_string():
    # Test Optional[UUID] parameter: providing a valid UUID string.

    @inject_args
    def step(optional_uuid: UUID | None) -> State:
        return {"result": optional_uuid}

    valid_uuid = uuid4()
    state = {"optional_uuid": str(valid_uuid)}
    new_state = step(state)
    result = new_state["result"]
    assert isinstance(result, UUID)
    assert result == valid_uuid


def test_optional_uuid_parameter_with_uuid_instance():
    # Test Optional[UUID] parameter: providing a UUID instance.

    @inject_args
    def step(optional_uuid: UUID | None) -> State:
        return {"result": optional_uuid}

    valid_uuid = uuid4()
    state = {"optional_uuid": valid_uuid}
    new_state = step(state)
    result = new_state["result"]
    assert isinstance(result, UUID)
    assert result == valid_uuid


def test_optional_uuid_parameter_with_none():
    # Test Optional[UUID] parameter: providing None explicitly.

    @inject_args
    def step(optional_uuid: UUID | None) -> State:
        return {"result": optional_uuid}

    state = {"optional_uuid": None}
    new_state = step(state)
    assert new_state["result"] is None


def test_optional_uuid_parameter_missing_key():
    # Test Optional[UUID] parameter: when the key is missing.

    @inject_args
    def step(optional_uuid: UUID | None) -> State:
        return {"result": optional_uuid}

    state = {}  # key missing; no default is provided, so expect a KeyError
    with pytest.raises(KeyError) as excinfo:
        step(state)

    assert "Could not find key 'optional_uuid' in state. for function" in str(excinfo.value)


def test_optional_uuid_parameter_invalid_value():
    # Test Optional[UUID] parameter: providing an invalid UUID value should raise ValueError.

    @inject_args
    def step(optional_uuid: UUID | None) -> State:
        return {"result": optional_uuid}

    state = {"optional_uuid": "invalid-uuid"}
    with pytest.raises(ValueError) as excinfo:
        step(state)

    assert f"Could not convert value 'invalid-uuid' to {UUID | None}" in str(excinfo.value)


def test_uuid_parameter_with_default_value():
    # Test that a default value is used if the key is missing.

    default_uuid = uuid4()

    @inject_args
    def step(uuid_param: UUID = default_uuid) -> State:
        return {"result": uuid_param}

    state = {}  # missing key, so the default should be used
    new_state = step(state)
    assert new_state["result"] == default_uuid


def test_uuid_parameter_with_default_value_and_string_in_state():
    # Test that when a UUID parameter has a default and a string is provided in state,
    # it gets converted to UUID (not left as a string).

    default_uuid = uuid4()

    @inject_args
    def step(uuid_param: UUID = default_uuid) -> State:
        return {"result": uuid_param}

    state = {"uuid_param": str(default_uuid)}
    new_state = step(state)
    assert isinstance(new_state["result"], UUID), f"Expected UUID but got {type(new_state['result'])}"
    assert new_state["result"] == default_uuid


def test_optional_uuid_parameter_with_default_none_and_string_in_state():
    # Test that Optional[UUID] with default None converts string to UUID when present.

    @inject_args
    def step(uuid_param: UUID | None = None) -> State:
        return {"result": uuid_param}

    valid_uuid = uuid4()
    state = {"uuid_param": str(valid_uuid)}
    new_state = step(state)
    assert isinstance(new_state["result"], UUID), f"Expected UUID but got {type(new_state['result'])}"
    assert new_state["result"] == valid_uuid


def test_optional_uuid_parameter_with_default_none_missing_key():
    # Test that Optional[UUID] with default None returns None when key is missing.

    @inject_args
    def step(uuid_param: UUID | None = None) -> State:
        return {"result": uuid_param}

    state = {}
    new_state = step(state)
    assert new_state["result"] is None


def test_list_of_uuid_parameter_with_default_and_string_in_state():
    # Test that list[UUID] with a default converts strings to UUIDs when present.

    default_list = [uuid4()]

    @inject_args
    def step(uuid_list: list[UUID] = default_list) -> State:
        return {"result": uuid_list}

    valid_uuid = uuid4()
    state = {"uuid_list": [str(valid_uuid)]}
    new_state = step(state)
    result = new_state["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], UUID), f"Expected UUID but got {type(result[0])}"
    assert result[0] == valid_uuid


def test_build_arguments_empty_signature():
    """Test that a function with no parameters returns an empty argument list."""
    from orchestrator.utils.state import _build_arguments

    def step_no_params():
        pass

    result = _build_arguments(step_no_params, {})
    assert result == []


def test_build_arguments_state_param_injects_entire_dict():
    """Test that a parameter named 'state' receives the entire state dict."""
    from orchestrator.utils.state import _build_arguments

    def step_with_state(state: State, other: int):
        pass

    test_state = {"other": 42, "extra_key": "extra_value"}
    result = _build_arguments(step_with_state, test_state)

    assert len(result) == 2
    assert result[0] is test_state  # entire state dict
    assert result[1] == 42


def test_build_arguments_state_param_at_different_positions():
    """Test 'state' param works at any position in signature."""
    from orchestrator.utils.state import _build_arguments

    def step_state_middle(a: int, state: State, b: str):
        pass

    test_state = {"a": 1, "b": "test"}
    result = _build_arguments(step_state_middle, test_state)

    assert result == [1, test_state, "test"]


def test_build_arguments_varargs_and_kwargs_ignored():
    """Test that *args and **kwargs are ignored and a warning is logged."""
    from orchestrator.utils.state import _build_arguments

    def step_with_varargs(a: int, *args, b: str, **kwargs):
        pass

    test_state = {"a": 10, "b": "hello"}
    result = _build_arguments(step_with_varargs, test_state)

    # Should only process 'a' and 'b', ignoring *args and **kwargs
    assert result == [10, "hello"]


def test_build_arguments_missing_required_param_includes_qualname():
    """Test that missing required param raises KeyError with module+qualname."""
    from orchestrator.utils.state import _build_arguments

    def step_func(required_param: str):
        pass

    state = {}

    with pytest.raises(KeyError) as exc_info:
        _build_arguments(step_func, state)

    error_msg = str(exc_info.value)
    assert "Could not find key 'required_param' in state." in error_msg
    assert "for function" in error_msg
    assert "test_state" in error_msg  # module name
    assert "step_func" in error_msg  # function name


def test_build_arguments_non_uuid_default_no_conversion():
    """Test that non-UUID types with defaults don't trigger UUID conversion."""
    from orchestrator.utils.state import _build_arguments

    def step(count: int = 10, name: str = "default"):
        pass

    state = {"count": 42}  # 'name' missing, should use default
    result = _build_arguments(step, state)

    assert result == [42, "default"]


def test_build_arguments_mixed_parameters():
    """Test a function with multiple parameter types to ensure correct ordering."""
    from orchestrator.utils.state import _build_arguments

    def step_func(
        required_uuid: UUID,
        required_str: str,
        optional_int: int = 42,
        optional_uuid: UUID | None = None,
    ):
        pass

    test_uuid1 = uuid4()
    test_uuid2 = uuid4()
    state = {
        "required_uuid": str(test_uuid1),
        "required_str": "hello",
        "optional_uuid": str(test_uuid2),
        # optional_int not in state, should use default
    }

    result = _build_arguments(step_func, state)

    assert len(result) == 4
    assert isinstance(result[0], UUID)
    assert result[0] == test_uuid1
    assert result[1] == "hello"
    assert result[2] == 42  # default
    assert isinstance(result[3], UUID)
    assert result[3] == test_uuid2


def test_build_arguments_empty_state_with_all_defaults():
    """Test that empty state works when all params have defaults."""
    from orchestrator.utils.state import _build_arguments

    def step_func(a: int = 1, b: str = "default"):
        pass

    state = {}
    result = _build_arguments(step_func, state)

    assert result == [1, "default"]


def test_build_arguments_subscription_model_list_any_guard(monkeypatch):
    """Test that list[Any] for SubscriptionModel raises ValueError with expected message."""
    from typing import Any

    from orchestrator.domain.base import SubscriptionModel
    from orchestrator.types import is_list_type
    from orchestrator.utils.state import _build_arguments

    # Create a function with list[Any] annotation that would trigger the guard
    def step_func(models: list[Any]):
        pass

    # Monkeypatch is_list_type to return True for this annotation
    # (simulating the case where we detect it's a list type intended for SubscriptionModel)
    original_is_list_type = is_list_type

    def patched_is_list_type(annotation, target_type):
        if target_type == SubscriptionModel and annotation == list[Any]:
            return True
        return original_is_list_type(annotation, target_type)

    monkeypatch.setattr("orchestrator.utils.state.is_list_type", patched_is_list_type)

    state = {"models": []}

    with pytest.raises(ValueError) as exc_info:
        _build_arguments(step_func, state)

    error_msg = str(exc_info.value)
    assert "Step function argument 'models' cannot be serialized from database with type 'Any'" in error_msg
