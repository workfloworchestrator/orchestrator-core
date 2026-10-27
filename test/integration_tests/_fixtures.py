# Copyright 2019-2026 SURF, GÉANT.
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

"""Integration-test fixtures specific to orchestrator-core.

The database, app and test client fixtures come from the :mod:`orchestrator.core.testing.fixtures` plugin, the
same one downstream orchestrators use. This module adds the hooks, products, subscriptions, scheduler and Celery
fixtures that only orchestrator-core's own tests need. ``test/unit_tests/conftest.py`` is intentionally
boring; it does not import anything from this module.
"""

import contextlib
import datetime
import os
import time
import uuid
from contextlib import contextmanager
from uuid import uuid4

import pytest
import redis
import structlog
from celery import Celery
from sqlalchemy import select, text

from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import (
    ProcessSubscriptionTable,
    ProcessTable,
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionCustomerDescriptionTable,
    SubscriptionMetadataTable,
    WorkflowTable,
    db,
)
from orchestrator.core.db.models import WorkflowApschedulerJob
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.core.domain.base import ProductBlockModel
from orchestrator.core.schedules.scheduler import get_scheduler
from orchestrator.core.schedules.service import run_start_workflow_scheduler_task
from orchestrator.core.services.tasks import (
    NEW_TASK,
    NEW_WORKFLOW,
    RESUME_TASK,
    RESUME_WORKFLOW,
    initialise_celery,
    register_custom_serializer,
)
from orchestrator.core.services.worker_status_monitor import get_worker_status_monitor
from orchestrator.core.services.workflows import get_workflow_by_name
from orchestrator.core.settings import AppSettings, app_settings
from orchestrator.core.targets import Target
from orchestrator.core.testing import WorkflowInstanceForTests
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.utils.redis_client import create_redis_client
from orchestrator.core.workflow import ProcessStatus
from test.integration_tests._async_session import session_joined_async
from test.integration_tests.fixtures.processes import (  # noqa: F401
    mocked_processes,
    mocked_processes_resumeall,
    test_workflow,
    test_workflow_soft_deleted,
)
from test.integration_tests.fixtures.products.product_blocks.product_block_list_nested import (  # noqa: F401
    test_product_block_list_nested,
    test_product_block_list_nested_db_in_use_by_block,
)
from test.integration_tests.fixtures.products.product_blocks.product_block_one import (  # noqa: F401
    test_product_block_one,
    test_product_block_one_db,
)
from test.integration_tests.fixtures.products.product_blocks.product_block_one_nested import (  # noqa: F401
    test_product_block_one_nested,
    test_product_block_one_nested_db_in_use_by_block,
)
from test.integration_tests.fixtures.products.product_blocks.product_block_with_list_union import (  # noqa: F401
    test_product_block_with_list_union,
    test_product_block_with_list_union_db,
)
from test.integration_tests.fixtures.products.product_blocks.product_block_with_union import (  # noqa: F401
    test_product_block_with_union,
    test_product_block_with_union_db,
)
from test.integration_tests.fixtures.products.product_blocks.product_sub_block_one import (  # noqa: F401
    test_product_sub_block_one,
    test_product_sub_block_one_db,
)
from test.integration_tests.fixtures.products.product_blocks.product_sub_block_two import (  # noqa: F401
    test_product_sub_block_two,
    test_product_sub_block_two_db,
)
from test.integration_tests.fixtures.products.product_types.product_type_list_nested import (  # noqa: F401
    test_product_list_nested,
    test_product_model_list_nested,
    test_product_type_list_nested,
)
from test.integration_tests.fixtures.products.product_types.product_type_list_union import (  # noqa: F401
    test_product_list_union,
    test_product_type_list_union,
)
from test.integration_tests.fixtures.products.product_types.product_type_list_union_overlap import (  # noqa: F401
    sub_list_union_overlap_subscription_1,
    test_product_list_union_overlap,
    test_product_type_list_union_overlap,
)
from test.integration_tests.fixtures.products.product_types.product_type_one import (  # noqa: F401
    product_one_subscription_1,
    test_product_model,
    test_product_one,
    test_product_type_one,
)
from test.integration_tests.fixtures.products.product_types.product_type_one_nested import (  # noqa: F401
    test_product_model_nested,
    test_product_one_nested,
    test_product_type_one_nested,
)
from test.integration_tests.fixtures.products.product_types.product_type_sub_list_union import (  # noqa: F401
    product_sub_list_union_subscription_1,
    test_product_sub_list_union,
    test_product_type_sub_list_union,
)
from test.integration_tests.fixtures.products.product_types.product_type_sub_one import (  # noqa: F401
    sub_one_subscription_1,
    test_product_sub_one,
    test_product_type_sub_one,
)
from test.integration_tests.fixtures.products.product_types.product_type_sub_two import (  # noqa: F401
    sub_two_subscription_1,
    test_product_sub_two,
    test_product_type_sub_two,
)
from test.integration_tests.fixtures.products.product_types.product_type_sub_union import (  # noqa: F401
    test_union_sub_product,
    test_union_type_sub_product,
)
from test.integration_tests.fixtures.products.product_types.product_type_union import (  # noqa: F401
    test_union_product,
    test_union_type_product,
)
from test.integration_tests.fixtures.products.product_types.subscription_relations import (  # noqa: F401
    factory_subscription_with_nestings_depends_on,
    factory_subscription_with_nestings_in_use_by,
    test_product_model_list_nested_product_type_one,
    test_product_model_list_nested_product_type_two,
)
from test.integration_tests.fixtures.products.resource_types import (  # noqa: F401
    resource_type_enum,
    resource_type_int,
    resource_type_int_2,
    resource_type_list,
    resource_type_str,
)
from test.integration_tests.fixtures.workflows import (  # noqa: F401
    sample_workflow,
    sample_workflow_with_suspend,
)
from test.integration_tests.workflows.shared.test_validate_subscriptions import validation_workflow

logger = structlog.getLogger(__name__)

CUSTOMER_ID: str = "2f47f65a-0911-e511-80d0-005056956c1a"

CLI_OPT_MONITOR_SQLALCHEMY = "--monitor-sqlalchemy"


def pytest_addoption(parser):
    """Define custom pytest commandline options."""
    parser.addoption(
        CLI_OPT_MONITOR_SQLALCHEMY,
        action="store_true",
        default=False,
        help=(
            "When set, activate query monitoring for tests instrumented with monitor_sqlalchemy. "
            "Note that this has a certain overhead on execution time."
        ),
    )


@pytest.fixture(scope="session")
def joined_async_session():
    """Join the per-test transaction, and fail on ORM loads an ``AsyncSession`` could not have performed."""
    return session_joined_async


@pytest.fixture(scope="session")
def load_scheduled_tasks(database):
    with get_scheduler():
        pass


def reset_active_threadpool_jobs() -> None:
    """Reset the threadpool active-job counter to zero.

    Used in teardown when a test leaked a job that never finished, so the leaked count does not fail
    every later test on the same xdist worker (#2039).
    """
    import orchestrator.core.services.processes as processes

    with processes._active_jobs_lock:
        processes._active_threadpool_jobs = 0


def wait_for_no_active_threadpool_jobs(timeout: float = 5.0, interval: float = 0.05) -> int:
    """Wait for in-flight threadpool jobs to finish, returning the number still active.

    Jobs that are merely finishing (rather than stuck) decrement the counter shortly after a test
    ends. Only a job that never returns survives the timeout, in which case the counter is reset so
    the leak does not fail every later test on the same xdist worker (#2039).

    Args:
        timeout: Maximum number of seconds to wait for jobs to finish.
        interval: Number of seconds to sleep between checks.

    Returns:
        The number of jobs still active after waiting (0 when none leaked).
    """
    import orchestrator.core.services.processes as processes

    deadline = time.monotonic() + timeout
    while (remaining := processes.get_active_threadpool_jobs_count()) != 0 and time.monotonic() < deadline:
        time.sleep(interval)

    if remaining != 0:
        reset_active_threadpool_jobs()
    return remaining


def wait_for_running_jobs_count(expected: int = 0, timeout: float = 10.0, interval: float = 0.05) -> None:
    """Refresh the monitor until its running jobs count equals ``expected``, or fail after ``timeout``.

    The monitor caches the running jobs count and only refreshes it periodically. Tests that assert on
    the count would otherwise read a stale value left behind by a previous test's background job (#2039).

    The monitor is resolved through ``get_worker_status_monitor()``, the same accessor the API and
    metrics use, so the helper always refreshes the monitor that production reads from.

    Args:
        expected: The count to wait for.
        timeout: Maximum number of seconds to wait.
        interval: Number of seconds to sleep between refreshes.

    Raises:
        AssertionError: If the count does not reach ``expected`` within ``timeout``.
    """
    deadline = time.monotonic() + timeout
    while True:
        monitor = get_worker_status_monitor()
        monitor._refresh_once()
        count = monitor.get_running_jobs_count()
        if count == expected:
            return
        if time.monotonic() >= deadline:
            raise AssertionError(f"running jobs count is {count}, expected {expected} after {timeout}s")
        time.sleep(interval)


@pytest.fixture
def generic_resource_type_1():
    rt = ResourceTypeTable(description="Resource Type one", resource_type="rt_1")
    db.session.add(rt)
    db.session.commit()

    return rt


@pytest.fixture
def generic_resource_type_2():
    rt = ResourceTypeTable(description="Resource Type two", resource_type="rt_2")
    db.session.add(rt)
    db.session.commit()
    return rt


@pytest.fixture
def generic_resource_type_3():
    rt = ResourceTypeTable(description="Resource Type three", resource_type="rt_3")
    db.session.add(rt)
    db.session.commit()

    return rt


@pytest.fixture
def generic_product_block_1(generic_resource_type_1):
    pb = ProductBlockTable(
        name="PB_1",
        description="Generic Product Block 1",
        tag="PB1",
        status="active",
        resource_types=[generic_resource_type_1],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_product_block_2(generic_resource_type_2, generic_resource_type_3):
    pb = ProductBlockTable(
        name="PB_2",
        description="Generic Product Block 2",
        tag="PB2",
        status="active",
        resource_types=[generic_resource_type_2, generic_resource_type_3],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_product_block_3(generic_resource_type_2):
    pb = ProductBlockTable(
        name="PB_3",
        description="Generic Product Block 3",
        tag="PB3",
        status="active",
        resource_types=[generic_resource_type_2],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_referencing_product_block_1(generic_resource_type_1, generic_root_product_block_1):
    pb = ProductBlockTable(
        name="PB_1",
        description="Generic Referencing Product Block 1",
        tag="PB1",
        status="active",
        resource_types=[generic_resource_type_1],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
        depends_on_block_relations=[generic_root_product_block_1],
        in_use_by_block_relations=[],
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_root_product_block_1(generic_resource_type_3):
    pb = ProductBlockTable(
        name="PB_Root_1",
        description="Generic Root Product Block 1",
        tag="PBR1",
        status="active",
        resource_types=[generic_resource_type_3],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
        in_use_by_block_relations=[],
        depends_on_block_relations=[],
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_product_block_chain(generic_resource_type_3):

    pb_2 = ProductBlockTable(
        name="PB_Chained_2",
        description="Generic Product Block 2",
        tag="PB2",
        status="active",
        resource_types=[generic_resource_type_3],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
    )
    pb_1 = ProductBlockTable(
        name="PB_Chained_1",
        description="Generic Product Block 1",
        tag="PB1",
        status="active",
        resource_types=[generic_resource_type_3],
        created_at=datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00"),
        depends_on=[pb_2],
    )
    db.session.add_all([pb_1, pb_2])
    db.session.commit()
    return pb_1, pb_2


@pytest.fixture
def generic_product_1(generic_product_block_1, generic_product_block_2):
    workflow = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))
    p = ProductTable(
        name="Product 1",
        description="Generic Product One",
        product_type="Generic",
        status="active",
        tag="GEN1",
        product_blocks=[generic_product_block_1, generic_product_block_2],
        workflows=[workflow],
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def generic_product_2(generic_product_block_3):
    workflow = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))

    p = ProductTable(
        name="Product 2",
        description="Generic Product Two",
        product_type="Generic",
        status="active",
        tag="GEN2",
        product_blocks=[generic_product_block_3],
        workflows=[workflow],
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def generic_product_3(generic_product_block_2):
    p = ProductTable(
        name="Product 3",
        description="Generic Product Three",
        product_type="Generic",
        status="active",
        tag="GEN3",
        product_blocks=[generic_product_block_2],
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def generic_product_4(generic_product_block_chain):
    pb_1, pb_2 = generic_product_block_chain
    p = ProductTable(
        name="Product 4",
        description="Generic Product Four",
        product_type="Generic",
        status="active",
        tag="GEN3",
        product_blocks=[pb_1],
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def generic_product_block_type_1(generic_product_block_1):
    class GenericProductBlockOneInactive(ProductBlockModel, product_block_name="PB_1"):
        rt_1: str | None = None

    class GenericProductBlockOne(GenericProductBlockOneInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        rt_1: str

    return GenericProductBlockOneInactive, GenericProductBlockOne


@pytest.fixture
def generic_product_block_type_2(generic_product_block_2):
    class GenericProductBlockTwoInactive(ProductBlockModel, product_block_name="PB_2"):
        rt_2: int | None = None
        rt_3: str | None = None

    class GenericProductBlockTwo(GenericProductBlockTwoInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        rt_2: int
        rt_3: str

    return GenericProductBlockTwoInactive, GenericProductBlockTwo


@pytest.fixture
def generic_product_block_type_3(generic_product_block_3):
    class GenericProductBlockThreeInactive(ProductBlockModel, product_block_name="PB_3"):
        rt_2: int | None = None

    class GenericProductBlockThree(GenericProductBlockThreeInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        rt_2: int

    return GenericProductBlockThreeInactive, GenericProductBlockThree


@pytest.fixture
def generic_product_type_1(generic_product_1, generic_product_block_type_1, generic_product_block_type_2):
    GenericProductBlockOneInactive, GenericProductBlockOne = generic_product_block_type_1
    GenericProductBlockTwoInactive, GenericProductBlockTwo = generic_product_block_type_2
    # Test Product domain models

    class GenericProductOneInactive(SubscriptionModel, is_base=True):
        pb_1: GenericProductBlockOneInactive
        pb_2: GenericProductBlockTwoInactive

    class GenericProductOne(GenericProductOneInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        pb_1: GenericProductBlockOne
        pb_2: GenericProductBlockTwo

    SUBSCRIPTION_MODEL_REGISTRY["Product 1"] = GenericProductOne

    yield GenericProductOneInactive, GenericProductOne

    del SUBSCRIPTION_MODEL_REGISTRY["Product 1"]


@pytest.fixture
def generic_product_type_2(generic_product_2, generic_product_block_type_3):
    GenericProductBlockThreeInactive, GenericProductBlockThree = generic_product_block_type_3

    class GenericProductTwoInactive(SubscriptionModel, is_base=True):
        pb_3: GenericProductBlockThreeInactive

    class GenericProductTwo(GenericProductTwoInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        pb_3: GenericProductBlockThree

    SUBSCRIPTION_MODEL_REGISTRY["Product 2"] = GenericProductTwo

    yield GenericProductTwoInactive, GenericProductTwo

    del SUBSCRIPTION_MODEL_REGISTRY["Product 2"]


@pytest.fixture
def product_type_1_subscription_factory(generic_product_1, generic_product_type_1):
    def subscription_create(
        description="Generic Subscription One",
        start_date="2023-05-24T00:00:00+00:00",
        rt_1="Value1",
        rt_2=42,
        rt_3="Value2",
    ):
        GenericProductOneInactive, _ = generic_product_type_1
        gen_subscription = GenericProductOneInactive.from_product_id(
            generic_product_1.product_id, customer_id=CUSTOMER_ID, insync=True
        )
        gen_subscription.pb_1.rt_1 = rt_1
        gen_subscription.pb_2.rt_2 = rt_2
        gen_subscription.pb_2.rt_3 = rt_3
        gen_subscription = SubscriptionModel.from_other_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
        gen_subscription.description = description
        gen_subscription.start_date = start_date
        gen_subscription.save()

        gen_subscription_metadata = SubscriptionMetadataTable()
        gen_subscription_metadata.subscription_id = gen_subscription.subscription_id
        gen_subscription_metadata.metadata_ = {"description": "Some metadata description"}
        db.session.add(gen_subscription_metadata)
        db.session.commit()
        return str(gen_subscription.subscription_id)

    return subscription_create


@pytest.fixture
def product_type_1_subscriptions_factory(product_type_1_subscription_factory):
    def subscriptions_create(amount=1):
        return [
            product_type_1_subscription_factory(
                description=f"Subscription {i}",
                start_date=(
                    datetime.datetime.fromisoformat("2023-05-24T00:00:00+00:00") + datetime.timedelta(days=i)
                ).replace(tzinfo=datetime.UTC),
            )
            for i in range(0, amount)
        ]

    return subscriptions_create


@pytest.fixture
def generic_subscription_1(product_type_1_subscription_factory):
    return product_type_1_subscription_factory()


@pytest.fixture
def generic_subscription_2(generic_product_2, generic_product_type_2):
    GenericProductTwoInactive, _ = generic_product_type_2
    gen_subscription = GenericProductTwoInactive.from_product_id(
        generic_product_2.product_id, customer_id=CUSTOMER_ID, insync=True
    )
    gen_subscription.pb_3.rt_2 = 42
    gen_subscription = SubscriptionModel.from_other_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
    gen_subscription.description = "Generic Subscription Two"
    gen_subscription.save()
    db.session.commit()

    return str(gen_subscription.subscription_id)


@pytest.fixture
def validation_workflow_instance():
    with WorkflowInstanceForTests(validation_workflow, "validation_workflow") as ctx:
        yield ctx


@pytest.fixture
def validation_workflow_process_instance(generic_subscription_1, validation_workflow_instance):
    """Fixture to create a ProcessSubscriptionTable entry for testing."""
    start_time = datetime.datetime.now(datetime.UTC)
    process_id = uuid4()
    process = ProcessTable(
        process_id=process_id,
        workflow_id=validation_workflow_instance.workflow_id,
        last_status="completed",
        last_step="Modify",
        started_at=start_time,
        last_modified_at=start_time + datetime.timedelta(seconds=10),
        assignee=Assignee.SYSTEM,
        is_task=True,
    )

    process_subscription = ProcessSubscriptionTable(
        subscription_id=generic_subscription_1,
        process_id=process_id,
        workflow_target=validation_workflow_instance.target,
        created_at=start_time,
    )

    db.session.add(process)
    db.session.add(process_subscription)
    db.session.commit()
    return process, process_subscription


@pytest.fixture
def make_customer_description():
    def customer_description(subscription_id, customer_id, description):
        model = SubscriptionCustomerDescriptionTable(
            subscription_id=subscription_id, customer_id=customer_id, description=description
        )
        db.session.add(model)
        db.session.commit()
        return model

    return customer_description


@pytest.fixture
def cache_fixture(monkeypatch):
    """Fixture to enable domain model caching and cleanup keys added to the list."""
    with monkeypatch.context():
        cache = create_redis_client(app_settings.CACHE_URI.get_secret_value())
        # Clear cache before using this fixture
        cache.flushdb()

        to_cleanup = []

        yield to_cleanup

        for key in to_cleanup:
            try:
                cache.delete(key)
            except Exception as exc:
                print("failed to delete cache key", key, str(exc))  # noqa: T001, T201


def do_refresh_subscriptions_search_view():
    db.session.execute(text("REFRESH MATERIALIZED VIEW subscriptions_search"))


@pytest.fixture
def refresh_subscriptions_search_view():
    do_refresh_subscriptions_search_view()


@pytest.fixture
def monitor_sqlalchemy(pytestconfig, request, capsys):
    """Can be used to inspect the number of sqlalchemy queries made by part of the code.

    Usage: include this fixture, it returns a context manager. Wrap this around the code you want to inspect.
    The inspection is disabled unless you explicitly enable it.
    To enable it pass the cli option --monitor-sqlalchemy (see CLI_OPT_MONITOR_SQLALCHEMY).

    Example:
        def mytest(monitor_sqlalchemy):
            # given
            ... some setup

            # when
            with monitor_sqlalchemy():
                ... something that does db queries
    """
    from orchestrator.core.db.listeners import disable_listeners, monitor_sqlalchemy_queries

    @contextlib.contextmanager
    def monitor_queries():
        monitor_sqlalchemy_queries()
        before = db.session.connection().info.copy()

        yield

        after = db.session.connection().info.copy()
        disable_listeners()

        estimated_queries = after["queries_completed"] - before.get("queries_completed", 0)
        estimated_query_time = after["query_time_spent"] - before.get("query_time_spent", 0.0)

        with capsys.disabled():
            print(f"\n{request.node.nodeid} performed {estimated_queries} queries in {estimated_query_time:.2f}s\n")

    @contextlib.contextmanager
    def noop():
        yield

    if pytestconfig.getoption(CLI_OPT_MONITOR_SQLALCHEMY):
        yield monitor_queries
    else:
        yield noop


@pytest.fixture
def scheduler_with_jobs():
    def _create(
        job_name: str = "Test Job",
        workflow_name: str = "task_clean_up_tasks",
        schedule_id: str = str(uuid.uuid4()),
        trigger: str = "interval",
        trigger_kwargs: dict | None = None,
    ):
        with get_scheduler() as scheduler:
            # First remove all existing jobs
            if trigger_kwargs is None:
                trigger_kwargs = {"hours": 1}

            scheduler.add_job(
                func=run_start_workflow_scheduler_task,
                trigger=trigger,
                id=schedule_id,
                name=job_name,
                kwargs={"workflow_name": workflow_name},
                **trigger_kwargs,
            )

            return scheduler

    return _create


@pytest.fixture
def clear_all_scheduler_jobs():
    """Fixture to clear all scheduler jobs before and after the test."""

    def _clear():
        with get_scheduler() as scheduler:
            # Clear all jobs before the test
            for job in scheduler.get_jobs():
                scheduler.remove_job(job.id)

    return _clear


@pytest.fixture
def create_schedules_via_api(test_client, scheduler_with_jobs):
    def _create(
        job_name: str = "Test Job",
        workflow_name: str = "task_resume_workflows",
        schedule_id: str = str(uuid.uuid4()),
        trigger: str = "interval",
        trigger_kwargs: dict | None = None,
    ):
        workflow = get_workflow_by_name(workflow_name)
        if not workflow:
            return

        scheduler_with_jobs(
            job_name=job_name,
            workflow_name=workflow_name,
            schedule_id=schedule_id,
            trigger=trigger,
            trigger_kwargs=trigger_kwargs,
        )

        workflows_apscheduler_job = WorkflowApschedulerJob(workflow_id=workflow.workflow_id, schedule_id=schedule_id)
        db.session.add(workflows_apscheduler_job)
        db.session.commit()

    return _create


# ---------------------------------------------------------------------------
# Celery integration support
#
# Tests under test/integration_tests/test_with_pytest_celery.py use these
# fixtures together with the pytest-celery plugin to spin up a Celery worker
# backed by Redis. They have always been part of integration_tests/conftest.py
# and remain here unchanged.
# ---------------------------------------------------------------------------


# Singleton Redis connection pool
_redis_pool: redis.ConnectionPool | None = None


def get_redis_connection():
    """Get Redis connection from pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
            max_connections=5,  # Limit connections for testing
        )
    return redis.Redis(connection_pool=_redis_pool)


@contextmanager
def redis_client():
    """Context manager for Redis connections."""
    client = get_redis_connection()
    try:
        yield client
    finally:
        client.close()


def validate_redis_connection():
    """Validate Redis connection is available."""
    try:
        with redis_client() as client:
            return client.ping()
    except redis.ConnectionError:
        return False


class TestOrchestratorCelery(Celery):
    """Test-specific Celery application class with pre-configured settings."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set test configuration during initialization
        self.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            task_serializer="orchestrator-json",
            accept_content=["orchestrator-json", "json"],
            result_serializer="json",
            task_track_started=True,
        )

    def on_init(self) -> None:
        """Initialize test settings and create mock OrchestratorCore."""
        test_settings = AppSettings()
        test_settings.TESTING = True

        class MockOrchestratorCore:
            def __init__(self, base_settings):
                self.settings = base_settings
                self.broadcast_thread = type("DummyThread", (), {"start": lambda: None, "stop": lambda: None})()

        app = MockOrchestratorCore(base_settings=test_settings)  # noqa:  F841


@pytest.fixture
def setup_test_process(request, db_session):
    """Create test workflow and process for celery tests.

    Args:
        request: The pytest request object, may contain 'param' for status
        db_session: Database session fixture

    Returns:
        tuple: (workflow, process) The created test workflow and process
    """

    def _create_process(status=ProcessStatus.CREATED):
        workflow = WorkflowTable(
            name=f"Test Workflow {uuid4()}", description="Test workflow for celery", target=Target.SYSTEM
        )
        db.session.add(workflow)
        db.session.commit()

        process = ProcessTable(
            workflow_id=workflow.workflow_id, last_status=status, assignee=Target.SYSTEM, process_id=uuid4()
        )
        db.session.add(process)
        db.session.commit()

        return workflow, process

    if hasattr(request, "param"):
        return _create_process(request.param)
    return _create_process()


@pytest.fixture
def setup_base_workflows(db_session):
    """Create base workflows needed for tests.

    Returns:
        WorkflowTable: The created or existing modify_note workflow
    """

    # Check if workflow exists
    existing = db.session.scalar(select(WorkflowTable).where(WorkflowTable.name == "modify_note"))

    if not existing:
        workflow = WorkflowTable(name="modify_note", description="Test workflow for modify_note", target=Target.SYSTEM)
        db.session.add(workflow)
        db.session.commit()
        return workflow

    return existing


@pytest.fixture(scope="session")
def celery_config():
    """Optimized Celery configuration for testing."""
    if not validate_redis_connection():
        pytest.skip("Redis is not available")

    return {
        "broker_url": os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        "broker_connection_pool_limit": 2,
        "result_backend_connection_pool_limit": 2,
        "task_always_eager": True,  # Run tasks synchronously for testing
        "task_eager_propagates": True,
        "task_serializer": "orchestrator-json",
        "result_serializer": "json",
        "accept_content": ["orchestrator-json", "json"],
        "task_routes": {
            NEW_TASK: {"queue": "test_tasks"},
            NEW_WORKFLOW: {"queue": "test_workflows"},
            RESUME_TASK: {"queue": "test_tasks"},
            RESUME_WORKFLOW: {"queue": "test_workflows"},
        },
        "worker_prefetch_multiplier": 1,
        "worker_max_tasks_per_child": 10,  # Increased for better performance
        "task_acks_late": False,  # Disable late acks for testing
        "broker_connection_retry": False,  # Disable retries for faster failures
        "broker_connection_timeout": 2,  # Reduced timeout
        "result_expires": 60,  # Reduced expiry time for test results
        "broker_heartbeat": 0,
        "worker_send_task_events": False,
        "event_queue_expires": 10,
        "worker_disable_rate_limits": True,
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    """Optimized worker configuration for testing."""
    return {
        "perform_ping_check": False,
        "queues": ["test_tasks", "test_workflows"],
        "concurrency": 1,
        "pool": "solo",
        "without_heartbeat": True,
        "without_mingle": True,
        "without_gossip": True,
        "shutdown_timeout": 0,
    }


@pytest.fixture(scope="session")
def register_celery_tasks(celery_session_app):
    """Register test tasks with the Celery application."""
    tasks = {}

    @celery_session_app.task(name=NEW_TASK)  # type: ignore[untyped-decorator]
    def new_task(process_id: str, user: str = "test") -> str:
        return f"Started new process {process_id}"

    tasks[NEW_TASK] = new_task

    @celery_session_app.task(name=NEW_WORKFLOW)  # type: ignore[untyped-decorator]
    def new_workflow(process_id: str, user: str = "test") -> str:
        return f"Started new workflow {process_id}"

    tasks[NEW_WORKFLOW] = new_workflow

    @celery_session_app.task(name=RESUME_TASK)  # type: ignore[untyped-decorator]
    def resume_task(process_id: str, user: str = "test") -> str:
        return f"Resumed task {process_id}"

    tasks[RESUME_TASK] = resume_task

    @celery_session_app.task(name=RESUME_WORKFLOW)  # type: ignore[untyped-decorator]
    def resume_workflow(process_id: str, user: str = "test") -> str:
        if process_id is None:
            raise ValueError("process_id cannot be None")
        return f"Resumed workflow {process_id}"

    tasks[RESUME_WORKFLOW] = resume_workflow

    return tasks


@pytest.fixture(scope="session")
def celery_includes():
    """Specify modules to import for task registration."""
    return ["orchestrator.core.services.tasks"]


@pytest.fixture
def celery_timeout():
    """Consistent timeout value for all tests."""
    return 10


@pytest.fixture
def setup_test_celery(celery_session_app, monkeypatch):
    """Setup and teardown for Celery tests."""
    # Reset Celery app
    monkeypatch.setattr("orchestrator.core.services.tasks._celery", None)

    # Initialize Celery
    register_custom_serializer()
    initialise_celery(celery_session_app)

    yield

    # Cleanup
    if _redis_pool:
        with redis_client() as client:
            client.flushdb()  # Clean test data
        _redis_pool.disconnect()  # Close all connections
