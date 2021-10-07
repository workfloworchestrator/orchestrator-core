# Copyright 2019-2020 SURF.
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


import inspect
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple, Union, cast
from uuid import UUID

from pydantic.typing import get_args

from orchestrator.domain.base import SubscriptionModel
from orchestrator.types import (
    FormGenerator,
    InputForm,
    InputFormGenerator,
    InputStepFunc,
    SimpleInputFormGenerator,
    State,
    StateInputStepFunc,
    StepFunc,
    is_list_type,
    is_optional_type,
)
from orchestrator.utils.functional import logger


def extract(keys: Tuple[str, ...], state: State) -> Tuple[Any, ...]:
    """Extract multiple values from dictionary.

    Args:
        keys: Tuple of key whose values should be extracted from the dictionary.
        state: The dictionary where values need to be extracted from.

    Returns:
        Tuple with values from the `state` dictionary.

    """
    return tuple(state[k] for k in keys)


def _get_sub_id(val: Any) -> Optional[UUID]:
    """Get the subscription_id for a domain model from a state like dict.

    The convention we use is that for a parameter specification of `light_path: Sn8LightPath` for a step function,
    eg::

        @state_params_domain
        def my_step(light_path: Sn8LightPath) -> State:
            ...

    we expect the state (that will be passed to `my_step`) to either:

    - have a top level key `light_path` with a `str` or `UUID` value for the associated `subscription_id`
    - have a top level key `light_path` with dict representation of the domain model.

    In case of the latter, the `subscription_id` is represented by the key `subscription_id` in the dict
    representation of the domain model.

    Args:
        data: the state like dict
        name: name of the variable representing a domain model

    Returns:
        A UUID if found, None otherwise.

    """
    if isinstance(val, dict):
        val = val.get("subscription_id")
    elif isinstance(val, SubscriptionModel):
        raise AssertionError("There should be no SubscriptionModel instances in the state before a step!")
    elif isinstance(val, UUID):
        return val
    try:
        uuid = UUID(val)
        return uuid
    except Exception:
        return None


def _save_models(state: State) -> None:
    """Save all domain models found under a key in the state.

    ..note:: This does not cover domain models in containers structures (lists, sets, tuples)

    It does cover domain models in nested dictionaries (use case: migration workflows that utilize `@focussteps`)

    Examples:
        Both dicts will have their `light_path` domain model saved::

            {
                'product': 'b3c0038f-1dc5-4dd4-b2a4-0a7c6c34401a',
                'customer': 'ae859151-fa7d-4953-a9d0-f709a0b31641',
                'light_path': Sn8LightPath(...)
            }

    and::

        {
            'product': 'b3c0038f-1dc5-4dd4-b2a4-0a7c6c34401a',
            'customer': 'ae859151-fa7d-4953-a9d0-f709a0b31641',
            'new_subscription': {
                'light_path': Sn8LightPath(...)
            }
        }

    but **not** the two `Sn8LightPath`ss under key `light_paths` (because value is a list)::

        {
            'product': 'b3c0038f-1dc5-4dd4-b2a4-0a7c6c34401a',
            'customer': 'ae859151-fa7d-4953-a9d0-f709a0b31641',
            'light_paths': [Sn8LightPath(...), Sn8LightPath(...)]
        }

    Args:
        state: state dictionary

    """
    for key, value in state.items():
        if isinstance(value, SubscriptionModel):
            logger.debug("Persisting domain model by calling `save()` on it.", name=key, type=value.__class__.__name__)
            value.save()
        elif isinstance(value, list):
            _save_models({f"{key}.{i}": v for i, v in enumerate(value)})
        elif isinstance(value, dict):
            # traverse entire state, depth first
            _save_models(value)


def _build_arguments(func: Union[StepFunc, InputStepFunc], state: State) -> List:
    """Build actual arguments based on step function signature and state.

    What the step function requests in its function signature it what this function retrieves from the state or DB.
    Domain models are retrieved from the DB (after `subscription_id` lookup in the state). Everything else is
    retrieved from the state.

    For domain models only ``Optional`` and ``List`` are supported as container types. Union, Dict and others are not supported

    Args:
        func: step function to inspect for requested arguments
        state: workflow state

    Returns:
        List of actual positional arguments.

    Raises:
         KeyError: if requested argument is not in the state, or cannot be reconstructed as an initial domain model.

    """
    sig = inspect.signature(func)
    arguments: List[Any] = []
    if sig.parameters:
        for name, param in sig.parameters.items():
            # Ignore dynamic arguments. Mostly need to deal with `const`
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                logger.warning("*args and **kwargs are not supported as step params")
                continue

            # If we find an argument named "state" we use the whole state as argument to
            # This is mainly to be backward compatible with code that needs the whole state...
            # TODO: Remove this construction
            if name == "state":
                arguments.append(state)
                continue

            # Workaround for the fact that you can't call issubclass on typing types
            try:
                is_subscription_model_type = issubclass(param.annotation, SubscriptionModel)
            except Exception:
                is_subscription_model_type = False

            if is_subscription_model_type:
                subscription_id = _get_sub_id(state.get(name))
                if subscription_id:
                    sub_mod = param.annotation.from_subscription(subscription_id)
                    arguments.append(sub_mod)
                else:
                    logger.error("Could not find key in state.", key=name, state=state)
                    raise KeyError(f"Could not find key '{name}' in state.")
            elif is_list_type(param.annotation, SubscriptionModel):
                subscription_ids = map(_get_sub_id, state.get(name, []))
                subscriptions = [
                    # Actual type is first argument from list type
                    get_args(param.annotation)[0].from_subscription(subscription_id)
                    for subscription_id in subscription_ids
                ]
                arguments.append(subscriptions)
            elif is_optional_type(param.annotation, SubscriptionModel):
                subscription_id = _get_sub_id(state.get(name))
                if subscription_id:
                    # Actual type is first argument from optional type
                    sub_mod = get_args(param.annotation)[0].from_subscription(subscription_id)
                    arguments.append(sub_mod)
                else:
                    arguments.append(None)
            elif param.default is not inspect.Parameter.empty:
                arguments.append(state.get(name, param.default))
            else:
                try:
                    arguments.append(state[name])
                except KeyError as key_error:
                    logger.error("Could not find key in state.", key=name, state=state)
                    raise KeyError(
                        f"Could not find key '{name}' in state. for function {func.__module__}.{func.__qualname__}"
                    ) from key_error
    return arguments


def inject_args(func: StepFunc) -> Callable[[State], State]:
    """Allow functions to specify values from the state dict as parameters named after the state keys.

    .. note:: domain models are subject to special processing (see: :ref:`domain models processing
        <domain-models-processing>`)

    What this decorator does is better explained with an example than lots of text. So normally we do this::

        def load_initial_state_for_modify(state: State) -> State:
            organisation_id = state["organisation"]
            subscription_id = state["subscription_id"]
            ....
            # build new_state
            ...
            return {**state, **new_state}

    With this decorator we can do::

        @inject_args
        def load_initial_state_for_modify(organisation: UUID, subscription_id: UUID) -> State:
            ....
            # build new_state
            ...
            return new_state

    So any parameters specified to the step function are looked up in the `state` dict supplied by the `step` decorator
    and passed as values to the step function. The dict `new_state` returned by the step function will be merged with
    that of the original `state` dict and returned as the final result.

    It knows how to deal with parameters that have a default. Eg, given::

        @inject_args
        def do_stuff_with_saps(subscription_id: UUID, sap1: Dict, sap2: Optional[Dict] = None) -> State:
            ....
            # build new_state
            ...
            return new_state

    Both `subscription_id` and `sap1` need to be present in the state. However `sap2` can be present but does not need
    to be. If it is not present in the state it will get the value `None`

    Default values are supported to!

    .. _domain-models-processing:

    Domain models as parameters are subject to special processing. Eg, given::

        @inject_args
        def do_stuff(light_path: Sn8LightPath) -> State:
            ...
            return {'light_path': light_path}  # <- required for any changes to be saved to the DB

    Then the key 'light_path' is looked up in the state. If it is present, it is expected to be either:

    - a UUID (or str representation of a UUID)
    - a dictionary with at least a key 'subscription_id', representing a domain model.

    It will use the UUID found to retrieve the domain model from the DB and inject it into the step function. None of
    the other data from the domain model (in case of it being a dict representation) will be used! At the end of the
    step function any domain models explicitly returned will be automatically saved to the DB; this includes any new
    domain models that might be created in the step and returned by the step. Hence the automatic save is not limited
    to domain models requested as part of the step parameter list.

    If the key `light_path` was not found in the state, the parameter is interpreted as a request to create a
    domain model of the given type. For that to work correctly the keys `product` and `organisation` need to be
    present in the state. This will not work for more than one domain model. Eg. you can't request two domain
    models to be created as we will not know to which of the two domain models `product` is applicable to.

    Also supported is wrapping a domain model in ``Optional`` or ``List``. Other types are not supported.

    Args:
        func: a step function with parameters (that should be keys into the state dict, except for optional ones)

    Returns:
        The original state dict merged with the state that step function returned.

    """

    @wraps(func)
    def wrapper(state: State) -> State:
        args = _build_arguments(func, state)
        new_state = func(*args)

        # Support step functions that don't return anything
        if new_state is None:
            new_state = {}

        _save_models(new_state)

        return {**state, **new_state}

    return wrapper


def form_inject_args(func: InputStepFunc) -> StateInputStepFunc:
    """See :func:`state_parms` for description.

    This decorator behaves similarly to :func:`inject_args`. `form_inject_args` can be used on generatorfunctions.
    """

    if inspect.isgeneratorfunction(func):
        generator_func = cast(InputFormGenerator, func)

        @wraps(generator_func)
        def wrapper(state: State) -> FormGenerator:
            args = _build_arguments(generator_func, state)
            new_state = yield from generator_func(*args)
            _save_models(new_state)
            return new_state

    else:
        simple_func = cast(SimpleInputFormGenerator, func)

        @wraps(simple_func)
        def wrapper(state: State) -> Optional[InputForm]:
            args = _build_arguments(simple_func, state)
            new_state = simple_func(*args)
            return new_state

    return wrapper
