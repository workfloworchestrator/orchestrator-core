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

from enum import Enum
from http import HTTPStatus
from typing import Any, Callable, Dict, Generator, List, Literal, Optional, Tuple, Type, TypedDict, TypeVar, Union

from pydantic import BaseModel
from pydantic.typing import get_args, get_origin

UUIDstr = str
State = Dict[str, Any]
JSON = Any
# ErrorState is either a string containing an error message, a catched Exception or a tuple containing a message and
# a HTTP status code
ErrorState = Union[str, Exception, Tuple[str, Union[int, HTTPStatus]]]
# An ErrorDict should have the following keys:
# error: str  # A message describing the error
# class: str[Optional]  # The exception class name (type)
# status_code: Optional[int]  # HTTP Status code (optional)
# traceback: Optional[str]  # A python traceback as a string formatted by nwastdlib.ex.show_ex
ErrorDict = Dict[str, Union[str, int, List[Dict[str, Any]], "InputForm", None]]
StateStepFunc = Callable[[State], State]
StepFunc = Callable[..., Optional[State]]


class strEnum(str, Enum):
    def __str__(self) -> str:
        return self.value

    @classmethod
    def values(cls) -> List:
        return list(map(lambda obj: obj.value, cls))  # type: ignore


class SubscriptionLifecycle(strEnum):
    INITIAL = "initial"
    ACTIVE = "active"
    MIGRATING = "migrating"
    DISABLED = "disabled"
    TERMINATED = "terminated"
    PROVISIONING = "provisioning"


# The key is the Parent subscription life cycle status. The keys are lists of safe transitions for child subscriptions.
SAFE_PARENT_TRANSITIONS_FOR_STATUS = {
    SubscriptionLifecycle.INITIAL: [
        SubscriptionLifecycle.INITIAL,
    ],
    SubscriptionLifecycle.ACTIVE: [
        SubscriptionLifecycle.INITIAL,
        SubscriptionLifecycle.PROVISIONING,
        SubscriptionLifecycle.MIGRATING,
        SubscriptionLifecycle.ACTIVE,
        SubscriptionLifecycle.TERMINATED,
        SubscriptionLifecycle.DISABLED,
    ],
    SubscriptionLifecycle.MIGRATING: [
        SubscriptionLifecycle.INITIAL,
        SubscriptionLifecycle.MIGRATING,
        SubscriptionLifecycle.TERMINATED,
    ],
    SubscriptionLifecycle.PROVISIONING: [
        SubscriptionLifecycle.INITIAL,
        SubscriptionLifecycle.PROVISIONING,
        SubscriptionLifecycle.ACTIVE,
        SubscriptionLifecycle.TERMINATED,
    ],
    SubscriptionLifecycle.TERMINATED: [SubscriptionLifecycle.INITIAL, SubscriptionLifecycle.TERMINATED],
    SubscriptionLifecycle.DISABLED: [
        SubscriptionLifecycle.INITIAL,
        SubscriptionLifecycle.DISABLED,
        SubscriptionLifecycle.TERMINATED,
    ],
}


class AcceptItemType(strEnum):
    INFO = "info"
    LABEL = "label"
    WARNING = "warning"
    URL = "url"
    CHECKBOX = "checkbox"
    SUBCHECKBOX = ">checkbox"
    OPTIONAL_CHECKBOX = "checkbox?"
    OPTIONAL_SUBCHECKBOX = ">checkbox?"
    SKIP = "skip"
    VALUE = "value"
    MARGIN = "margin"


AcceptData = List[Union[Tuple[str, AcceptItemType], Tuple[str, AcceptItemType, Dict]]]

InputForm = Type[BaseModel]

T = TypeVar("T", bound=BaseModel)
FormGenerator = Generator[Type[T], T, State]
SimpleInputFormGenerator = Callable[..., InputForm]
InputFormGenerator = Callable[..., FormGenerator]
InputStepFunc = Union[SimpleInputFormGenerator, InputFormGenerator]
StateSimpleInputFormGenerator = Callable[[State], InputForm]
StateInputFormGenerator = Callable[[State], FormGenerator]
StateInputStepFunc = Union[StateSimpleInputFormGenerator, StateInputFormGenerator]
SubscriptionMapping = Dict[str, List[Dict[str, str]]]


class SummaryData(TypedDict, total=False):
    headers: List[str]
    labels: List[str]
    columns: List[List[Union[str, int, bool, float]]]


def is_of_type(t: Any, test_type: Any) -> bool:
    """Check if annotation type is valid for type.

    >>> is_of_type(list, list)
    True
    >>> is_of_type(List[int], List[int])
    True
    >>> is_of_type(strEnum, str)
    True
    >>> is_of_type(strEnum, Enum)
    True
    >>> is_of_type(int, str)
    False
    """

    if (
        get_origin(t)
        and get_origin(test_type)
        and get_origin(t) is get_origin(test_type)
        and get_args(t) == get_args(test_type)
    ):
        return True

    if test_type is t:
        # Test type is a typing type instance and matches
        return True

    # Workaround for the fact that you can't call issubclass on typing types
    try:
        return issubclass(t, test_type)
    except TypeError:
        return False


def is_list_type(t: Any, test_type: Optional[type] = None) -> bool:
    """Check if `t` is list type.

    And optionally check if the list items are of `test_type`

    >>> is_list_type(List[int])
    True
    >>> is_list_type(Optional[List[int]])
    True
    >>> is_list_type(Optional[List[int]], int)
    True
    >>> is_list_type(Optional[List[int]], str)
    False
    >>> is_list_type(Optional[int])
    False
    >>> is_list_type(List[Tuple[int, int]])
    True
    >>> is_list_type(List[Tuple[int, int]], int)
    False
    >>> is_list_type(List[Tuple[int, int]], Tuple[int, int])
    True
    >>> is_list_type(List[strEnum], Enum)
    True
    >>> is_list_type(int)
    False
    >>> is_list_type(Literal[1,2,3])
    False
    """
    if get_origin(t):
        if is_optional_type(t) or is_union_type(t):
            for arg in get_args(t):
                if is_list_type(arg, test_type):
                    return True
        elif get_origin(t) == Literal:  # type:ignore
            return False  # Literal cannot contain lists see pep 586
        elif issubclass(get_origin(t), list):  # type: ignore
            if test_type and get_args(t):
                return is_of_type(get_args(t)[0], test_type)
            else:
                return True

    return False


def is_optional_type(t: Any, test_type: Optional[type] = None) -> bool:
    """Check if `t` is optional type (Union[None, ...]).

    And optionally check if T is of `test_type`

    >>> is_optional_type(Optional[int])
    True
    >>> is_optional_type(Union[None, int])
    True
    >>> is_optional_type(Union[int, str, None])
    True
    >>> is_optional_type(Optional[int], int)
    True
    >>> is_optional_type(Optional[int], str)
    False
    >>> is_optional_type(Optional[State], int)
    False
    >>> is_optional_type(Optional[State], State)
    True
    >>> is_optional_type(int)
    False
    """
    if get_origin(t):
        if get_origin(t) == Union and None.__class__ in get_args(t):  # type:ignore
            for arg in get_args(t):
                if arg is None.__class__:
                    continue

                if test_type:
                    return is_of_type(arg, test_type)
                else:
                    return True
    return False


def is_union_type(t: Any, test_type: Optional[type] = None) -> bool:
    """Check if `t` is union type (Union[Type, AnotherType]).

    Optionally check if T is of `test_type` We cannot check for literal Nones.

    >>> is_union_type(Union[int, str])
    True
    >>> is_union_type(Union[int, str], str)
    True
    >>> is_union_type(Union[int, str], Union[int, str])
    True
    >>> is_union_type(int)
    False

    """
    if get_origin(t):
        if get_origin(t) == Union:  # type: ignore
            if test_type:
                if is_of_type(t, test_type):
                    return True
                for arg in get_args(t):
                    result = is_of_type(arg, test_type)
                    if result:
                        return result
                return False
            else:
                return True

    return False
