from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.forms.validators import customer_contact_list
from pydantic_forms.core import FormPage


def test_customer_contact_list():
    ContactPersonList = customer_contact_list()

    class Form(FormPage):
        customer_contacts: ContactPersonList

    validated_data = Form(
        customer_contacts=[{"name": "test1", "email": "a@b.nl", "phone": ""}, {"name": "test2", "email": "a@b.nl"}]
    ).model_dump()

    expected = {
        "customer_contacts": [
            {"email": "a@b.nl", "name": "test1", "phone": ""},
            {"email": "a@b.nl", "name": "test2", "phone": ""},
        ]
    }
    assert validated_data == expected


def test_customer_contact_list_schema():
    customer_id = uuid4()
    customer_id_str = str(customer_id)

    CustomerContactList = customer_contact_list(customer_id, "key", min_items=1)

    class Form(FormPage):
        customer_contacts: customer_contact_list()
        customer_contacts_customer: CustomerContactList
        customer_contacts_customer2: customer_contact_list(customer_id, "foo")  # noqa: F821

    expected = {
        "$defs": {
            "ContactPerson": {
                "properties": {
                    "name": {"format": "contactPersonName", "title": "Name", "type": "string"},
                    "email": {"format": "email", "title": "Email", "type": "string"},
                    "phone": {"default": "", "title": "Phone", "type": "string"},
                },
                "required": ["name", "email"],
                "title": "ContactPerson",
                "type": "object",
            }
        },
        "additionalProperties": False,
        "properties": {
            "customer_contacts": {
                "customerKey": "customer_id",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "title": "Customer Contacts",
                "type": "array",
            },
            "customer_contacts_customer": {
                "customerId": customer_id_str,
                "customerKey": "key",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "minItems": 1,
                "title": "Customer Contacts Customer",
                "type": "array",
            },
            "customer_contacts_customer2": {
                "customerId": customer_id_str,
                "customerKey": "foo",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "title": "Customer Contacts Customer2",
                "type": "array",
            },
        },
        "required": ["customer_contacts", "customer_contacts_customer", "customer_contacts_customer2"],
        "title": "unknown",
        "type": "object",
    }

    assert Form.model_json_schema() == expected


@pytest.fixture(name="Form")
def form_with_customer_contact_list():
    customer_id = uuid4()

    ReqContactList = customer_contact_list(min_items=1)
    CustomerContactList = customer_contact_list(customer_id=customer_id, customer_key="key")

    class Form(FormPage):
        customer_contacts: ReqContactList
        customer_contacts_customer: CustomerContactList = []

    return Form


def test_customer_contact_list_nok_invalid_email(Form):
    with pytest.raises(ValidationError) as error_info:
        Form(customer_contacts=[{"name": "test1", "email": "a@b"}, {"email": "a@b.nl"}])

    errors = error_info.value.errors(include_url=False, include_context=False)
    expected = [
        {
            "input": "a@b",
            "loc": ("customer_contacts", 0, "email"),
            "msg": "value is not a valid email address: The part after the @-sign is not valid. It should have a period.",
            "type": "value_error",
        },
        {
            "input": {"email": "a@b.nl"},
            "loc": ("customer_contacts", 1, "name"),
            "msg": "Field required",
            "type": "missing",
        },
    ]
    assert errors == expected


def test_customer_contact_list_nok_empty(Form):
    with pytest.raises(ValidationError) as error_info:
        Form(customer_contacts=[])

    errors = error_info.value.errors(include_url=False)
    expected = [
        {
            "input": [],
            "loc": ("customer_contacts",),
            "msg": "List should have at least 1 item after validation, not 0",
            "type": "too_short",
            "ctx": {"actual_length": 0, "field_type": "List", "min_length": 1},
        }
    ]
    assert errors == expected


@pytest.mark.parametrize("value", [[], [{}]])
def test_customer_contact_list_empty_values(value):
    assert TypeAdapter(customer_contact_list()).validate_python(value) == []
