import os
import uuid
from contextlib import closing
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pytest
import structlog
from alembic import command
from alembic.config import Config
from fastapi.applications import FastAPI
from fastapi_etag.dependency import add_exception_handler
from nwastdlib.logging import initialise_logging
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from urllib3_mock import Responses

from orchestrator.api.api_v1.api import api_router
from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.db import (
    ProductBlockTable,
    ProductTable,
    ResourceTypeTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    WorkflowTable,
    db,
)
from orchestrator.db.database import ENGINE_ARGUMENTS, SESSION_ARGUMENTS, BaseModel, DBSessionMiddleware, SearchQuery
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.domain.base import ProductBlockModel
from orchestrator.domain.lifecycle import change_lifecycle
from orchestrator.exception_handlers import form_error_handler, problem_detail_handler
from orchestrator.forms import FormException
from orchestrator.services import products, subscriptions
from orchestrator.settings import app_settings
from orchestrator.types import State, SubscriptionLifecycle, UUIDstr

logger = structlog.getLogger(__name__)

CUSTOMER_ID: UUIDstr = "2f47f65a-0911-e511-80d0-005056956c1a"


def make_getter(resource_type_name: str, mapper: str) -> Callable[[State], List[Tuple[str, str]]]:
    """Based on an entry in the subscription mapping create a getter for the state.

    This getter should return a list of tuples each tuple representing an resource type and instance value.

    Examples:
        Imagine the entry "service_port.port_name" this should return a function that does:
        fun(resource_type, state): return [(resource_type_name, str(state['service_port']['port_name'])]

        Imagine the entry "service_port.port_tags[]", this should return a function that does:
        fun(resource_type, state): return [(resource_type_name, str(val)) for val in state['service_port']['port_tags']]

    """

    def getter(state: State) -> List[Tuple[str, str]]:
        logger.debug("Extracting instance value from state", mapper=mapper)
        x: Any = state
        is_optional = mapper.startswith("?")
        try:
            for key in mapper.strip("[]?").split("."):
                x = x[key]
        except KeyError:
            if is_optional:
                logger.debug("Optional instance value not found. Skipping...", mapper=mapper, key=key)
                return []
            else:
                raise
        logger.debug("Extracted value", value=x)

        if mapper.endswith("[]"):
            if is_optional:
                x = [v for v in x if v is not None]
            return [(resource_type_name, str(val)) for val in x]
        else:
            if is_optional and x is None:
                return []
            return [(resource_type_name, str(x))]

    return getter


def store_subscription_data(
    subscription_mapping: Dict,
    state: State,
    subscription_key: str = "subscription_id",
    product_key: str = "product",
    append: bool = False,
) -> State:
    """Store subscription instance values of all resource types of all product blocks in the subscription mapping."""

    def build_instances(
        subscription_instances: List[SubscriptionInstanceTable], product: ProductTable
    ) -> List[SubscriptionInstanceTable]:
        def build_instance(product_block_name: str, mapped_values: List[Tuple[str, str]]) -> SubscriptionInstanceTable:
            product_block = product.find_block_by_name(product_block_name)
            logger.debug(
                "Found product block.",
                product_block_name=product_block_name,
                product_block_id=product_block.product_block_id,
            )

            instance_values = []
            instance_id = None
            for resource_type, value in mapped_values:
                if resource_type == "subscription_instance_id":
                    instance_id = value
                    continue

                resource_type_id = product_block.find_resource_type_by_name(resource_type).resource_type_id
                logger.debug(
                    "Instantiating InstanceValue",
                    resource_type=resource_type,
                    resource_type_id=resource_type_id,
                    value=value,
                )
                instance_values.append(SubscriptionInstanceValueTable(resource_type_id=resource_type_id, value=value))

            instance = None
            if instance_id:
                instances = list(
                    filter(lambda si: str(si.subscription_instance_id) == instance_id, subscription_instances)
                )
                if len(instances) == 1:
                    instance = instances[0]

            if instance is None:
                instance = SubscriptionInstanceTable(product_block_id=product_block.product_block_id)
                subscription_instances.append(instance)

            instance.values = instance_values

            return instance

        def map_state(block_mapping: Dict) -> List[Tuple[str, str]]:
            getters = [
                make_getter(resource_type_name, instance_mapping)
                for resource_type_name, instance_mapping in block_mapping.items()
            ]
            mapped_state = []
            for getter in getters:
                mapped_state.extend(getter(state))
            logger.debug("Processed block_mapping", block_mapping=block_mapping, mapped_state=mapped_state)
            return mapped_state

        return [
            build_instance(product_block_name, map_state(block_mapping))
            for product_block_name, mappings in subscription_mapping.items()
            for block_mapping in mappings
        ]

    subscription_id = state[subscription_key]
    subscription = (
        SubscriptionTable.query.with_for_update()
        .options(selectinload(SubscriptionTable.instances))
        .get(subscription_id)
    )
    product = products.get_product(state[product_key])
    if append:
        subscription.instances += build_instances([], product)
    else:
        subscription.instances = build_instances(subscription.instances, product)

    return state


def store_subscription(
    organisation: UUIDstr,
    product_id: UUIDstr,
    subscription_name: str,
    gen_subscription_id: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> str:
    product = ProductTable.query.get(product_id)
    subscription_id = gen_subscription_id()
    subscriptions.create_subscription(organisation, product, subscription_name, subscription_id)
    return subscription_id


def run_migrations(db_uri: str) -> None:
    """
    Configure the alembic context and run the migrations.

    Each test will start with a clean database. This a heavy operation but ensures that our database is clean and
    tests run within their own context.

    Args:
        db_uri: The database uri configuration to run the migration on.

    Returns:
        None

    """
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)))
    os.environ["DATABASE_URI"] = db_uri
    app_settings.DATABASE_URI = db_uri
    alembic_cfg = Config(file_=os.path.join(path, "../../orchestrator/migrations/alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(path, "../../orchestrator/migrations"))
    alembic_cfg.set_main_option(
        "version_locations",
        f"{os.path.join(path, '../../orchestrator/migrations/versions/schema')}",
    )
    alembic_cfg.set_main_option("sqlalchemy.url", db_uri)
    command.upgrade(alembic_cfg, "heads")


@pytest.fixture(scope="session")
def db_uri(worker_id):
    """
    Ensure each pytest thread has its database.

    When running tests with the -j option make sure each test worker is isolated within its own database.

    Args:
        worker_id: the worker id

    Returns:
        Database uri to be used in the test thread

    """
    database_uri = os.environ.get("DATABASE_URI", "postgresql://nwa:nwa@localhost/orchestrator-core-test")
    if worker_id == "master":
        # pytest is being run without any workers
        return database_uri
    url = make_url(database_uri)
    url.database = f"{url.database}-{worker_id}"
    return str(url)


@pytest.fixture(scope="session")
def database(db_uri):
    """Create database and run migrations and cleanup afterwards.

    Args:
        db_uri: fixture for providing the application context and an initialized database. Although specifying this
            as an explicit parameter is redundant due to `flask_app`'s autouse setting, we have made the dependency
            explicit here for the purpose of documentation.

    """
    url = make_url(db_uri)
    db_to_create = url.database
    url.database = "postgres"
    engine = create_engine(url)
    with closing(engine.connect()) as conn:
        conn.execute("COMMIT;")
        conn.execute(f'DROP DATABASE IF EXISTS "{db_to_create}";')
        conn.execute("COMMIT;")
        conn.execute(f'CREATE DATABASE "{db_to_create}";')

    run_migrations(db_uri)
    db.engine = create_engine(db_uri, **ENGINE_ARGUMENTS)

    try:
        yield
    finally:
        db.engine.dispose()
        with closing(engine.connect()) as conn:
            conn.execute("COMMIT;")
            conn.execute(f'DROP DATABASE IF EXISTS "{db_to_create}";')


@pytest.fixture(autouse=True)
def db_session(database):
    """
    Ensure tests are run in a transaction with automatic rollback.

    This implementation creates a connection and transaction before yielding to the test function. Any transactions
    started and committed from within the test will be tied to this outer transaction. From the test function's
    perspective it looks like everything will indeed be committed; allowing for queries on the database to be
    performed to see if functions under test have persisted their changes to the database correctly. However once
    the test function returns this fixture will clean everything up by rolling back the outer transaction; leaving the
    database in a known state (=empty with the exception of what migrations have added as the initial state).

    Args:
        database: fixture for providing an initialized database.

    """
    with closing(db.engine.connect()) as test_connection:
        db.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=test_connection)
        db.scoped_session = scoped_session(db.session_factory, db._scopefunc)
        BaseModel.set_query(cast(SearchQuery, db.scoped_session.query_property()))

        trans = test_connection.begin()
        try:
            yield
        finally:
            trans.rollback()


def build_subscription_fixture(
    mapping: Dict,
    state: State,
    organisation: UUIDstr,
    product_name: str = "dummy",
    description: str = "Dummy Subscription",
    migrating: bool = False,
    provisioning: bool = False,
) -> UUIDstr:
    """Build a subscription with a mapping, complete state and product name."""
    product = products.get_product_by_name(product_name)
    subscription_id = store_subscription(organisation, product.product_id, description)
    store_subscription_data(mapping, {**state, "subscription_id": subscription_id, "product": product.product_id})

    if migrating:
        subscriptions.migrate_subscription(subscription_id)
    elif provisioning:
        subscriptions.provision_subscription(subscription_id)
    else:
        subscriptions.activate_subscription(subscription_id)

    subscriptions.resync(subscription_id)

    # This function is only used in tests. So it should be fine to do a manual commit. Tests, also run fine without it.
    db.session.commit()
    return str(subscription_id)


@pytest.fixture(scope="session", autouse=True)
def fastapi_app(database, db_uri):
    app = FastAPI(
        title="orchestrator",
        openapi_url="/openapi/openapi.yaml",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        default_response_class=JSONResponse,
    )
    initialise_logging()

    app.include_router(api_router, prefix="/api")
    # app.include_router(surf_api_router, prefix="/api")

    app.add_middleware(SessionMiddleware, secret_key=app_settings.SESSION_SECRET)
    app.add_middleware(DBSessionMiddleware, database=db)
    origins = app_settings.CORS_ORIGINS.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=app_settings.CORS_ALLOW_METHODS,
        allow_headers=app_settings.CORS_ALLOW_HEADERS,
        expose_headers=app_settings.CORS_EXPOSE_HEADERS,
    )
    app.add_exception_handler(FormException, form_error_handler)
    app.add_exception_handler(ProblemDetailException, problem_detail_handler)
    add_exception_handler(app)

    return app


@pytest.fixture(scope="session")
def test_client(fastapi_app):
    return TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def responses():
    responses_mock = Responses("requests.packages.urllib3")

    def _find_request(call):
        mock_url = responses_mock._find_match(call.request)
        if not mock_url:
            raise Exception(f"Call not mocked: {call.request}")
        return mock_url

    def _to_tuple(url_mock):
        return (url_mock["url"], url_mock["method"], url_mock["match_querystring"])

    with responses_mock:
        yield responses_mock

        mocked_urls = map(_to_tuple, responses_mock._urls)
        used_urls = map(_to_tuple, map(_find_request, responses_mock.calls))
        not_used = set(mocked_urls) - set(used_urls)
        if not_used:
            pytest.fail(f"Found unused responses mocks: {not_used}", pytrace=False)


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
    )
    db.session.add(pb)
    db.session.commit()
    return pb


@pytest.fixture
def generic_product_1(generic_product_block_1, generic_product_block_2):
    workflow = WorkflowTable.query.filter(WorkflowTable.name == "modify_note").one()
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
    workflow = WorkflowTable.query.filter(WorkflowTable.name == "modify_note").one()

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
def generic_product_block_type_1():
    class GenericProductBlockOneInactive(ProductBlockModel, product_block_name="PB_1"):
        rt_1: Optional[str] = None

    class GenericProductBlockOne(GenericProductBlockOneInactive, lifecyle=[SubscriptionLifecycle.ACTIVE]):
        rt_1: str

    return GenericProductBlockOneInactive, GenericProductBlockOne


@pytest.fixture
def generic_product_block_type_2():
    class GenericProductBlockTwoInactive(ProductBlockModel, product_block_name="PB_2"):
        rt_2: Optional[int] = None
        rt_3: Optional[str] = None

    class GenericProductBlockTwo(GenericProductBlockTwoInactive, lifecyle=[SubscriptionLifecycle.ACTIVE]):
        rt_2: int
        rt_3: str

    return GenericProductBlockTwoInactive, GenericProductBlockTwo


@pytest.fixture
def generic_product_block_type_3():
    class GenericProductBlockThreeInactive(ProductBlockModel, product_block_name="PB_3"):
        rt_2: Optional[int] = None

    class GenericProductBlockThree(GenericProductBlockThreeInactive, lifecyle=[SubscriptionLifecycle.ACTIVE]):
        rt_2: int

    return GenericProductBlockThreeInactive, GenericProductBlockThree


@pytest.fixture
def generic_product_type_1(generic_product_block_type_1, generic_product_block_type_2):
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
def generic_product_type_2(generic_product_block_type_3):
    GenericProductBlockThreeInactive, GenericProductBlockThree = generic_product_block_type_3

    class GenericProductTwoInactive(SubscriptionModel, is_base=True):
        pb_3: GenericProductBlockThreeInactive

    class GenericProductTwo(GenericProductTwoInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        pb_3: GenericProductBlockThree

    SUBSCRIPTION_MODEL_REGISTRY["Product 2"] = GenericProductTwo

    yield GenericProductTwoInactive, GenericProductTwo

    del SUBSCRIPTION_MODEL_REGISTRY["Product 2"]


@pytest.fixture
def generic_subscription_1(generic_product_1, generic_product_type_1):
    GenericProductOneInactive, _ = generic_product_type_1
    gen_subscription = GenericProductOneInactive.from_product_id(
        generic_product_1.product_id, customer_id=CUSTOMER_ID, insync=True
    )
    gen_subscription.pb_1.rt_1 = "Value1"
    gen_subscription.pb_2.rt_2 = 42
    gen_subscription.pb_2.rt_3 = "Value2"
    gen_subscription.description = "Generic Subscription One"
    gen_subscription = change_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
    gen_subscription.save()

    return str(gen_subscription.subscription_id)


@pytest.fixture
def generic_subscription_2(generic_product_2, generic_product_type_2):
    GenericProductTwoInactive, _ = generic_product_type_2
    gen_subscription = GenericProductTwoInactive.from_product_id(
        generic_product_2.product_id, customer_id=CUSTOMER_ID, insync=True
    )
    gen_subscription.pb_3.rt_2 = 42
    gen_subscription.description = "Generic Subscription One"
    gen_subscription = change_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
    gen_subscription.save()

    return str(gen_subscription.subscription_id)
