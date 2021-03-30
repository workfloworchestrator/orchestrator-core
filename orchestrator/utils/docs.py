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

"""
Functions for automatically generating docs for workflows and domain models.

WARNING: When developing on these auto generated docs,
    sphinx does not rebuild the files where these functions are called. To see your changes reflected you need to
    change or ``touch`` the file in question. Or use ``make clean docs``

WARNING2: Since we use the sphinx napoleon extension and the docstrings we generate are parsed by that.
    You cannot use all rst but you need to conform to google style docstring syntax. This also means that
    For any new header you probably need to add it to the docs config

    Also watch out for indentation. The resulting string needs to have the correct indentation.
"""

import inspect
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, get_origin
from uuid import UUID

from more_itertools import first

from orchestrator.types import SubscriptionLifecycle

if TYPE_CHECKING:
    from orchestrator.domain.base import ProductBlockModel, SubscriptionModel
    from orchestrator.workflow import Step, Workflow
    from orchestrator.workflows import LazyWorkflowInstance


INDENT1 = " " * 4
INDENT2 = " " * 8
INDENT3 = " " * 12


def make_ref(field_type: Any, shorten: bool = True) -> str:
    if hasattr(field_type, "__qualname__"):
        ref = f"{'~' if shorten else ''}{field_type.__module__}.{field_type.__qualname__.split('.<locals>')[0].split('[')[0]}"
    elif get_origin(field_type):
        ref = make_ref(get_origin(field_type))
    else:
        ref = str(field_type)
    return ref


def get_doc_title(field_type: Any) -> str:
    return first((field_type.__doc__ or "").splitlines(), "")


def make_field_doc(field_name: str, field_type: Any) -> str:
    r"""Make docstring for domain model field.

    >>> make_field_doc("int_field", int)
    '        int_field:\n            Type :class:`~builtins.int`'

    >>> class Something:
    ...     "Doc title"
    >>> make_field_doc("int_field", Something)
    '        int_field:\n            Doc title\n\n            Type :class:`~orchestrator.utils.docs.Something`'
    """

    if field_type in (int, bool, str, UUID):
        type_doc_str = ""
    else:
        type_doc_str = f"{INDENT3}" + get_doc_title(field_type) + "\n\n"

    return f"{INDENT2}{field_name}:\n{type_doc_str}{INDENT3}Type :class:`{make_ref(field_type)}`"


def make_product_block_docstring(
    block: Type["ProductBlockModel"], lifecycle: Optional[List[SubscriptionLifecycle]] = None
) -> str:

    lifecycle_str = f"\n\nValid for statuses: {', '.join(lifecycle) if lifecycle else 'all others'}"

    if SubscriptionLifecycle.ACTIVE not in (lifecycle or []):
        return f"{lifecycle_str}\n\nSee `active` version."

    siv_strings = []
    for field_name, field_type in block._non_product_block_fields_.items():
        siv_strings.append(make_field_doc(field_name, field_type))

    product_block_strings = []
    for field_name, field_type in block._product_block_fields_.items():
        product_block_strings.append(make_field_doc(field_name, field_type))

    siv_string = ""
    if siv_strings:
        siv_string = "\nInstance Values:\n\n" + "\n".join(siv_strings)

    product_block_string = ""
    if product_block_strings:
        product_block_string = "\nBlocks:\n\n" + "\n".join(product_block_strings)

    return (block.__doc__ or "") + f"\n\n{lifecycle_str}\n\n{siv_string}{product_block_string}\n"


def make_subscription_model_docstring(
    model: Type["SubscriptionModel"], lifecycle: Optional[List[SubscriptionLifecycle]] = None
) -> str:
    lifecycle_str = f"\n\nValid for statuses: {', '.join(lifecycle) if lifecycle else 'all others'}"

    if SubscriptionLifecycle.ACTIVE not in (lifecycle or []):
        return f"{lifecycle_str}\n\nSee `active` version."

    fixed_input_strings = []
    for field_name, field_type in model._non_product_block_fields_.items():
        fixed_input_strings.append(make_field_doc(field_name, field_type))

    product_block_strings = []
    for field_name, field_type in model._product_block_fields_.items():
        product_block_strings.append(make_field_doc(field_name, field_type))

    fixed_input_string = ""
    if fixed_input_strings:
        fixed_input_string = "\nFixed Inputs:\n\n" + "\n".join(fixed_input_strings)

    product_block_string = ""
    if product_block_strings:
        product_block_string = "\nBlocks:\n\n" + "\n".join(product_block_strings)

    return (model.__doc__ or "") + f"\n\n{lifecycle_str}\n\n{fixed_input_string}{product_block_string}"


def make_workflow_doc(wf: "Workflow") -> str:
    def make_step_doc(step: "Step") -> str:
        doc = inspect.getdoc(step)
        doc_title = doc.splitlines()[0] if doc else ""

        return (
            f"{INDENT1}#. :func:`{step.__name__.strip('_')} <{make_ref(step, shorten=False)}>`\n\n{INDENT2}{doc_title}"
        )

    steps_string = "\n".join(make_step_doc(step) for step in wf.steps)

    return f"{(wf.__doc__ or '')}\n\nSteps:\n\n{steps_string}\n"


def make_workflow_index_doc(all_workflows: Dict[str, "LazyWorkflowInstance"]) -> str:
    workflow_list_str = "\n".join(map(lambda wf: f"* :obj:`~{wf[1].package}.{wf[0]}`", all_workflows.items()))
    return f"\nWorkflows\n---------\n\n{workflow_list_str}\n"


def make_product_type_index_doc(subscription_model_registry: Dict[str, Type["SubscriptionModel"]]) -> str:
    product_types_str = "\n".join(
        map(
            lambda product: f"* :class:`~{product.__module__}.{product.__qualname__}`",
            set(subscription_model_registry.values()),
        )
    )

    return f"\nProduct Types\n---------\n\n{product_types_str}\n"
