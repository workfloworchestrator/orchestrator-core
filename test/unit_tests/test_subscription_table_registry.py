from orchestrator.db.models import SubscriptionTable


def test_get_subscription_table_class_returns_default_when_no_custom_registered():
    original = SubscriptionTable._custom_table_class
    SubscriptionTable._custom_table_class = None
    try:
        result = SubscriptionTable.get_subscription_table_class()
        assert result is SubscriptionTable
    finally:
        SubscriptionTable._custom_table_class = original


def test_init_subclass_registers_custom_table():
    original = SubscriptionTable._custom_table_class
    SubscriptionTable._custom_table_class = None
    try:

        class CustomSubscriptionTable(SubscriptionTable, use_as_subscription_table=True):
            pass

        result = SubscriptionTable.get_subscription_table_class()
        assert result is CustomSubscriptionTable
    finally:
        SubscriptionTable._custom_table_class = original


def test_init_subclass_does_not_register_without_keyword():
    original = SubscriptionTable._custom_table_class
    SubscriptionTable._custom_table_class = None
    try:

        class PlainSubclass(SubscriptionTable):
            pass

        result = SubscriptionTable.get_subscription_table_class()
        assert result is SubscriptionTable
    finally:
        SubscriptionTable._custom_table_class = original
