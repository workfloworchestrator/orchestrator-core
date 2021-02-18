from http import HTTPStatus
from unittest import TestCase

import pytest

from orchestrator.api.error_handling import ProblemDetailException
from orchestrator.api.models import transform_json, validate
from orchestrator.db import ProductTable, ResourceTypeTable


class TestModels(TestCase):
    def test_validate(self):
        with pytest.raises(ProblemDetailException) as excinfo:
            validate(ProductTable, {})

        assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
        assert (
            excinfo.value.detail == "Missing attributes 'name, description, product_type, tag, status' for ProductTable"
        )

        json_dict = {"resource_type": "some"}
        res = validate(ResourceTypeTable, json_dict)
        self.assertEqual(json_dict, res)

        with pytest.raises(ProblemDetailException) as excinfo:
            validate(ResourceTypeTable, json_dict, is_new_instance=False)

        assert excinfo.value.status_code == HTTPStatus.BAD_REQUEST
        assert excinfo.value.detail == "Missing attributes 'resource_type_id' for ResourceTypeTable"

    def test_transform_json(self):
        nested_body = {
            "name": "MSP",
            "description": "MSP",
            "product_type": "Port",
            "tag": "Port",
            "status": "active",
            "fixed_inputs": [{"name": "name", "value": "val"}, {"name": "name", "value": "val"}],
            "product_blocks": [{"name": "name", "description": "desc", "resource_types": [{"resource_type": "test"}]}],
        }

        nested_json_with_objects = transform_json(nested_body)
        product = ProductTable(**nested_json_with_objects)

        self.assertEqual("test", product.product_blocks[0].resource_types[0].resource_type)
