import os
import typing
from contextlib import closing
from typing import Any, Optional, cast

import pytest
import requests
import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm.scoping import scoped_session
from sqlalchemy.orm.session import sessionmaker
from starlette.testclient import DataType, TestClient
from urllib3_mock import Responses

from orchestrator import OrchestratorCore
from orchestrator.db import ProductBlockTable, ProductTable, ResourceTypeTable, WorkflowTable, db
from orchestrator.db.database import ENGINE_ARGUMENTS, SESSION_ARGUMENTS, BaseModel, Database, SearchQuery
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY, SubscriptionModel
from orchestrator.domain.base import ProductBlockModel
from orchestrator.forms import FormPage
from orchestrator.services.translations import generate_translations
from orchestrator.settings import app_settings
from orchestrator.types import SubscriptionLifecycle, UUIDstr
from orchestrator.utils.json import json_dumps
from test.unit_tests.workflows import WorkflowInstanceForTests
from test.unit_tests.workflows.shared.test_validate_subscriptions import validation_workflow

logger = structlog.getLogger(__name__)

CUSTOMER_ID: UUIDstr = "2f47f65a-0911-e511-80d0-005056956c1a"


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
    if hasattr(url, "set"):
        url = url.set(database=f"{url.database}-{worker_id}")
    else:
        url.database = f"{url.database}-{worker_id}"
    return str(url)


@pytest.fixture(scope="session")
def database(db_uri):
    """Create database and run migrations and cleanup afterwards.

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
    engine = create_engine(url)
    with closing(engine.connect()) as conn:
        conn.execute("COMMIT;")
        conn.execute(f'DROP DATABASE IF EXISTS "{db_to_create}";')
        conn.execute("COMMIT;")
        conn.execute(f'CREATE DATABASE "{db_to_create}";')

    run_migrations(db_uri)
    db.wrapped_database.engine = create_engine(db_uri, **ENGINE_ARGUMENTS)

    try:
        yield
    finally:
        db.wrapped_database.engine.dispose()
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
    with closing(db.wrapped_database.engine.connect()) as test_connection:
        db.wrapped_database.session_factory = sessionmaker(**SESSION_ARGUMENTS, bind=test_connection)
        db.wrapped_database.scoped_session = scoped_session(db.session_factory, db._scopefunc)
        BaseModel.set_query(cast(SearchQuery, db.wrapped_database.scoped_session.query_property()))

        trans = test_connection.begin()
        try:
            yield
        finally:
            if not trans._deactivated_from_connection:
                trans.rollback()


@pytest.fixture(scope="session", autouse=True)
def fastapi_app(database, db_uri):
    app_settings.DATABASE_URI = db_uri
    app = OrchestratorCore(base_settings=app_settings)
    return app


@pytest.fixture(scope="session")
def test_client(fastapi_app):
    class JsonTestClient(TestClient):
        def request(  # type: ignore
            self,
            method: str,
            url: str,
            data: Optional[DataType] = None,
            headers: Optional[typing.MutableMapping[str, str]] = None,
            json: typing.Any = None,
            **kwargs: Any,
        ) -> requests.Response:
            if json is not None:
                if headers is None:
                    headers = {}
                data = json_dumps(json).encode()
                headers["Content-Type"] = "application/json"

            return super().request(method, url, data=data, headers=headers, **kwargs)  # type: ignore

    return JsonTestClient(fastapi_app)


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


@pytest.fixture(scope="session", autouse=True)
def test_form_translations(worker_id):
    """Some voodoo to check for each form during test if the translations are complete."""

    translations = generate_translations("en-GB")["forms"]["fields"]
    used_translations = set()

    # In order to properly wrap a classmethod we need to do special stuff
    old_init_subclass = FormPage.__dict__["__init_subclass__"]

    # Wrap a form function that is certain to be called to extract the used form fields
    @classmethod
    def init_subclass_wrapper(cls, *args, **kwargs: Any) -> None:
        # Skip forms in test modules
        if "test" not in cls.__module__:
            for field_name in cls.__fields__:
                used_translations.add(field_name)
                if field_name not in translations and f"{field_name}_accept" not in translations:
                    pytest.fail(f"Missing translation for field {field_name} in  {cls.__name__}")

        # Because the original is a classmethod we need to conform to the descriptor protocol
        return old_init_subclass.__get__(None, cls)(*args, **kwargs)

    FormPage.__init_subclass__ = init_subclass_wrapper
    try:
        yield
    finally:
        # unwrapp and check if all translations are actually used
        FormPage.__init_subclass__ = old_init_subclass

        # This check only works when you run without python-xdist because we need one single session
        # TODO this does not work reliable yet
        # if worker_id == "master":
        #     unused_keys = set()
        #     for trans_key in translations:
        #         if (
        #             not trans_key.endswith("_info")
        #             and not trans_key.endswith("_accept")
        #             and not trans_key.endswith("_fields")
        #             and trans_key not in used_translations
        #             and f"{trans_key}_accept" not in used_translations
        #         ):
        #             unused_keys.add(trans_key)

        #     if unused_keys:
        #         pytest.fail(f"found unused translations: {sorted(unused_keys)}", pytrace=False)


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
def generic_product_block_type_1(generic_product_block_1):
    class GenericProductBlockOneInactive(ProductBlockModel, product_block_name="PB_1"):
        rt_1: Optional[str] = None

    class GenericProductBlockOne(GenericProductBlockOneInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        rt_1: str

    return GenericProductBlockOneInactive, GenericProductBlockOne


@pytest.fixture
def generic_product_block_type_2(generic_product_block_2):
    class GenericProductBlockTwoInactive(ProductBlockModel, product_block_name="PB_2"):
        rt_2: Optional[int] = None
        rt_3: Optional[str] = None

    class GenericProductBlockTwo(GenericProductBlockTwoInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        rt_2: int
        rt_3: str

    return GenericProductBlockTwoInactive, GenericProductBlockTwo


@pytest.fixture
def generic_product_block_type_3(generic_product_block_3):
    class GenericProductBlockThreeInactive(ProductBlockModel, product_block_name="PB_3"):
        rt_2: Optional[int] = None

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
def generic_subscription_1(generic_product_1, generic_product_type_1):
    GenericProductOneInactive, _ = generic_product_type_1
    gen_subscription = GenericProductOneInactive.from_product_id(
        generic_product_1.product_id, customer_id=CUSTOMER_ID, insync=True
    )
    gen_subscription.pb_1.rt_1 = "Value1"
    gen_subscription.pb_2.rt_2 = 42
    gen_subscription.pb_2.rt_3 = "Value2"
    gen_subscription = SubscriptionModel.from_other_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
    gen_subscription.description = "Generic Subscription One"
    gen_subscription.save()
    db.session.commit()
    return str(gen_subscription.subscription_id)


@pytest.fixture
def generic_subscription_2(generic_product_2, generic_product_type_2):
    GenericProductTwoInactive, _ = generic_product_type_2
    gen_subscription = GenericProductTwoInactive.from_product_id(
        generic_product_2.product_id, customer_id=CUSTOMER_ID, insync=True
    )
    gen_subscription.pb_3.rt_2 = 42
    gen_subscription = SubscriptionModel.from_other_lifecycle(gen_subscription, SubscriptionLifecycle.ACTIVE)
    gen_subscription.description = "Generic Subscription One"
    gen_subscription.save()
    db.session.commit()

    return str(gen_subscription.subscription_id)


@pytest.fixture
def validation_workflow_instance():
    with WorkflowInstanceForTests(validation_workflow, "validation_workflow"):
        yield "created validation workflow"
