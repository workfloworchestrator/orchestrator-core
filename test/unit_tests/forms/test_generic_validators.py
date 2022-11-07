from typing import TypeVar
from unittest import mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.forms import FormPage, ReadOnlyField
from orchestrator.forms.validators import (
    Accept,
    Choice,
    ContactPersonList,
    DisplaySubscription,
    Divider,
    Label,
    ListOfOne,
    ListOfTwo,
    LongText,
    MigrationSummary,
    OrganisationId,
    ProductId,
    UniqueConstrainedList,
    choice_list,
    contact_person_list,
    migration_summary,
    product_id,
    unique_conlist,
)
from orchestrator.services import products
from orchestrator.utils.json import json_dumps, json_loads


def test_constrained_list_good():
    class UniqueConListModel(FormPage):
        v: unique_conlist(int, unique_items=True) = []

    m = UniqueConListModel(v=[1, 2, 3])
    assert m.v == [1, 2, 3]


def test_constrained_list_default():
    class UniqueConListModel(FormPage):
        v: unique_conlist(int, unique_items=True) = []

    m = UniqueConListModel()
    assert m.v == []


def test_constrained_list_constraints():
    class UniqueConListModel(FormPage):
        v: unique_conlist(int, min_items=1, unique_items=True)

    m = UniqueConListModel(v=list(range(7)))
    assert m.v == list(range(7))

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=[1, 1, 1])
    assert exc_info.value.errors() == [
        {"loc": ("v",), "msg": "the list has duplicated items", "type": "value_error.list.unique_items"}
    ]

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=1)
    assert exc_info.value.errors() == [{"loc": ("v",), "msg": "value is not a valid list", "type": "type_error.list"}]

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=[])
    assert exc_info.value.errors() == [
        {
            "loc": ("v",),
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items",
            "ctx": {"limit_value": 1},
        }
    ]


def test_constrained_list_inherit_constraints():
    T = TypeVar("T")

    class Parent(UniqueConstrainedList[T]):
        min_items = 1

    class Child(Parent[T]):
        unique_items = True

    class UniqueConListModel(FormPage):
        v: Child[int]

    m = UniqueConListModel(v=list(range(7)))
    assert m.v == list(range(7))

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=[1, 1, 1])
    assert exc_info.value.errors() == [
        {"loc": ("v",), "msg": "the list has duplicated items", "type": "value_error.list.unique_items"}
    ]

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=1)
    assert exc_info.value.errors() == [{"loc": ("v",), "msg": "value is not a valid list", "type": "type_error.list"}]

    with pytest.raises(ValidationError) as exc_info:
        UniqueConListModel(v=[])
    assert exc_info.value.errors() == [
        {
            "loc": ("v",),
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items",
            "ctx": {"limit_value": 1},
        }
    ]


def test_constrained_list_schema():
    class UniqueConListClass(UniqueConstrainedList[int]):
        min_items = 1
        max_items = 3
        unique_items = True

    class UniqueConListModel(FormPage):
        unique_conlist1: unique_conlist(int)
        unique_conlist2: unique_conlist(int, min_items=1, max_items=3, unique_items=True)
        unique_conlist3: UniqueConListClass

    expected = {
        "additionalProperties": False,
        "properties": {
            "unique_conlist1": {"items": {"type": "integer"}, "title": "Unique Conlist1", "type": "array"},
            "unique_conlist2": {
                "items": {"type": "integer"},
                "maxItems": 3,
                "minItems": 1,
                "title": "Unique Conlist2",
                "type": "array",
                "uniqueItems": True,
            },
            "unique_conlist3": {
                "items": {"type": "integer"},
                "maxItems": 3,
                "minItems": 1,
                "title": "Unique Conlist3",
                "type": "array",
                "uniqueItems": True,
            },
        },
        "required": ["unique_conlist1", "unique_conlist2", "unique_conlist3"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == UniqueConListModel.schema()


def test_accept_ok():
    class Form(FormPage):
        accept: Accept

    validated_data = Form(accept="ACCEPTED").dict()

    expected = {"accept": True}
    assert expected == json_loads(json_dumps(validated_data))


def test_accept_schema():
    class Form(FormPage):
        accept: Accept

    expected = {
        "additionalProperties": False,
        "properties": {
            "accept": {
                "enum": ["ACCEPTED", "INCOMPLETE"],
                "format": "accept",
                "type": "string",
                "title": "Accept",
            }
        },
        "required": ["accept"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == Form.schema()


def test_accept_schema_with_data():
    class SpecialAccept(Accept):
        data = [("field", "label")]

    class Form(FormPage):
        accept: SpecialAccept

    expected = {
        "additionalProperties": False,
        "properties": {
            "accept": {
                "data": [("field", "label")],
                "enum": ["ACCEPTED", "INCOMPLETE"],
                "format": "accept",
                "type": "string",
                "title": "Accept",
            }
        },
        "required": ["accept"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == Form.schema()


def test_accept_nok():
    class Form(FormPage):
        accept: Accept

    with pytest.raises(ValidationError) as error_info:
        Form(accept="INCOMPLETE")

    expected = [{"loc": ("accept",), "msg": "Not all tasks are done", "type": "value_error"}]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(accept="Bla")

    expected = [
        {
            "ctx": {"enum_values": [Accept.Values.ACCEPTED, Accept.Values.INCOMPLETE]},
            "loc": ("accept",),
            "msg": "value is not a valid enumeration member; permitted: 'ACCEPTED', 'INCOMPLETE'",
            "type": "type_error.enum",
        }
    ]
    assert expected == error_info.value.errors()


def test_choice():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: LegChoice

    # Make sure label classvar is not included
    assert len(LegChoice.__members__) == 2

    # Should still count as string and enum
    assert Form(choice="Primary").choice == "Primary"
    assert Form(choice="Primary").choice == LegChoice.Primary

    # Validation works
    Form(choice="Primary")

    with pytest.raises(ValidationError):
        Form(choice="Wrong")


def test_choice_default():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: LegChoice = LegChoice.Primary

    Form(choice="Primary")
    Form()
    Form(choice=LegChoice.Primary)

    with pytest.raises(ValidationError):
        Form(choice="Wrong")


def test_choice_default_str():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: LegChoice = "Primary"

    Form(choice="Primary")
    Form()
    Form(choice=LegChoice.Primary)

    with pytest.raises(ValidationError):
        Form(choice="Wrong")


def test_choice_schema():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class LegChoiceLabel(Choice):
        Primary = ("Primary", "Primary LP")
        Secondary = ("Secondary", "Secondary LP")
        Tertiary = "Tertiary"

    class Form(FormPage):
        choice: LegChoice
        choice_label: LegChoiceLabel

    assert Form.schema() == {
        "additionalProperties": False,
        "definitions": {
            "LegChoice": {
                "description": "An enumeration.",
                "enum": ["Primary", "Secondary"],
                "title": "LegChoice",
                "type": "string",
            },
            "LegChoiceLabel": {
                "description": "An enumeration.",
                "enum": ["Primary", "Secondary", "Tertiary"],
                "options": {"Primary": "Primary LP", "Secondary": "Secondary LP", "Tertiary": "Tertiary"},
                "title": "LegChoiceLabel",
                "type": "string",
            },
        },
        "properties": {
            "choice": {"$ref": "#/definitions/LegChoice"},
            "choice_label": {"$ref": "#/definitions/LegChoiceLabel"},
        },
        "required": ["choice", "choice_label"],
        "title": "unknown",
        "type": "object",
    }


def test_choice_list():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: choice_list(LegChoice)

    # Validation works
    Form(choice=["Primary"])
    Form(choice=["Primary", "Primary"])

    with pytest.raises(ValidationError):
        Form(choice=["Wrong"])

    with pytest.raises(ValidationError):
        Form(choice=["Primary", "Wrong"])


def test_choice_list_default():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: choice_list(LegChoice) = [LegChoice.Primary]

    Form(choice=["Primary"])
    Form()
    Form(choice=[LegChoice.Primary])

    with pytest.raises(ValidationError):
        Form(choice=["Wrong"])


def test_choice_list_default_str():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: choice_list(LegChoice) = ["Primary"]

    Form(choice=["Primary"])
    Form()
    Form(choice=[LegChoice.Primary])

    with pytest.raises(ValidationError):
        Form(choice=["Wrong"])


def test_choice_list_schema():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class LegChoiceLabel(Choice):
        Primary = ("Primary", "Primary LP")
        Secondary = ("Secondary", "Secondary LP")
        Tertiary = "Tertiary"

    class Form(FormPage):
        choice: choice_list(LegChoice)
        choice_label: choice_list(LegChoiceLabel)

    assert Form.schema() == {
        "additionalProperties": False,
        "definitions": {
            "LegChoice": {
                "description": "An enumeration.",
                "enum": ["Primary", "Secondary"],
                "title": "LegChoice",
                "type": "string",
            },
            "LegChoiceLabel": {
                "description": "An enumeration.",
                "enum": ["Primary", "Secondary", "Tertiary"],
                "options": {"Primary": "Primary LP", "Secondary": "Secondary LP", "Tertiary": "Tertiary"},
                "title": "LegChoiceLabel",
                "type": "string",
            },
        },
        "properties": {
            "choice": {"items": {"$ref": "#/definitions/LegChoice"}, "type": "array"},
            "choice_label": {
                "items": {"$ref": "#/definitions/LegChoiceLabel"},
                "options": {"Primary": "Primary LP", "Secondary": "Secondary LP", "Tertiary": "Tertiary"},
                "type": "array",
            },
        },
        "required": ["choice", "choice_label"],
        "title": "unknown",
        "type": "object",
    }


def test_choice_list_constraints():
    class LegChoice(Choice):
        Primary = "Primary"
        Secondary = "Secondary"

    class Form(FormPage):
        choice: choice_list(LegChoice, min_items=1, unique_items=True) = ["Primary"]

    m = Form(choice=[LegChoice.Primary, LegChoice.Secondary])
    assert m.choice == [LegChoice.Primary, LegChoice.Secondary]

    with pytest.raises(ValidationError) as exc_info:
        Form(choice=[1, 1, 1])
    assert exc_info.value.errors() == [
        {"loc": ("choice",), "msg": "the list has duplicated items", "type": "value_error.list.unique_items"}
    ]

    with pytest.raises(ValidationError) as exc_info:
        Form(choice=1)
    assert exc_info.value.errors() == [
        {"loc": ("choice",), "msg": "value is not a valid list", "type": "type_error.list"}
    ]

    with pytest.raises(ValidationError) as exc_info:
        Form(choice=[])
    assert exc_info.value.errors() == [
        {
            "loc": ("choice",),
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items",
            "ctx": {"limit_value": 1},
        }
    ]


def test_contact_persons():
    class Form(FormPage):
        contact_persons: ContactPersonList

    validated_data = Form(
        contact_persons=[{"name": "test1", "email": "a@b.nl", "phone": ""}, {"name": "test2", "email": "a@b.nl"}]
    ).dict()

    expected = {
        "contact_persons": [
            {"email": "a@b.nl", "name": "test1", "phone": ""},
            {"email": "a@b.nl", "name": "test2", "phone": ""},
        ]
    }
    assert expected == validated_data


def test_contact_persons_schema():
    org_id = uuid4()

    class OrgContactPersonList(ContactPersonList):
        organisation = org_id
        organisation_key = "key"
        min_items = 1

    class Form(FormPage):
        contact_persons: ContactPersonList = []
        contact_persons_org: OrgContactPersonList
        contact_persons_org2: contact_person_list(org_id, "foo")  # noqa: F821

    assert Form.schema() == {
        "additionalProperties": False,
        "definitions": {
            "ContactPerson": {
                "properties": {
                    "email": {"format": "email", "title": "Email", "type": "string"},
                    "name": {"format": "contactPersonName", "title": "Name", "type": "string"},
                    "phone": {"default": "", "title": "Phone", "type": "string"},
                },
                "required": ["name", "email"],
                "title": "ContactPerson",
                "type": "object",
            }
        },
        "properties": {
            "contact_persons": {
                "default": [],
                "items": {"$ref": "#/definitions/ContactPerson"},
                "organisationKey": "organisation",
                "title": "Contact Persons",
                "type": "array",
            },
            "contact_persons_org": {
                "items": {"$ref": "#/definitions/ContactPerson"},
                "organisationId": str(org_id),
                "organisationKey": "key",
                "title": "Contact Persons Org",
                "type": "array",
                "minItems": 1,
            },
            "contact_persons_org2": {
                "items": {"$ref": "#/definitions/ContactPerson"},
                "organisationId": str(org_id),
                "organisationKey": "foo",
                "title": "Contact Persons Org2",
                "type": "array",
            },
        },
        "required": ["contact_persons_org", "contact_persons_org2"],
        "title": "unknown",
        "type": "object",
    }


def test_contact_persons_nok():
    org_id = uuid4()

    class ReqContactPersonList(ContactPersonList):
        min_items = 1

    class OrgContactPersonList(ContactPersonList):
        organisation = org_id
        organisation_key = "key"

    class Form(FormPage):
        contact_persons: ReqContactPersonList
        contact_persons_org: OrgContactPersonList = []

    with pytest.raises(ValidationError) as error_info:
        Form(contact_persons=[{"name": "test1", "email": "a@b"}, {"email": "a@b.nl"}])

    expected = [
        {
            "loc": ("contact_persons", 0, "email"),
            "msg": "value is not a valid email address",
            "type": "value_error.email",
        },
        {"loc": ("contact_persons", 1, "name"), "msg": "field required", "type": "value_error.missing"},
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(contact_persons=[])

    expected = [
        {
            "loc": ("contact_persons",),
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items",
            "ctx": {"limit_value": 1},
        }
    ]
    assert expected == error_info.value.errors()


def test_long_text_schema():
    class Form(FormPage):
        long_text: LongText

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {"long_text": {"format": "long", "title": "Long Text", "type": "string"}},
        "required": ["long_text"],
        "title": "unknown",
        "type": "object",
    }


def test_display():
    class Form(FormPage):
        display_sub: DisplaySubscription
        label: Label
        migration_summary: migration_summary({"headers": ["one"]})  # noqa: F821

    assert Form().dict() == {"display_sub": None, "label": None, "migration_summary": None}
    assert Form(display_sub="foo", label="bar", migration_summary="baz").dict() == {
        "display_sub": None,
        "label": None,
        "migration_summary": None,
    }


def test_labels_with_value_and_dividers():
    class Form(FormPage):
        label: Label = "value"
        divider: Divider

    assert Form().dict() == {"label": "value", "divider": None}
    assert Form(label="fob", divider="baz").dict() == {
        "label": "value",
        "divider": None,
    }


def test_display_only_schema():
    some_sub_id = uuid4()

    class Form(FormPage):
        display_sub: DisplaySubscription = some_sub_id
        label: Label
        migration_summary: migration_summary({"headers": ["one"]})  # noqa: F821

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "display_sub": {
                "default": str(some_sub_id),
                "format": "subscription",
                "title": "Display Sub",
                "type": "string",
            },
            "label": {"format": "label", "title": "Label", "type": "string"},
            "migration_summary": {
                "format": "summary",
                "title": "Migration Summary",
                "type": "string",
                "uniforms": {"data": {"headers": ["one"]}},
            },
        },
        "title": "unknown",
        "type": "object",
    }


def test_read_only_field_schema():
    class Form(FormPage):
        read_only: int = ReadOnlyField(1, const=False)

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "read_only": {
                "const": 1,
                "default": 1,
                "title": "Read Only",
                "type": "integer",
                "uniforms": {"disabled": True, "value": 1},
            },
        },
        "title": "unknown",
        "type": "object",
    }


def test_organisation_id_schema():
    class Form(FormPage):
        org_id: OrganisationId

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {"org_id": {"format": "organisationId", "title": "Org Id", "type": "string"}},
        "required": ["org_id"],
        "title": "unknown",
        "type": "object",
    }


def test_display_default():
    some_sub_id = uuid4()

    class Summary(MigrationSummary):
        data = {"headers": ["one"]}

    class Form(FormPage):
        display_sub: DisplaySubscription = some_sub_id
        label: Label = "bla"
        migration_summary: Summary = "foo"

    assert Form().dict() == {
        "display_sub": some_sub_id,
        "label": "bla",
        "migration_summary": "foo",
    }
    assert Form(display_sub="").dict() == {
        "display_sub": some_sub_id,
        "label": "bla",
        "migration_summary": "foo",
    }


@mock.patch.object(products, "get_product_by_id")
def test_product_id(mock_get_product_by_id):
    product_x_id = uuid4()
    product_y_id = uuid4()

    mock_get_product_by_id.side_effect = [product_x_id, product_y_id]

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    data = Form(product_id=product_y_id, product_x=product_x_id)
    assert data.product_x == product_x_id
    assert data.product_id == product_y_id
    assert mock_get_product_by_id.has_calls([mock.call(product_x_id), mock.call(product_y_id)])


def test_product_id_schema():
    product_x_id = uuid4()

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "product_id": {"format": "productId", "title": "Product Id", "type": "string"},
            "product_x": {
                "format": "productId",
                "title": "Product X",
                "type": "string",
                "uniforms": {"productIds": [product_x_id]},
            },
        },
        "required": ["product_x", "product_id"],
        "title": "unknown",
        "type": "object",
    }


@mock.patch.object(products, "get_product_by_id")
def test_product_id_nok(mock_get_product_by_id):
    product_x_id = uuid4()
    product_y_id = uuid4()

    mock_get_product_by_id.side_effect = [product_y_id, None]

    class Form(FormPage):
        product_x: product_id([product_x_id])
        product_id: ProductId

    with pytest.raises(ValidationError) as error_info:
        Form(product_id=product_y_id, product_x=product_y_id)

    expected = [
        {
            "ctx": {"enum_values": [str(product_x_id)]},
            "loc": ("product_x",),
            "msg": f"value is not a valid enumeration member; permitted: '{str(product_x_id)}'",
            "type": "type_error.product_id",
        },
        {"loc": ("product_id",), "msg": "Product not found", "type": "value_error"},
    ]
    assert expected == error_info.value.errors()
    assert mock_get_product_by_id.has_calls([mock.call(product_x_id), mock.call(product_y_id)])

    with pytest.raises(ValidationError) as error_info:
        Form(product_id="INCOMPLETE")

    expected = [
        {"loc": ("product_x",), "msg": "field required", "type": "value_error.missing"},
        {"loc": ("product_id",), "msg": "value is not a valid uuid", "type": "type_error.uuid"},
    ]
    assert expected == error_info.value.errors()


def test_migration_summary_schema():
    class Summary(MigrationSummary):
        data = "foo"

    class Form(FormPage):
        ms1: Summary
        ms2: migration_summary("bar")  # noqa: F821

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "ms1": {"format": "summary", "title": "Ms1", "type": "string", "uniforms": {"data": "foo"}},
            "ms2": {"format": "summary", "title": "Ms2", "type": "string", "uniforms": {"data": "bar"}},
        },
        "title": "unknown",
        "type": "object",
    }


def test_list_of_one():
    class Form(FormPage):
        one: ListOfOne[int]

    assert Form(one=[1])

    with pytest.raises(ValidationError) as error_info:
        assert Form(one=[])

    expected = [
        {
            "ctx": {"limit_value": 1},
            "loc": ("one",),
            "msg": "ensure this value has at least 1 items",
            "type": "value_error.list.min_items",
        }
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(one=[1, 2])

    expected = [
        {
            "ctx": {"limit_value": 1},
            "loc": ("one",),
            "msg": "ensure this value has at most 1 items",
            "type": "value_error.list.max_items",
        },
    ]
    assert expected == error_info.value.errors()


def test_list_of_two():
    class Form(FormPage):
        two: ListOfTwo[int]

    assert Form(two=[1, 2])

    with pytest.raises(ValidationError) as error_info:
        assert Form(two=[1])

    expected = [
        {
            "ctx": {"limit_value": 2},
            "loc": ("two",),
            "msg": "ensure this value has at least 2 items",
            "type": "value_error.list.min_items",
        }
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(two=[1, 2, 3])

    expected = [
        {
            "ctx": {"limit_value": 2},
            "loc": ("two",),
            "msg": "ensure this value has at most 2 items",
            "type": "value_error.list.max_items",
        },
    ]
    assert expected == error_info.value.errors()


def test_list_of_two_schema():
    class Form(FormPage):
        list: ListOfTwo[str]

    expected = {
        "additionalProperties": False,
        "properties": {
            "list": {
                "items": {"type": "string"},
                "title": "List",
                "minItems": 2,
                "maxItems": 2,
                "type": "array",
            }
        },
        "required": ["list"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == Form.schema()
