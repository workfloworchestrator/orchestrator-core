# Copyright 2019-2026 SURF, GÉANT, ESnet.
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
from typing import TYPE_CHECKING, Annotated

import strawberry
from strawberry import UNSET
from strawberry.federation.schema_directives import Key
from strawberry.federation.types import FieldSet
from strawberry.scalars import JSON

from oauth2_lib.strawberry import authenticated_field
from orchestrator.core.api.api_v1.endpoints.processes import get_auth_callbacks, get_steps_to_evaluate_for_rbac
from orchestrator.core.db import ProcessTable, ProductTable, db
from orchestrator.core.graphql.pagination import EMPTY_PAGE, Connection
from orchestrator.core.graphql.schemas.customer import CustomerType
from orchestrator.core.graphql.schemas.helpers import get_original_model
from orchestrator.core.graphql.schemas.product import ProductType
from orchestrator.core.graphql.types import FormUserPermissionsType, GraphqlFilter, GraphqlSort, OrchestratorInfo
from orchestrator.core.schemas.process import ProcessSchema, ProcessStepSchema
from orchestrator.core.services.processes import load_process
from orchestrator.core.settings import app_settings
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.workflows import get_workflow

if TYPE_CHECKING:
    from orchestrator.core.graphql.schemas.subscription import SubscriptionInterface
else:
    SubscriptionInterface = Annotated["SubscriptionInterface", strawberry.lazy(".subscription")]

federation_key_directives = [Key(fields=FieldSet("processId"), resolvable=UNSET)]


@strawberry.experimental.pydantic.type(model=ProcessStepSchema)
class ProcessStepType:
    step_id: strawberry.auto
    name: strawberry.auto
    status: strawberry.auto
    created_by: strawberry.auto
    executed: strawberry.auto = strawberry.field(
        deprecation_reason="Deprecated, use 'started' and 'completed' for step start and completion times"
    )
    started: strawberry.auto
    completed: strawberry.auto
    commit_hash: strawberry.auto
    state: JSON | None
    state_delta: JSON | None


@strawberry.experimental.pydantic.type(model=ProcessSchema, directives=federation_key_directives)
class ProcessType:
    process_id: strawberry.auto
    product_id: strawberry.auto
    customer_id: strawberry.auto
    workflow_id: strawberry.auto
    workflow_name: strawberry.auto
    workflow_target: strawberry.auto
    assignee: strawberry.auto
    failed_reason: strawberry.auto
    last_step: strawberry.auto
    last_status: strawberry.auto
    created_by: strawberry.auto
    started_at: strawberry.auto
    last_modified_at: strawberry.auto
    is_task: strawberry.auto
    steps: strawberry.auto
    form: JSON | None
    current_state: JSON | None
    note: str | None

    @strawberry.field(description="Get traceback")  # type: ignore
    def traceback(self) -> str | None:
        model = get_original_model(self, ProcessTable)
        return model.traceback

    @authenticated_field(description="Returns the associated product")  # type: ignore
    def product(self) -> ProductType | None:
        if self.product_id and (product := db.session.get(ProductTable, self.product_id)):
            return ProductType.from_pydantic(product)
        return None

    @strawberry.field(description="Returns customer of a subscription")  # type: ignore
    def customer(self) -> CustomerType:
        return CustomerType(
            customer_id=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
        )

    @strawberry.field(description="Returns user permissions for operations on this process")  # type: ignore
    async def user_permissions(self, info: OrchestratorInfo) -> FormUserPermissionsType:
        oidc_user = await info.context.get_current_user

        # Note that workflow and pstat.workflow can differ here!
        workflow = get_workflow(self.workflow_name)
        pstat = load_process(db.session.get(ProcessTable, self.process_id))  # type: ignore[arg-type]

        steps = get_steps_to_evaluate_for_rbac(pstat)
        auth_resume, auth_retry = get_auth_callbacks(steps, workflow)

        resume_context = AuthContext(user=oidc_user, workflow=pstat.workflow, step=steps[-1], action="resume_workflow")
        retry_context = AuthContext(user=oidc_user, workflow=pstat.workflow, step=steps[-1], action="retry_workflow")

        return FormUserPermissionsType(
            retryAllowed=bool(auth_retry and await auth_retry(resume_context)),
            resumeAllowed=bool(auth_resume and await auth_resume(retry_context)),
        )

    @authenticated_field(description="Returns list of subscriptions of the process")  # type: ignore
    async def subscriptions(
        self,
        info: OrchestratorInfo,
        filter_by: list[GraphqlFilter] | None = None,
        sort_by: list[GraphqlSort] | None = None,
        first: int = 10,
        after: int = 0,
    ) -> Connection[SubscriptionInterface]:
        from orchestrator.core.graphql.resolvers.subscription import resolve_subscriptions

        subscription_ids = [str(s.subscription_id) for s in self._original_model.subscriptions]  # type: ignore
        if not subscription_ids:
            return EMPTY_PAGE
        filter_by_with_related_subscriptions = (filter_by or []) + [
            GraphqlFilter(field="subscriptionId", value="|".join(subscription_ids))
        ]
        return await resolve_subscriptions(info, filter_by_with_related_subscriptions, sort_by, first, after)
