from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.db.models import ProductTable
from orchestrator.forms import FormPage
from orchestrator.forms.network_type_validators import BFD, MTU
from orchestrator.forms.validators import (
    Accept,
    Choice,
    ContactPersonList,
    DisplaySubscription,
    Label,
    ListOfTwo,
    LongText,
    MigrationSummary,
    OrganisationId,
    ProductId,
    UniqueConstrainedList,
    contact_person_list,
    migration_summary,
    product_id,
    unique_conlist,
)
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
    assert exc_info.value.errors() == [{"loc": ("v",), "msg": "Items must be unique", "type": "value_error"}]

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


def test_product_id_ok(generic_product_1):
    product = ProductTable.query.limit(1).one()

    class Form(FormPage):
        product_id: ProductId

    assert Form(product_id=product.product_id).product_id == product.product_id


def test_product_id_schema():
    class Form(FormPage):
        product_id: ProductId

    expected = {
        "additionalProperties": False,
        "properties": {"product_id": {"format": "productId", "title": "Product Id", "type": "string"}},
        "required": ["product_id"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == Form.schema()


def test_product_id_schema_with_product():
    some_product = uuid4()

    class Form(FormPage):
        product_id: product_id(products=[some_product])

    expected = {
        "additionalProperties": False,
        "properties": {
            "product_id": {
                "format": "productId",
                "title": "Product Id",
                "type": "string",
                "uniforms": {"productIds": [some_product]},
            }
        },
        "required": ["product_id"],
        "title": "unknown",
        "type": "object",
    }
    assert expected == Form.schema()


def test_product_id_nok():
    class Form(FormPage):
        product_id: ProductId

    with pytest.raises(ValidationError) as error_info:
        Form(product_id="INCOMPLETE")

    expected = [{"loc": ("product_id",), "msg": "value is not a valid uuid", "type": "type_error.uuid"}]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(product_id=uuid4())

    expected = [{"loc": ("product_id",), "msg": "Product not found", "type": "value_error"}]
    assert expected == error_info.value.errors()


def test_product_id_nok_with_products(generic_product_1, generic_product_2):
    product = ProductTable.query.limit(1).one()
    another_product = ProductTable.query.offset(1).limit(1).one()

    class Form(FormPage):
        product_id: product_id(products=[product.product_id])

    with pytest.raises(ValidationError) as error_info:
        Form(product_id="INCOMPLETE")

    expected = [{"loc": ("product_id",), "msg": "value is not a valid uuid", "type": "type_error.uuid"}]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(product_id=uuid4())

    expected = [{"loc": ("product_id",), "msg": "Product not found", "type": "value_error"}]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(product_id=another_product.product_id)

    expected = [
        {
            "ctx": {"enum_values": [str(product.product_id)]},
            "loc": ("product_id",),
            "msg": f"value is not a valid enumeration member; permitted: '{product.product_id}'",
            "type": "type_error.product_id",
        },
    ]
    assert expected == error_info.value.errors()


def test_list_of_two():
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


def test_bfd_ok():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False, "minimum_interval": None, "multiplier": None}
    validated_data = Form(bfd=model).dict()

    expected = {"bfd": BFD(enabled=False, minimum_interval=None, multiplier=None)}
    assert expected == validated_data

    model = {"enabled": True, "minimum_interval": 600, "multiplier": 3}
    validated_data = Form(bfd=model).dict()

    expected = {"bfd": BFD(enabled=True, minimum_interval=600, multiplier=3)}
    assert expected == validated_data


def test_bfd_missing_values():
    class Form(FormPage):
        bfd: BFD

    model = {"enabled": False}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": False}}

    model = {"enabled": True, "multiplier": 4}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": True, "multiplier": 4, "minimum_interval": 900}}

    model = {"enabled": True, "minimum_interval": 600}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": True, "multiplier": 3, "minimum_interval": 600}}

    model = {"enabled": False, "minimum_interval": 600, "multiplier": 3}
    assert Form(bfd=model).dict() == {"bfd": {"enabled": False}}


def test_bfd_wrong_values():
    class Form(FormPage):
        bfd: BFD

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 0, "multiplier": 3})

    expected = [
        {
            "loc": ("bfd", "minimum_interval"),
            "msg": "ensure this value is greater than or equal to 1",
            "type": "value_error.number.not_ge",
            "ctx": {"limit_value": 1},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 255001, "multiplier": 3})

    expected = [
        {
            "loc": ("bfd", "minimum_interval"),
            "msg": "ensure this value is less than or equal to 255000",
            "type": "value_error.number.not_le",
            "ctx": {"limit_value": 255000},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 0})

    expected = [
        {
            "loc": ("bfd", "multiplier"),
            "msg": "ensure this value is greater than or equal to 1",
            "type": "value_error.number.not_ge",
            "ctx": {"limit_value": 1},
        },
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        Form(bfd={"enabled": True, "minimum_interval": 600, "multiplier": 256})

    expected = [
        {
            "loc": ("bfd", "multiplier"),
            "msg": "ensure this value is less than or equal to 255",
            "type": "value_error.number.not_le",
            "ctx": {"limit_value": 255},
        },
    ]
    assert expected == error_info.value.errors()


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


def test_mtu():
    class Form(FormPage):
        mtu: MTU

    assert Form(mtu=1500).mtu == 1500
    assert Form(mtu=1501).mtu == 1501
    assert Form(mtu=9000).mtu == 9000


def test_mtu_schema():
    class Form(FormPage):
        mtu: MTU

    assert Form.schema() == {
        "additionalProperties": False,
        "properties": {
            "mtu": {"maximum": 9000, "minimum": 1500, "multipleOf": 7500, "title": "Mtu", "type": "integer"}
        },
        "required": ["mtu"],
        "title": "unknown",
        "type": "object",
    }


def test_mtu_nok():
    class Form(FormPage):
        mtu: MTU

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=1499)

    expected = [
        {
            "ctx": {"limit_value": 1500},
            "loc": ("mtu",),
            "msg": "ensure this value is greater than or equal to 1500",
            "type": "value_error.number.not_ge",
        }
    ]
    assert expected == error_info.value.errors()

    with pytest.raises(ValidationError) as error_info:
        assert Form(mtu=9001)

    expected = [
        {
            "ctx": {"limit_value": 9000},
            "loc": ("mtu",),
            "msg": "ensure this value is less than or equal to 9000",
            "type": "value_error.number.not_le",
        },
    ]
    assert expected == error_info.value.errors()
