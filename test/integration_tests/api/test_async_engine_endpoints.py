# Copyright 2019-2026 SURF.
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

"""Endpoint tests that run against the real async engine.

Every other integration test resolves ``get_async_session`` through the shared
``test_client`` fixture, which overrides it with ``session_joined_async()`` — an
``AsyncSession`` bound to the *sync* per-test connection. That keeps fixture data and
endpoint reads inside one roll-back-able transaction, at the cost of never exercising the
async psycopg driver: greenlet context, connection pooling and lazy-load behaviour are all
the sync engine's.

The tests here drop that override, so endpoints run on ``db.async_session()`` and the async
engine's own pool. That is the whole point of the module: it is the only place where
async-only failure modes are reachable. Add a test here whenever an endpoint's behaviour
depends on actually being async rather than merely being declared ``async def``.

The failure mode covered so far is lazy loading. An ORM attribute that a query did not
eager-load, but that response serialization reads, triggers a lazy load on the event
loop's main greenlet; it reaches ``AsyncAdaptedQueuePool._checkout()`` outside
``greenlet_spawn`` and raises ``MissingGreenlet``. Under the sync binding the same read is
merely an extra round-trip, which is why the regular suite is green while production is
not.

Running on the real engine means fixture data has to be committed — the async engine reads
on its own connection and cannot see the uncommitted rows ``db_session`` stages.
``committed_session`` provides that, and every seed fixture cleans up after itself.
"""

from http import HTTPStatus

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import get_async_session
from orchestrator.core.db.models import (
    ProcessStepTable,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    WorkflowTable,
)
from orchestrator.core.domain.lifecycle import ProductLifecycle
from orchestrator.core.targets import Target
from orchestrator.core.workflow import (
    CALLBACK_TOKEN_KEY,
    DEFAULT_CALLBACK_PROGRESS_KEY,
    ProcessStatus,
    StepStatus,
)
from test.integration_tests._fixtures import JsonTestClient

WORKFLOW_NAME = "test_async_engine_endpoints_workflow"
CALLBACK_WORKFLOW_NAME = "test_async_engine_endpoints_callback_workflow"
PRODUCT_BLOCK_NAME = "AsyncEngineEndpointsBlock"
STANDALONE_PRODUCT_BLOCK_NAME = "AsyncEngineEndpointsStandaloneBlock"
PRODUCT_NAME = "AsyncEngineEndpointsProduct"
RESOURCE_TYPE_NAME = "async_engine_endpoints_resource_type"
STANDALONE_RESOURCE_TYPE_NAME = "async_engine_endpoints_standalone_resource_type"
TRACEBACK = "Traceback (most recent call last): ..."
CALLBACK_TOKEN = "async-engine-endpoints-token"  # noqa: S105


@pytest.fixture
def async_engine_test_client(fastapi_app, test_client):
    """Test client whose endpoints resolve ``get_async_session`` to the real async engine.

    Depends on ``test_client`` purely for ordering: that fixture installs the
    ``session_joined_async`` override, and this one removes it again so the endpoints fall
    back to ``db.async_session()``.
    """
    fastapi_app.dependency_overrides.pop(get_async_session, None)
    return JsonTestClient(fastapi_app)


@pytest.fixture
def committed_session(db_uri):
    """Session on its own connection whose commits are real.

    The autouse ``db_session`` fixture wraps each test in a transaction it rolls back, so
    the rows it writes are invisible to every other connection. Endpoints driven through
    ``async_engine_test_client`` read from the async engine's own pool, so their fixture
    data has to be committed — and cleaned up — explicitly.
    """
    engine = create_engine(db_uri)
    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def committed_process(committed_session):
    """Yield the id of a committed process with a workflow but no steps or subscriptions.

    ``traceback`` is populated because ``processes_filterable`` defers that column while
    ``enrich_process`` reads it, making the deferred-column load observable in the response.
    """
    workflow = WorkflowTable(
        name=WORKFLOW_NAME,
        target=Target.SYSTEM,
        description="Workflow backing the async engine endpoint tests",
        is_task=True,
    )
    process = ProcessTable(
        workflow=workflow,
        last_status=ProcessStatus.FAILED,
        assignee=Assignee.SYSTEM,
        is_task=True,
        traceback=TRACEBACK,
    )
    committed_session.add(process)
    committed_session.commit()

    yield process.process_id

    committed_session.execute(delete(ProcessTable).where(ProcessTable.process_id == process.process_id))
    committed_session.execute(delete(WorkflowTable).where(WorkflowTable.workflow_id == workflow.workflow_id))
    committed_session.commit()


@pytest.fixture
def committed_awaiting_callback_process(committed_session):
    """Yield the id of a committed process parked on an awaiting-callback step.

    The step carries the callback token in its state, which is what
    ``ensure_correct_callback_token`` checks once ``load_process`` has rebuilt the
    ``ProcessStat``. The workflow is deliberately not registered: ``load_process`` falls
    back to ``removed_workflow``, which is enough to exercise the endpoint without
    standing up the workflow engine.
    """
    workflow = WorkflowTable(
        name=CALLBACK_WORKFLOW_NAME,
        target=Target.CREATE,
        description="Workflow backing the async engine callback test",
    )
    process = ProcessTable(
        workflow=workflow,
        last_status=ProcessStatus.AWAITING_CALLBACK,
        assignee=Assignee.SYSTEM,
        is_task=False,
    )
    committed_session.add(process)
    committed_session.commit()

    # ProcessTable.steps sets cascade="delete", which switches off the default save-update
    # cascade, so the step has to be added to the session in its own right.
    committed_session.add(
        ProcessStepTable(
            process_id=process.process_id,
            name="callback_step",
            status=StepStatus.AWAITING_CALLBACK,
            state={CALLBACK_TOKEN_KEY: CALLBACK_TOKEN},
        )
    )
    committed_session.commit()

    yield process.process_id

    # process_steps.pid cascades on delete at the database level.
    committed_session.execute(delete(ProcessTable).where(ProcessTable.process_id == process.process_id))
    committed_session.execute(delete(WorkflowTable).where(WorkflowTable.workflow_id == workflow.workflow_id))
    committed_session.commit()


@pytest.fixture
def committed_product_block(committed_session):
    """Yield the id of a committed product block owning one resource type.

    Shared by the GET and PATCH tests below so the two endpoints are compared on identical
    data: same row, same response schema, same relationship — only the loader options differ.
    """
    resource_type = ResourceTypeTable(resource_type=STANDALONE_RESOURCE_TYPE_NAME, description="Resource type")
    product_block = ProductBlockTable(
        name=STANDALONE_PRODUCT_BLOCK_NAME,
        description="Original description",
        tag="AEEB",
        status=ProductLifecycle.ACTIVE,
        resource_types=[resource_type],
    )
    committed_session.add(product_block)
    committed_session.commit()

    yield product_block.product_block_id

    # Deleted through the ORM so the secondary association rows go with them.
    committed_session.delete(product_block)
    committed_session.delete(resource_type)
    committed_session.commit()


@pytest.fixture
def committed_product(committed_session):
    """Yield the id of a committed product owning one product block with one resource type."""
    resource_type = ResourceTypeTable(resource_type=RESOURCE_TYPE_NAME, description="Resource type")
    product_block = ProductBlockTable(
        name=PRODUCT_BLOCK_NAME,
        description="Product block",
        tag="AEEP",
        status=ProductLifecycle.ACTIVE,
        resource_types=[resource_type],
    )
    product = ProductTable(
        name=PRODUCT_NAME,
        description="Original description",
        product_type="AsyncEngineEndpoints",
        tag="AEEP",
        status=ProductLifecycle.ACTIVE,
        product_blocks=[product_block],
    )
    committed_session.add(product)
    committed_session.commit()

    yield product.product_id

    # Deleted through the ORM so the secondary association rows go with them.
    committed_session.delete(product)
    committed_session.delete(product_block)
    committed_session.delete(resource_type)
    committed_session.commit()


def test_patch_process_note_serializes_workflow_name(async_engine_test_client, committed_process):
    """``PATCH /api/processes/{process_id}`` must serialize ``workflow_name``.

    ``get_process_async`` eager-loads ``steps`` and ``process_subscriptions`` but not
    ``workflow``, while ``ProcessSchema`` inherits the required ``workflow_name`` field,
    which reads the ``ProcessTable.workflow.name`` property. The note itself commits before
    serialization, so the write lands and the response still fails.
    """
    response = async_engine_test_client.patch(f"/api/processes/{committed_process}", json={"note": "a note"})

    assert HTTPStatus.OK == response.status_code
    body = response.json()
    assert body["note"] == "a note"
    assert body["workflow_name"] == WORKFLOW_NAME


def test_list_processes_serializes_workflow_and_traceback(async_engine_test_client, committed_process):
    """``GET /api/processes/`` must serialize the workflow fields and the deferred traceback.

    ``processes_filterable`` loads neither ``workflow`` — which ``enrich_process`` reads for
    ``workflow_name`` and ``workflow_target`` — nor ``traceback``, which it explicitly
    defers and then reads anyway. Both are lazy loads during serialization.
    """
    response = async_engine_test_client.get("/api/processes/")

    assert HTTPStatus.OK == response.status_code
    processes = {process["process_id"]: process for process in response.json()}
    process = processes[str(committed_process)]
    assert process["workflow_name"] == WORKFLOW_NAME
    assert process["workflow_target"] == Target.SYSTEM
    assert process["traceback"] == TRACEBACK


def test_process_callback_progress_loads_workflow(
    async_engine_test_client, committed_awaiting_callback_process, committed_session
):
    """``POST /api/processes/{id}/callback/{token}/progress`` must reach ``load_process``.

    ``load_process`` opens with ``process.workflow.name``, so the endpoint fails on the
    lazy load before it can validate the callback token. The progress data is written onto
    the current step's state, which is asserted from a separate connection.
    """
    response = async_engine_test_client.post(
        f"/api/processes/{committed_awaiting_callback_process}/callback/{CALLBACK_TOKEN}/progress",
        json={"percentage": 50},
    )

    assert HTTPStatus.OK == response.status_code
    committed_session.expire_all()
    step = committed_session.scalars(
        select(ProcessStepTable).where(ProcessStepTable.process_id == committed_awaiting_callback_process)
    ).one()
    assert step.state[DEFAULT_CALLBACK_PROGRESS_KEY] == {"percentage": 50}


def test_get_process_status_tool_loads_workflow(async_engine_test_client, committed_process):
    """``POST /api/agent/get_process_status`` must reach ``load_process`` and ``enrich_process``.

    The MCP tool loads the process through ``get_process_async`` and then reads
    ``process.workflow`` twice: once inside ``load_process`` and once when building the
    response. The sibling ``list_recent_processes`` tool eager-loads ``workflow``; this one
    does not.
    """
    response = async_engine_test_client.post(
        "/api/agent/get_process_status", json={"process_id": str(committed_process)}
    )

    assert HTTPStatus.OK == response.status_code
    body = response.json()
    assert body["workflow_name"] == WORKFLOW_NAME
    assert body["traceback"] == TRACEBACK


def test_get_product_block_serializes_resource_types(async_engine_test_client, committed_product_block):
    """``GET /api/product_blocks/{product_block_id}`` eager-loads correctly and must stay green.

    This is the module's control. It exercises the same fixture, response schema and
    relationship as the PATCH below, but passes
    ``options=[selectinload(ProductBlockTable.resource_types)]`` — the pattern every async
    endpoint returning an ORM object needs. A failure here means the harness is broken
    (committed fixture data, the dropped override, the async engine itself), not the endpoint.
    """
    response = async_engine_test_client.get(f"/api/product_blocks/{committed_product_block}")

    assert HTTPStatus.OK == response.status_code
    body = response.json()
    assert body["description"] == "Original description"
    assert [rt["resource_type"] for rt in body["resource_types"]] == [STANDALONE_RESOURCE_TYPE_NAME]


def test_patch_product_block_serializes_resource_types(async_engine_test_client, committed_product_block):
    """``PATCH /api/product_blocks/{product_block_id}`` must serialize ``resource_types``.

    ``ProductBlockSchema.resource_types`` is backed by a relationship that this endpoint's
    bare ``session.get`` does not load — the one difference from the GET above, which is
    green on exactly the same data.
    """
    response = async_engine_test_client.patch(
        f"/api/product_blocks/{committed_product_block}", json={"description": "updated description"}
    )

    assert HTTPStatus.CREATED == response.status_code
    body = response.json()
    assert body["description"] == "updated description"
    assert [rt["resource_type"] for rt in body["resource_types"]] == [STANDALONE_RESOURCE_TYPE_NAME]


@pytest.mark.parametrize(
    ("method", "body", "expected_status"),
    [
        pytest.param("get", None, HTTPStatus.OK, id="get_product"),
        pytest.param("patch", {"description": "updated description"}, HTTPStatus.CREATED, id="patch_product"),
    ],
)
def test_product_endpoints_serialize_nested_resource_types(
    async_engine_test_client, committed_product, method, body, expected_status
):
    """``GET`` and ``PATCH /api/products/{product_id}`` must serialize nested resource types.

    Both go through ``_product_by_id``, which eager-loads ``product_blocks`` but not
    ``product_blocks.resource_types``. The nested ``ProductBlockSchema`` reads that
    relationship one level down during serialization. ``fetch`` (the list endpoint) chains
    the nested ``selectinload`` correctly; ``_product_by_id`` does not.
    """
    kwargs = {"json": body} if body is not None else {}
    response = getattr(async_engine_test_client, method)(f"/api/products/{committed_product}", **kwargs)

    assert expected_status == response.status_code
    product_block = response.json()["product_blocks"][0]
    assert [rt["resource_type"] for rt in product_block["resource_types"]] == [RESOURCE_TYPE_NAME]
