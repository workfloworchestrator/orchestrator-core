import pytest

from orchestrator.forms import FormNotCompleteError, FormPage, FormValidationError, generate_form, post_process
from orchestrator.types import strEnum
from orchestrator.utils.json import json_dumps, json_loads


class TestChoices(strEnum):
    A = "a"
    B = "b"


class TestForm(FormPage):
    generic_select: TestChoices


def test_post_process_yield():
    def input_form(state):
        user_input = yield TestForm
        return {**user_input.dict(), "extra": 234}

    validated_data = post_process(input_form, {"previous": True}, [{"generic_select": "a"}])

    expected = {"generic_select": "a", "extra": 234}
    assert expected == json_loads(json_dumps(validated_data))


def test_post_process_extra_data():
    def input_form(state):
        user_input = yield TestForm
        return {**user_input.dict(), "extra": 234}

    with pytest.raises(FormValidationError) as e:
        post_process(input_form, {"previous": True}, [{"generic_select": "a", "extra_data": False}])

    assert (
        str(e.value)
        == "1 validation error for TestForm\nextra_data\n  extra fields not permitted (type=value_error.extra)"
    )


def test_post_process_validation_errors():
    def input_form(state):
        user_input = yield TestForm
        return user_input.dict()

    with pytest.raises(FormValidationError) as e:
        post_process(input_form, {}, [{"generic_select": 1, "extra_data": False}])

    assert (
        str(e.value)
        == "2 validation errors for TestForm\ngeneric_select\n  value is not a valid enumeration member; permitted: 'a', 'b' (type=type_error.enum; enum_values=[<TestChoices.A: 'a'>, <TestChoices.B: 'b'>])\nextra_data\n  extra fields not permitted (type=value_error.extra)"
    )

    with pytest.raises(FormValidationError) as e:
        post_process(input_form, {}, [{"generic_select": 1}])

    assert (
        str(e.value)
        == "1 validation error for TestForm\ngeneric_select\n  value is not a valid enumeration member; permitted: 'a', 'b' (type=type_error.enum; enum_values=[<TestChoices.A: 'a'>, <TestChoices.B: 'b'>])"
    )


def test_post_process_wizard():
    # Return if there is no form
    assert post_process(None, {}, []) == {}
    assert post_process([], {}, []) == {}

    def input_form(state):
        class TestForm1(FormPage):
            generic_select1: TestChoices

            class Config:
                title = "Some title"

        class TestForm2(FormPage):
            generic_select2: TestChoices

        class TestForm3(FormPage):
            generic_select3: TestChoices

        user_input_1 = yield TestForm1

        if user_input_1.generic_select1 == TestChoices.A:
            user_input_2 = yield TestForm2
        else:
            user_input_2 = yield TestForm3

        return {**user_input_1.dict(), **user_input_2.dict()}

    # Submit 1
    with pytest.raises(FormNotCompleteError) as error_info:
        post_process(input_form, {"previous": True}, [])

    assert error_info.value.form == {
        "title": "Some title",
        "type": "object",
        "additionalProperties": False,
        "definitions": {
            "TestChoices": {
                "description": "An enumeration.",
                "enum": ["a", "b"],
                "title": "TestChoices",
                "type": "string",
            }
        },
        "properties": {"generic_select1": {"$ref": "#/definitions/TestChoices"}},
        "required": ["generic_select1"],
    }

    # Submit 2
    with pytest.raises(FormNotCompleteError) as error_info:
        post_process(input_form, {"previous": True}, [{"generic_select1": "b"}])

    assert error_info.value.form == {
        "title": "unknown",
        "type": "object",
        "additionalProperties": False,
        "definitions": {
            "TestChoices": {
                "description": "An enumeration.",
                "enum": ["a", "b"],
                "title": "TestChoices",
                "type": "string",
            }
        },
        "properties": {"generic_select3": {"$ref": "#/definitions/TestChoices"}},
        "required": ["generic_select3"],
    }

    # Submit complete
    validated_data = post_process(input_form, {"previous": True}, [{"generic_select1": "b"}, {"generic_select3": "a"}])

    expected = {"generic_select1": "b", "generic_select3": "a"}
    assert expected == json_loads(json_dumps(validated_data))

    # Submit overcomplete
    validated_data = post_process(
        input_form, {"previous": True}, [{"generic_select1": "b"}, {"generic_select3": "a"}, {"to_much": True}]
    )

    expected = {"generic_select1": "b", "generic_select3": "a"}
    assert expected == json_loads(json_dumps(validated_data))


def test_generate_form():
    def input_form(state):
        class TestForm1(FormPage):
            generic_select1: TestChoices

            class Config:
                title = "Some title"

        class TestForm2(FormPage):
            generic_select2: TestChoices

        class TestForm3(FormPage):
            generic_select3: TestChoices

        user_input_1 = yield TestForm1

        if user_input_1.generic_select1 == TestChoices.A:
            user_input_2 = yield TestForm2
        else:
            user_input_2 = yield TestForm3

        return {**user_input_1.dict(), **user_input_2.dict()}

    # Submit 1
    form = generate_form(input_form, {"previous": True}, [])

    assert form == {
        "title": "Some title",
        "type": "object",
        "additionalProperties": False,
        "definitions": {
            "TestChoices": {
                "description": "An enumeration.",
                "enum": ["a", "b"],
                "title": "TestChoices",
                "type": "string",
            }
        },
        "properties": {"generic_select1": {"$ref": "#/definitions/TestChoices"}},
        "required": ["generic_select1"],
    }

    # Submit 2
    form = generate_form(input_form, {"previous": True}, [{"generic_select1": "b"}])

    assert form == {
        "title": "unknown",
        "type": "object",
        "additionalProperties": False,
        "definitions": {
            "TestChoices": {
                "description": "An enumeration.",
                "enum": ["a", "b"],
                "title": "TestChoices",
                "type": "string",
            }
        },
        "properties": {"generic_select3": {"$ref": "#/definitions/TestChoices"}},
        "required": ["generic_select3"],
    }

    # Submit complete
    form = generate_form(input_form, {"previous": True}, [{"generic_select1": "b"}, {"generic_select3": "a"}])
    assert form is None
