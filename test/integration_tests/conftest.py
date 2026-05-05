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

"""Integration-test conftest.

Owns every fixture that requires Postgres, Redis, FastAPI app bootstrap, the
scheduler or the Celery broker. ``test/unit_tests/conftest.py`` is intentionally
boring; it does not import anything from this module.

Service endpoints are resolved by :func:`provide_services` (env vars first,
testcontainers fallback). The resolution runs at module import — *before* any
``orchestrator.*`` import — so that pydantic-settings reads the correct
``DATABASE_URI`` / ``CACHE_URI`` and module-level cache clients in
``orchestrator.core.schedules.service`` and ``orchestrator.core.utils.redis``
bind to the right Redis instance.
"""

# isort: off
# Resolve Postgres + Redis BEFORE importing any orchestrator module.
# ``_session_setup`` imports ``provide_services`` and enters its context at
# module load, exporting ``DATABASE_URI`` / ``CACHE_URI`` into ``os.environ``
# for the testcontainers fallback (no-op in env-var mode). ``app_settings`` is
# constructed during the orchestrator imports below, so it picks up the
# correct values regardless of which mode is active. Do not let import sorters
# move this past the ``orchestrator.*`` imports — the ordering is load-bearing.
from test.integration_tests._session_setup import SERVICES as _INTEGRATION_SERVICES
from test.integration_tests._session_setup import SERVICES_STACK as _SERVICES_STACK

# isort: on

import contextlib
import datetime
import os
import typing
import uuid
from contextlib import closing, contextmanager
from copy import copy
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
import redis
import requests
import structlog
from alembic import command
from alembic.config import Config
from celery import Celery
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import close_all_sessions, sessionmaker
from starlette.testclient import TestClient

from orchestrator.core import OrchestratorCore
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
from orchestrator.core.db.database import ENGINE_ARGUMENTS, SESSION_ARGUMENTS, BaseModel, Database, SearchQuery
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
from orchestrator.core.services.workflows import get_workflow_by_name
from orchestrator.core.settings import AppSettings, SecretPostgresDsn, app_settings
from orchestrator.core.targets import Target
from orchestrator.core.types import SubscriptionLifecycle
from orchestrator.core.utils.json import json_dumps
from orchestrator.core.utils.redis_client import create_redis_client
from orchestrator.core.workflow import ProcessStatus
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
from test.integration_tests.fixtures.services import patch_app_settings
from test.integration_tests.fixtures.workflows import (  # noqa: F401
    sample_workflow,
    sample_workflow_with_suspend,
)
from test.integration_tests.workflows import WorkflowInstanceForTests
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


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 — pytest hook signature
    """Tear down testcontainers (no-op in env-var mode) at session end."""
    _SERVICES_STACK.close()


@pytest.fixture(scope="session")
def integration_services():
    """Expose the session-wide ``ServiceURIs`` for tests that need them.

    Resolution happened at conftest import time (see ``_session_setup``); this
    fixture is a thin pytest-friendly wrapper. ``app_settings`` is also patched
    defensively here in case ``orchestrator.core.settings`` was imported before
    ``_session_setup`` ran.
    """
    patch_app_settings(_INTEGRATION_SERVICES)
    return _INTEGRATION_SERVICES


def run_migrations(db_uri: str) -> None:
    """Configure the alembic context and run the migrations.

    Each test will start with a clean database. This a heavy operation but ensures that our database is clean and
    tests run within their own context.

    Args:
        db_uri: The database uri configuration to run the migration on.

    Returns:
        None

    """
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)))
    os.environ["DATABASE_URI"] = db_uri
    app_settings.DATABASE_URI = SecretPostgresDsn(db_uri)  # type: ignore
    alembic_cfg = Config(file_=os.path.join(path, "../../orchestrator/core/migrations/alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(path, "../../orchestrator/core/migrations"))
    alembic_cfg.set_main_option(
        "version_locations",
        f"{os.path.join(path, '../../orchestrator/core/migrations/versions/schema')}",
    )
    alembic_cfg.set_main_option("sqlalchemy.url", db_uri)
    command.upgrade(alembic_cfg, "heads")


def make_db_uri(worker_id, base_uri):
    if worker_id == "master":
        # pytest is being run without any workers
        print(f"No workers, final DATABASE_URI is {base_uri!r}")
        return base_uri

    url = make_url(base_uri)
    if hasattr(url, "set"):
        url = url.set(database=f"{url.database}-{worker_id}")
    else:
        url.database = f"{url.database}-{worker_id}"

    worker_database_uri = url.render_as_string(hide_password=False)
    print(f"Final DATABASE_URI for worker {worker_id!r} is {worker_database_uri!r}")
    return worker_database_uri


@pytest.fixture(scope="session")
def db_uri(worker_id, integration_services):
    """Ensure each pytest thread has its database.

    When running tests with the -j option make sure each test worker is isolated within its own database.

    Args:
        worker_id: the worker id
        integration_services: resolved Postgres + Redis URIs (env or testcontainers).

    Returns:
        Database uri to be used in the test thread

    """
    session_db_uri = make_db_uri(worker_id, integration_services.database_uri)

    with patch.object(app_settings, "DATABASE_URI", SecretPostgresDsn(session_db_uri)):
        yield session_db_uri


@pytest.fixture(scope="session")
def database(db_uri):
    """Create database and run migrations and cleanup afterward.

    Args:
        db_uri: fixture for providing the application context and an initialized database. Although specifying this
            as an explicit parameter is redundant due to `fastapi_app`'s autouse setting, we have made the dependency
            explicit here for the purpose of documentation.

    """
    db.update(Database(db_uri))
    url = make_url(db_uri)
    db_to_create = url.database
    if hasattr(url, "set"):
        url = url.set(database="postgres")
    else:
        url.database = "postgres"
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with closing(engine.connect()) as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_to_create}";'))
        conn.execute(
            text(f'CREATE DATABASE "{db_to_create}" LOCALE_PROVIDER icu ICU_LOCALE "en-US" TEMPLATE template0;')
        )

    run_migrations(db_uri)
    db.wrapped_database.engine = create_engine(db_uri, **ENGINE_ARGUMENTS)

    try:
        yield
    finally:
        # Close all SQLAlchemy sessions
        db.wrapped_database.engine.dispose()
        close_all_sessions()

        # Force disconnect all sessions from the database
        with closing(engine.connect()) as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid)"
                    " FROM pg_stat_activity"
                    " WHERE datname = :dbname"
                    " AND pid <> pg_backend_pid()"
                ),
                {"dbname": db_to_create},
            )
            # Now try to drop the database
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_to_create}";'))


@pytest.fixture(scope="session")
def load_scheduled_tasks(database):
    with get_scheduler():
        pass


@pytest.fixture(autouse=True)
def db_session(database):
    """Ensure tests are run in a transaction with automatic rollback.

    This implementation creates a connection and transaction before yielding to the test function. Any transactions
    started and committed from within the test will be tied to this outer transaction. From the test function's
    perspective it looks like everything will indeed be committed; allowing for queries on the database to be
    performed to see if functions under test have persisted their changes to the database correctly. However once
    the test function returns this fixture will clean everything up by rolling back the outer transaction; leaving the
    database in a known state (=empty except what migrations have added as the initial state).

    Args:
        database: fixture for providing an initialized database.

    """
    with closing(db.wrapped_database.engine.connect()) as test_connection:
        db.wrapped_database.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=test_connection)
        db.wrapped_database.scoped_session = scoped_session(db.session_factory, db._scopefunc)
        BaseModel.set_query(cast(SearchQuery, db.wrapped_database.scoped_session.query_property()))

        trans = test_connection.begin()
        try:
            yield
        finally:
            # Ensure all connections are closed
            try:
                close_all_sessions()
            except Exception:
                logger.exception("Closing wrapped db connections failed, test teardown may fail")
            if not trans._deactivated_from_connection:
                trans.rollback()


@contextmanager
def make_orchestrator_app():
    from oauth2_lib.settings import oauth2lib_settings

    with (
        patch.multiple(
            oauth2lib_settings,
            OAUTH2_ACTIVE=False,
            ENVIRONMENT_IGNORE_MUTATION_DISABLED=["local", "TESTING"],
        ),
        patch.multiple(
            app_settings,
            ENABLE_PROMETHEUS_METRICS_ENDPOINT=True,
            ENVIRONMENT="TESTING",
        ),
    ):
        app = OrchestratorCore(base_settings=app_settings)
        app.broadcast_thread.start()

        try:
            yield app
        finally:
            app.worker_status_monitor.stop()
            app.broadcast_thread.stop()


@pytest.fixture(scope="session", autouse=True)
def fastapi_app(database, db_uri):
    with make_orchestrator_app() as app:
        yield app


@pytest.fixture
def fastapi_app_graphql(fastapi_app):
    """Patches the session-level fastapi_app to be used for graphql queries."""

    # Keep references to the fastapi routes and graphql router objects prior to registering
    original_routes = copy(fastapi_app.router.routes)
    original_router = fastapi_app.graphql_router

    # Register the graphql router; this needs to be done for every testcase.
    # This is because the product fixtures (e.g. generic_product_type_1) are function-level fixtures which change the
    # definitions in SUBSCRIPTION_MODEL_REGISTRY.
    # These models need to be updated in the graphql schema.
    fastapi_app.register_graphql()

    yield fastapi_app

    # Restore old routes and router object
    fastapi_app.router.routes = original_routes
    fastapi_app.graphql_router = original_router


class JsonTestClient(TestClient):
    def request(  # type: ignore
        self,
        method: str,
        url: str,
        data: Any | None = None,
        headers: typing.MutableMapping[str, str] | None = None,
        json: typing.Any = None,
        **kwargs: Any,
    ) -> requests.Response:
        if json is not None:
            if headers is None:
                headers = {}
            data = json_dumps(json).encode()
            headers["Content-Type"] = "application/json"

        return super().request(method, url, data=data, headers=headers, **kwargs)  # type: ignore


@pytest.fixture(scope="session")
def test_client(fastapi_app):
    """Client to test REST calls."""
    return JsonTestClient(fastapi_app)


@pytest.fixture
def test_client_graphql(fastapi_app_graphql):
    """Client to test GraphQL queries."""
    return JsonTestClient(fastapi_app_graphql)


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


@pytest.fixture(autouse=True)
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
