# Copyright 2019-2025 SURF, GÉANT, ESnet.
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

from collections.abc import Callable
from inspect import isgeneratorfunction
from typing import Annotated, Self, cast
from uuid import UUID

import structlog
from more_itertools import first_true
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select

from orchestrator.core.db import ProductTable, SubscriptionTable, db
from orchestrator.core.db.models import WorkflowTable
from orchestrator.core.services import subscriptions
from orchestrator.core.targets import Target
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.utils.auth import Authorizer
from orchestrator.core.utils.errors import StaleDataError
from orchestrator.core.utils.state import form_inject_args
from orchestrator.core.utils.validate_data_version import validate_data_version
from orchestrator.core.workflow import (
    RunPredicate,
    Step,
    StepList,
    Workflow,
    _warn_description_deprecated,
    begin,
    done,
    init,
    make_workflow,
    step,
)
from orchestrator.core.workflows.steps import (
    refresh_process_search_index,
    refresh_subscription_search_index,
    resync,
    set_status,
    store_process_subscription,
    unsync,
    unsync_unchecked,
)
from pydantic_forms.core import FormPage
from pydantic_forms.types import FormGenerator, InputForm, InputStepFunc, State, StateInputStepFunc
from pydantic_forms.validators.components.choice import Choice

logger = structlog.get_logger(__name__)


def _generate_new_subscription_form(
    _workflow_target: str, workflow_name: str, products_by_id: dict[str, ProductTable]
) -> InputForm:
    product_form_mapping = {k: (k, v.name) for k, v in products_by_id.items()}
    ProductChoice = Choice.__call__("ProductChoice", product_form_mapping)
    ProductSelect = Annotated[ProductChoice, Field(json_schema_extra={"format": "productId"})]  # type: ignore

    class NewProductPage(FormPage):
        product: ProductSelect

        @field_validator("product")
        @classmethod
        def product_validator(cls, product_id: ProductChoice) -> str:  # type: ignore
            """Run validator for initial_input_forms to check if the product exists and that this workflow is valid to run for this product."""
            product = products_by_id[product_id.name]  # type: ignore

            # Check if there is no reason to prevent this workflow
            current_workflow = product.create_subscription_workflow_key()

            if current_workflow != workflow_name:
                raise ValueError("This workflow is not valid for this product")

            return product_id

    return NewProductPage


def wrap_create_initial_input_form(initial_input_form: InputStepFunc | None) -> StateInputStepFunc | None:
    """Wrap initial input for create workflows.

    This is needed because the frontend expects all create workflows to start with a page that only contains the product.
    It also expects the second page to have some user visible inputs and the product *again*.
    """

    def create_initial_input_form_generator(state: State) -> FormGenerator:
        workflow_target: str = state["workflow_target"]
        workflow_name: str = state["workflow_name"]

        products = db.session.scalars(
            select(ProductTable).where(ProductTable.workflows.any(WorkflowTable.name == workflow_name))
        ).all()
        product_mapping = {str(product.product_id): product for product in products}

        product_user_input = yield _generate_new_subscription_form(workflow_target, workflow_name, product_mapping)

        product = product_mapping[product_user_input.product.name]

        begin_state = {"product": product.product_id, "product_name": product.name}

        if initial_input_form is None:
            return begin_state

        form = form_inject_args(initial_input_form)({**state, **begin_state})

        if isgeneratorfunction(initial_input_form):
            user_input = yield from cast(FormGenerator, form)
        else:
            user_input_model = yield cast(InputForm, form)
            user_input = user_input_model.model_dump()

        return {**begin_state, **user_input}

    return create_initial_input_form_generator


# TODO these translations should stay in the frontend See also #549
TRANSLATIONS = {
    "subscription.not_in_sync": "Subscription already has a running process or task",
    "subscription.relations_not_in_sync": "This subscription can not be modified because some related subscriptions are not insync",
    "subscription.no_modify_invalid_status": "This subscription can not be modified because of the status it has",
    "subscription.no_modify_parent_subscription": "This subscription can not be modified as it is used in other subscriptions",
    "subscription.no_modify_subscription_in_use_by_others": "This subscription can not be modified as it is used in other subscriptions",
    "subscription.no_modify_auto_negotiation": "This workflow is not valid for this subscription",
}


def _generate_modify_form(workflow_target: str, workflow_name: str) -> InputForm:
    class ModifySubscriptionPage(FormPage):
        # We use UUID instead of SubscriptionId here because we don't want the allowed_status check and
        # we do our own validation here.
        subscription_id: UUID
        version: int | None = None

        @field_validator("subscription_id")
        @classmethod
        def subscription_validator(cls, subscription_id: UUID) -> UUID:
            """Run validator for initial_input_forms to check if the subscription exists and that this workflow is valid to run for this subscription."""
            subscription = db.session.get(SubscriptionTable, subscription_id)
            if subscription is None:
                raise ValueError("Subscription not found")

            # Check if there is no reason to prevent this workflow
            workflows = subscriptions.subscription_workflows(subscription)
            current_workflow = first_true(
                workflows[workflow_target.lower()], None, lambda wf: wf["name"] == workflow_name
            )

            if not current_workflow:
                raise ValueError("This workflow is not valid for this subscription")

            if "reason" in current_workflow:
                message = TRANSLATIONS.get(current_workflow["reason"], current_workflow["reason"])
                raise ValueError(f"This workflow cannot be started: {message}")

            return subscription_id

        @model_validator(mode="after")
        def version_validator(self) -> Self:
            current_version = db.session.scalars(
                select(SubscriptionTable.version).where(SubscriptionTable.subscription_id == self.subscription_id)
            ).one()
            if not validate_data_version(current_version, self.version):
                raise StaleDataError(current_version, self.version)
            return self

    return ModifySubscriptionPage


def wrap_modify_initial_input_form(initial_input_form: InputStepFunc | None) -> StateInputStepFunc | None:
    """Wrap initial input for modify, reconcile and terminate workflows.

    This is needed because the frontend expects all modify workflows to start with a page that only contains the
    subscription id. It also expects the second page to have some user visible inputs and the subscription id *again*.
    """

    def create_initial_input_form_generator(state: State) -> FormGenerator:
        workflow_target: str = state["workflow_target"]
        workflow_name: str = state["workflow_name"]

        user_input = yield _generate_modify_form(workflow_target, workflow_name)

        subscription = db.session.get(SubscriptionTable, user_input.subscription_id)
        if subscription is None:
            raise ValueError(f"Subscription {user_input.subscription_id} not found")
        begin_state = {
            "subscription_id": str(subscription.subscription_id),
            "product": str(subscription.product_id),
            "customer_id": subscription.customer_id,
            "version": subscription.version,
        }

        if initial_input_form is None:
            return begin_state

        form = form_inject_args(initial_input_form)({**state, **begin_state})

        if isgeneratorfunction(initial_input_form):
            user_input = yield from cast(FormGenerator, form)
        else:
            user_input_model = yield cast(InputForm, form)
            user_input = user_input_model.model_dump()

        return {**begin_state, **user_input}

    return create_initial_input_form_generator


modify_initial_input_form_generator = None


validate_initial_input_form_generator = wrap_modify_initial_input_form(modify_initial_input_form_generator)


def task(
    description: str = "",
    initial_input_form: InputStepFunc | None = None,
    additional_steps: StepList | None = None,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow with a target=Target.SYSTEM.

    Use this for tasks only.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @task(initial_input_form=initial_input_form_generator)
        def run_some_task() -> StepList:
            begin
            >> do_something
            >> do_something_else
    """
    if description:
        _warn_description_deprecated()
    if initial_input_form is None:
        initial_input_form_in_form_inject_args = None
    else:
        initial_input_form_in_form_inject_args = form_inject_args(initial_input_form)

    def _workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = init >> f() >> (additional_steps or StepList()) >> done

        return make_workflow(
            f,
            description,
            initial_input_form_in_form_inject_args,
            Target.SYSTEM,
            steps=steplist,
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _workflow


def create_workflow(
    description: str = "",
    initial_input_form: InputStepFunc | None = None,
    status: SubscriptionLifecycle = SubscriptionLifecycle.ACTIVE,
    additional_steps: StepList | None = None,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow with a target=Target.CREATE.

    Use this for create workflows only.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @create_workflow(initial_input_form=initial_input_form_generator)
        def create_service_port() -> StepList:
            do_something
            >> do_something_else
    """
    if description:
        _warn_description_deprecated()
    create_initial_input_form_generator = wrap_create_initial_input_form(initial_input_form)

    def _create_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> f()
            >> (additional_steps or StepList())
            >> set_status(status)
            >> resync
            >> refresh_subscription_search_index
            >> refresh_process_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            create_initial_input_form_generator,
            Target.CREATE,
            steplist,
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _create_workflow


def modify_workflow(
    description: str = "",
    initial_input_form: InputStepFunc | None = None,
    additional_steps: StepList | None = None,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for modify workflows.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @modify_workflow(initial_input_form=initial_input_form_generator)
        def modify_service_port() -> StepList:
            do_something
            >> do_something_else
    """
    if description:
        _warn_description_deprecated()

    wrapped_modify_initial_input_form_generator = wrap_modify_initial_input_form(initial_input_form)

    def _modify_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> store_process_subscription()
            >> unsync
            >> f()
            >> (additional_steps or StepList())
            >> resync
            >> refresh_subscription_search_index
            >> refresh_process_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            wrapped_modify_initial_input_form_generator,
            Target.MODIFY,
            steplist,
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _modify_workflow


def terminate_workflow(
    description: str = "",
    initial_input_form: InputStepFunc | None = None,
    additional_steps: StepList | None = None,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for terminate workflows.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @terminate_workflow(initial_input_form=terminate_initial_input_form_generator)
        def terminate_service_port() -> StepList:
            do_something
            >> do_something_else
    """
    if description:
        _warn_description_deprecated()

    wrapped_terminate_initial_input_form_generator = wrap_modify_initial_input_form(initial_input_form)

    def _terminate_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> store_process_subscription()
            >> unsync
            >> f()
            >> (additional_steps or StepList())
            >> set_status(SubscriptionLifecycle.TERMINATED)
            >> resync
            >> refresh_subscription_search_index
            >> refresh_process_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            wrapped_terminate_initial_input_form_generator,
            Target.TERMINATE,
            steplist,
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _terminate_workflow


def validate_workflow(
    description: str = "",
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for subscription validate workflows.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @validate_workflow()
        def validate_service_port() -> StepList:
            do_something
            >> do_something_else
    """
    if description:
        _warn_description_deprecated()

    def _validate_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = init >> store_process_subscription() >> unsync_unchecked >> f() >> resync >> done

        return make_workflow(
            f,
            description,
            validate_initial_input_form_generator,
            Target.VALIDATE,
            steplist,
            run_predicate=run_predicate,
        )

    return _validate_workflow


def reconcile_workflow(
    description: str = "",
    additional_steps: StepList | None = None,
    authorize_callback: Authorizer | None = None,
    retry_auth_callback: Authorizer | None = None,
    run_predicate: RunPredicate | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Similar to a modify_workflow but without required input user input to perform a sync with external systems based on the subscriptions existing configuration.

    Use this for subscription reconcile workflows.

    .. deprecated::
        The `description` parameter is deprecated and will be removed in a future version.
        Workflow descriptions should now be managed in the database via the UI or API endpoint.
        You can safely remove this parameter from the decorator.
        Removal is tracked in issue #1463.

    Example::

        @reconcile_workflow()
        def reconcile_l2vpn() -> StepList:
            return (
                begin
                >> update_l2vpn_in_external_systems
            )
    """
    if description:
        _warn_description_deprecated()

    wrapped_reconcile_initial_input_form_generator = wrap_modify_initial_input_form(None)

    def _reconcile_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> store_process_subscription()
            >> unsync
            >> f()
            >> (additional_steps or StepList())
            >> resync
            >> refresh_subscription_search_index
            >> refresh_process_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            wrapped_reconcile_initial_input_form_generator,
            Target.RECONCILE,
            steplist,
            authorize_callback=authorize_callback,
            retry_auth_callback=retry_auth_callback,
            run_predicate=run_predicate,
        )

    return _reconcile_workflow


def ensure_provisioning_status(modify_steps: Step | StepList) -> StepList:
    """Decorator to ensure subscription modifications are executed only during Provisioning status."""
    return (
        begin
        >> set_status(SubscriptionLifecycle.PROVISIONING)
        >> modify_steps
        >> set_status(SubscriptionLifecycle.ACTIVE)
    )


@step("Equalize workflow step count")
def obsolete_step() -> None:
    """Equalize workflow step counts.

    When changing existing workflows that might have suspended instances in production it is important
    to keep the exact same amount of steps. This step can be used to fill the gap when removing a step.
    """
    pass
