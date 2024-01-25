from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestrator.forms.validators import customer_contact_list
from pydantic_forms.core import FormPage


def test_customer_contact_list():
    ContactPersonList = customer_contact_list()

    class Form(FormPage):
        contact_persons: ContactPersonList

    validated_data = Form(
        contact_persons=[{"name": "test1", "email": "a@b.nl", "phone": ""}, {"name": "test2", "email": "a@b.nl"}]
    ).model_dump()

    expected = {
        "contact_persons": [
            {"email": "a@b.nl", "name": "test1", "phone": ""},
            {"email": "a@b.nl", "name": "test2", "phone": ""},
        ]
    }
    assert validated_data == expected


def test_customer_contact_list_schema():
    customer = uuid4()

    CustomerContactList = customer_contact_list(customer, "key", min_items=1)

    class Form(FormPage):
        contact_persons: customer_contact_list()
        contact_persons_customer: CustomerContactList
        contact_persons_customer2: customer_contact_list(customer, "foo")  # noqa: F821

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
            "contact_persons": {
                "customerKey": "customer",
                "description": "organisationId and organisationKey attributes will be removed, switch to customer and customer_key",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "organisationKey": "customer",
                "title": "Customer Contacts",
                "type": "array",
            },
            "contact_persons_customer": {
                "customerId": "9ee269f6-aa7e-4810-a144-282feb3e5569",
                "customerKey": "key",
                "description": "organisationId and organisationKey attributes will be removed, switch to customer and customer_key",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "minItems": 1,
                "organisationId": "9ee269f6-aa7e-4810-a144-282feb3e5569",
                "organisationKey": "key",
                "title": "Customer Contacts Customer",
                "type": "array",
            },
            "contact_persons_customer2": {
                "customerId": "9ee269f6-aa7e-4810-a144-282feb3e5569",
                "customerKey": "foo",
                "description": "organisationId and organisationKey attributes will be removed, switch to customer and customer_key",
                "items": {"$ref": "#/$defs/ContactPerson"},
                "organisationId": "9ee269f6-aa7e-4810-a144-282feb3e5569",
                "organisationKey": "foo",
                "title": "Customer Contacts Customer2",
                "type": "array",
            },
        },
        "required": ["contact_persons", "contact_persons_customer", "contact_persons_customer2"],
        "title": "unknown",
        "type": "object",
    }

    assert Form.model_json_schema() == expected


@pytest.fixture(name="Form")
def form_with_customer_contact_list():
    customer = uuid4()

    ReqContactList = customer_contact_list(min_items=1)
    CustomerContactList = customer_contact_list(customer=customer, customer_key="key")

    class Form(FormPage):
        contact_persons: ReqContactList
        contact_persons_customer: CustomerContactList = []

    return Form


def test_customer_contact_list_nok_invalid_email(Form):
    with pytest.raises(ValidationError) as error_info:
        Form(contact_persons=[{"name": "test1", "email": "a@b"}, {"email": "a@b.nl"}])

    errors = error_info.value.errors(include_url=False, include_context=False)
    expected = [
        {
            "input": "a@b",
            "loc": ("contact_persons", 0, "email"),
            "msg": "value is not a valid email address: The part after the @-sign is not valid. It should have a period.",
            "type": "value_error",
        },
        {
            "input": {"email": "a@b.nl"},
            "loc": ("contact_persons", 1, "name"),
            "msg": "Field required",
            "type": "missing",
        },
    ]
    assert errors == expected


def test_customer_contact_list_nok_empty(Form):
    with pytest.raises(ValidationError) as error_info:
        Form(contact_persons=[])

    errors = error_info.value.errors(include_url=False)
    expected = [
        {
            "input": [],
            "loc": ("contact_persons",),
            "msg": "List should have at least 1 item after validation, not 0",
            "type": "too_short",
            "ctx": {"actual_length": 0, "field_type": "List", "min_length": 1},
        }
    ]
    assert errors == expected


@pytest.mark.parametrize("value", [[], [{}]])
def test_customer_contact_list_empty_values(value):
    assert TypeAdapter(customer_contact_list()).validate_python(value) == []
