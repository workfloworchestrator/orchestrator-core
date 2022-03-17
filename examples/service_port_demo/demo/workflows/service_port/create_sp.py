from typing import Optional
from uuid import uuid4, UUID

import structlog
from more_itertools import one

from orchestrator.forms import FormPage
from orchestrator.forms.validators import Choice, ContactPersonList, Divider, Label, OrganisationId
from orchestrator.services import products, subscriptions
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.steps import store_process_subscription

from demo.products.product_blocks.sp import PortMode
from demo.products.product_types.sp import ServicePortInactive, ServicePortProvisioning
from demo.workflows.workflow import create_workflow

logger = structlog.get_logger(__name__)


def initial_input_form_generator(product: UUIDstr, product_name: str) -> FormGenerator:
    _product = products.get_product_by_id(product)
    port_speed = int(_product.fixed_input_value("port_speed"))
    PortEnum = Choice("PortEnum", zip(["untagged", "tagged"], ["untagged", "tagged"]))

    class ServicePortCreateForm(FormPage):
        class Config:
            title = product_name

        organisation: UUID = uuid4()
        contact_persons: ContactPersonList = []

        port_id: int
        port_mode: PortEnum

    user_input = yield ServicePortCreateForm

    return user_input.dict()


@step("Construct SP model")
def construct_sp_model(
    product: UUIDstr,
    organisation: UUIDstr,
    port_mode: PortMode,
    port_id: int,
) -> State:
    sp = ServicePortInactive.from_product_id(
        product_id=product, customer_id=organisation, status=SubscriptionLifecycle.INITIAL
    )
    sp.port.port_mode = port_mode
    sp.port.port_id = port_id

    sp = ServicePortProvisioning.from_other_lifecycle(sp, SubscriptionLifecycle.PROVISIONING)

    sp.description = f"Service Port {port_mode}"

    return {
        "subscription": sp,
        "subscription_id": sp.subscription_id,
        "subscription_description": sp.description,
    }

@create_workflow("Create Service Port", initial_input_form=initial_input_form_generator)
def create_sp() -> StepList:
    return (
        begin
        >> construct_sp_model
        >> store_process_subscription(Target.CREATE)
    )
