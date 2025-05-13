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
from typing import Self, cast
from uuid import UUID

from more_itertools import first_true
from pydantic import field_validator, model_validator
from sqlalchemy import select

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.db import ProductTable, SubscriptionTable, db
from orchestrator.forms.validators import ProductId
from orchestrator.services import subscriptions
from orchestrator.targets import Target
from orchestrator.types import SubscriptionLifecycle
from orchestrator.utils.errors import StaleDataError
from orchestrator.utils.state import form_inject_args
from orchestrator.utils.validate_data_version import validate_data_version
from orchestrator.workflow import Step, StepList, Workflow, begin, done, init, make_workflow, step
from orchestrator.workflows.steps import (
    refresh_subscription_search_index,
    resync,
    set_status,
    store_process_subscription,
    unsync,
    unsync_unchecked,
)
from pydantic_forms.core import FormPage
from pydantic_forms.types import FormGenerator, InputForm, InputStepFunc, State, StateInputStepFunc


def _generate_new_subscription_form(_workflow_target: str, workflow_name: str) -> InputForm:
    class NewProductPage(FormPage):
        product: ProductId

        @field_validator("product")
        @classmethod
        def product_validator(cls, product_id: UUID) -> UUID:
            """Run validator for initial_input_forms to check if the product exists and that this workflow is valid to run for this product."""
            product = db.session.get(ProductTable, product_id)
            if product is None:
                raise ValueError("Product not found")

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

        product_user_input = yield _generate_new_subscription_form(workflow_target, workflow_name)

        product = db.session.scalars(
            select(ProductTable).where(ProductTable.product_id == product_user_input.product)
        ).one()

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
    """Wrap initial input for modify and terminate workflows.

    This is needed because the frontend expects all modify workflows to start with a page that only contains the
    subscription id. It also expects the second page to have some user visible inputs and the subscription id *again*.
    """

    def create_initial_input_form_generator(state: State) -> FormGenerator:
        workflow_target: str = state["workflow_target"]
        workflow_name: str = state["workflow_name"]

        user_input = yield _generate_modify_form(workflow_target, workflow_name)

        subscription = SubscriptionTable.query.get(user_input.subscription_id)
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


def create_workflow(
    description: str,
    initial_input_form: InputStepFunc | None = None,
    status: SubscriptionLifecycle = SubscriptionLifecycle.ACTIVE,
    additional_steps: StepList | None = None,
    authorize_callback: Callable[[OIDCUserModel | None], bool] | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow with a target=Target.CREATE.

    Use this for create workflows only.

    Example::

        @create_workflow("create service port")
        def create_service_port() -> StepList:
            do_something
            >> do_something_else
    """
    create_initial_input_form_generator = wrap_create_initial_input_form(initial_input_form)

    def _create_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> f()
            >> (additional_steps or StepList())
            >> set_status(status)
            >> resync
            >> refresh_subscription_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            create_initial_input_form_generator,
            Target.CREATE,
            steplist,
            authorize_callback=authorize_callback,
        )

    return _create_workflow


def modify_workflow(
    description: str,
    initial_input_form: InputStepFunc | None = None,
    additional_steps: StepList | None = None,
    authorize_callback: Callable[[OIDCUserModel | None], bool] | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for modify workflows.

    Example::

        @modify_workflow("modify service port") -> StepList:
        def modify_service_port():
            do_something
            >> do_something_else
    """

    wrapped_modify_initial_input_form_generator = wrap_modify_initial_input_form(initial_input_form)

    def _modify_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> store_process_subscription(Target.MODIFY)
            >> unsync
            >> f()
            >> (additional_steps or StepList())
            >> resync
            >> refresh_subscription_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            wrapped_modify_initial_input_form_generator,
            Target.MODIFY,
            steplist,
            authorize_callback=authorize_callback,
        )

    return _modify_workflow


def terminate_workflow(
    description: str,
    initial_input_form: InputStepFunc | None = None,
    additional_steps: StepList | None = None,
    authorize_callback: Callable[[OIDCUserModel | None], bool] | None = None,
) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for terminate workflows.

    Example::

        @terminate_workflow("terminate service port") -> StepList:
        def terminate_service_port():
            do_something
            >> do_something_else
    """

    wrapped_terminate_initial_input_form_generator = wrap_modify_initial_input_form(initial_input_form)

    def _terminate_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = (
            init
            >> store_process_subscription(Target.TERMINATE)
            >> unsync
            >> f()
            >> (additional_steps or StepList())
            >> set_status(SubscriptionLifecycle.TERMINATED)
            >> resync
            >> refresh_subscription_search_index
            >> done
        )

        return make_workflow(
            f,
            description,
            wrapped_terminate_initial_input_form_generator,
            Target.TERMINATE,
            steplist,
            authorize_callback=authorize_callback,
        )

    return _terminate_workflow


def validate_workflow(description: str) -> Callable[[Callable[[], StepList]], Workflow]:
    """Transform an initial_input_form and a step list into a workflow.

    Use this for subscription validate workflows.

    Example::

        @validate_workflow("create service port")
        def create_service_port():
            do_something
            >> do_something_else
    """

    def _validate_workflow(f: Callable[[], StepList]) -> Workflow:
        steplist = init >> store_process_subscription(Target.SYSTEM) >> unsync_unchecked >> f() >> resync >> done

        return make_workflow(f, description, validate_initial_input_form_generator, Target.VALIDATE, steplist)

    return _validate_workflow


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
