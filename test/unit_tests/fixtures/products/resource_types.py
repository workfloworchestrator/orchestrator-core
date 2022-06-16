import pytest

from orchestrator.db import ResourceTypeTable


@pytest.fixture
def resource_type_list():
    return ResourceTypeTable(resource_type="list_field", description="")


@pytest.fixture
def resource_type_int():
    return ResourceTypeTable(resource_type="int_field", description="")


@pytest.fixture
def resource_type_int_2():
    return ResourceTypeTable(resource_type="int_field_2", description="")


@pytest.fixture
def resource_type_str():
    return ResourceTypeTable(resource_type="str_field", description="")
