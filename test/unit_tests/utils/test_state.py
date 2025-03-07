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
