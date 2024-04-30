from unittest import mock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from orchestrator.db import ResourceTypeTable, SubscriptionTable, WorkflowTable, db, transactional
from orchestrator.db.helpers import get_postgres_version
from orchestrator.targets import Target


def test_transactional():
    def insert_wf(state):
        wf = WorkflowTable(name="Test transactional", target=Target.CREATE, description="Testing 1, 2, 3!")
        db.session.add(wf)

    def insert_wf_error(state):
        wf = WorkflowTable(
            name="Test transactional [ERROR]", target=Target.CREATE, description="Testing 1, 2, 3! BOOM!"
        )
        db.session.add(wf)
        raise Exception("Let's wreck some havoc!")

    logger = mock.MagicMock()

    with transactional(db, logger):
        insert_wf({})
    logger.assert_has_calls(
        [
            mock.call.debug("Temporarily disabling commit."),
            mock.call.debug("Reenabling commit."),
            mock.call.debug("Committing transaction."),
        ]
    )

    logger.reset_mock()
    with pytest.raises(Exception) as ex:
        with transactional(db, logger):
            insert_wf_error({})

    # https://github.com/PyCQA/flake8-bugbear/issues/334
    assert str(ex.value) == "Let's wreck some havoc!"

    logger.assert_has_calls(
        [
            mock.call.debug("Temporarily disabling commit."),
            mock.call.debug("Reenabling commit."),
            mock.call.warning("Rolling back transaction."),
        ]
    )


def test_transactional_no_commit():
    def insert_wf(state):
        wf = WorkflowTable(
            name="Test transactional should not be committed", target=Target.CREATE, description="Testing 1, 2, 3!"
        )
        db.session.add(wf)
        db.session.commit()

        raise Exception("Lets rollback")

    logger = mock.MagicMock()

    with pytest.raises(Exception, match="Lets rollback") as ex:
        with transactional(db, logger):
            insert_wf({})

    # https://github.com/PyCQA/flake8-bugbear/issues/334
    assert str(ex.value) == "Lets rollback"

    assert (
        db.session.scalars(
            select(WorkflowTable).filter(WorkflowTable.name == "Test transactional should not be committed")
        ).all()
        == []
    )
    logger.assert_has_calls(
        [
            mock.call.warning(
                "Step function tried to issue a commit. It should not! Will execute commit on behalf of step function when it returns."
            ),
        ]
    )


def test_transactional_no_commit_second_thread():
    def insert_wf(state):
        wf = WorkflowTable(
            name="Test transactional should not be committed", target=Target.CREATE, description="Testing 1, 2, 3!"
        )
        db.session.add(wf)
        db.session.commit()

        # Create new database session to simulate another workflow/api handler running at the same time
        # This is also a workaround for our disable commit wrapper, but it should be reasonable obvious that
        # someone is fucking around if you see `with db.database_scope():` in actual production code

        with db.database_scope():
            wf2 = WorkflowTable(
                name="Test transactional should be committed", target=Target.CREATE, description="Testing 1, 2, 3!"
            )
            db.session.add(wf2)
            db.session.commit()

        raise Exception("Lets rollback")

    logger = mock.MagicMock()

    with pytest.raises(Exception, match="Lets rollback") as ex:
        with transactional(db, logger):
            insert_wf({})

    # https://github.com/PyCQA/flake8-bugbear/issues/334
    assert str(ex.value) == "Lets rollback"

    assert (
        db.session.execute(
            select(WorkflowTable).filter(WorkflowTable.name == "Test transactional should not be committed")
        ).all()
        == []
    )
    logger.assert_has_calls(
        [
            mock.call.warning(
                "Step function tried to issue a commit. It should not! Will execute commit on behalf of step function when it returns."
            ),
        ]
    )


def test_autouse_fixture_rolls_back_aaa():
    # We want to test whether a change committed to the database in one test is visible to other tests (as in really
    # persisted to the database). Of course such a change should not be visible if our `fastapi_app` and `database`
    # autouse fixtures work as advertised.
    #
    # However, tests should be independent of each other and we cannot assume one test runs before the other. Hence
    # this test comes in two versions: one with the `_aaa` postfix and one with the `_bbb` postfix. Both will test
    # for the presence of a change the other test thinks it has committed to the database. If one of the tests (the
    # one that runs after the other) finds the change the other has committed our fixtures don't work properly.

    # Using ResourceTypeTable as it's a simple model than doesn't require foreign keys.
    rt = ResourceTypeTable(resource_type="aaa", description="aaa")
    # print(db)
    # print(dir(db))

    db.session.add(rt)
    db.session.commit()

    with pytest.raises(NoResultFound):
        db.session.scalars(select(ResourceTypeTable).where(ResourceTypeTable.resource_type == "bbb")).one()


def test_autouse_fixture_rolls_back_bbb():
    # We want to test whether a change committed to the database in one test is visible to other tests (as in really
    # persisted to the database). Of course such a change should not be visible if our `fastapi_app` and `database`
    # autouse fixtures work as advertised.
    #
    # However, tests should be independent of each other and we cannot assume one test runs before the other. Hence
    # this test comes in two versions: one with the `_aaa` postfix and one with the `_bbb` postfix. Both will test
    # for the presence of a change the other test thinks it has committed to the database. If one of the tests (the
    # one that runs after the other) finds the change the other has committed our fixtures don't work properly.

    # Using ResourceTypeTable as it's a simple model than doesn't require foreign keys.
    rt = ResourceTypeTable(resource_type="bbb", description="bbb")
    db.session.add(rt)
    db.session.commit()

    with pytest.raises(NoResultFound):
        db.session.scalars(select(ResourceTypeTable).where(ResourceTypeTable.resource_type == "aaa")).one()


def test_str_method():
    assert (
        str(SubscriptionTable())
        == "SubscriptionTable(subscription_id=None, description=None, status=None, product_id=None, customer_id=None, insync=None, start_date=None, end_date=None, note=None)"
    )


def test_get_postgres_version():
    pg_version = get_postgres_version()
    assert isinstance(pg_version, int)
    assert 0 < pg_version < 20
