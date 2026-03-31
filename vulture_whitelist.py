"""Vulture whitelist: false positives that must not be flagged as unused."""

# alembic include_object callback signature (migrations/env.py)
compare_to  # noqa
reflected  # noqa

# __exit__ protocol signature (services/processes.py)
exc_type  # noqa
exc_val  # noqa
exc_tb  # noqa
