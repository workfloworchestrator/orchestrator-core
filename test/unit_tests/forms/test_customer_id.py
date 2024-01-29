from orchestrator.forms.validators import CustomerId
from pydantic_forms.core import FormPage


def test_customer_id_schema():
    class Form(FormPage):
        customer_id: CustomerId

    expected = {
        "additionalProperties": False,
        "properties": {"customer_id": {"format": "customerId", "title": "Customer Id", "type": "string"}},
        "required": ["customer_id"],
        "title": "unknown",
        "type": "object",
    }

    assert Form.model_json_schema() == expected
