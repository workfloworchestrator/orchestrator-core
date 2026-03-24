from orchestrator.cli.generator.generator.validations import (
    get_all_validations,
    get_validation_imports,
    get_validations,
)


def test_get_all_validations_empty_fields() -> None:
    result = get_all_validations([])
    assert result == []


def test_get_all_validations_without_validations() -> None:
    fields = [{"name": "field1", "type": "str"}, {"name": "field2", "type": "int"}]
    result = get_all_validations(fields)
    assert result == []


def test_get_all_validations_with_validations() -> None:
    fields = [
        {
            "name": "field1",
            "type": "str",
            "validations": [{"id": "min_length", "value": 1}, {"id": "max_length", "value": 10}],
        },
        {
            "name": "field2",
            "type": "int",
            "validations": [{"id": "positive"}],
        },
    ]
    result = get_all_validations(fields)
    assert len(result) == 3
    assert result[0] == {"validation": {"id": "min_length", "value": 1}, "field": fields[0]}
    assert result[1] == {"validation": {"id": "max_length", "value": 10}, "field": fields[0]}
    assert result[2] == {"validation": {"id": "positive"}, "field": fields[1]}


def test_get_validation_imports() -> None:
    validations = [
        {"validation": {"id": "min_length"}, "field": {"name": "field1"}},
        {"validation": {"id": "max_length"}, "field": {"name": "field1"}},
        {"validation": {"id": "positive"}, "field": {"name": "field2"}},
    ]
    result = get_validation_imports(validations)
    assert result == ["min_length_validator", "max_length_validator", "positive_validator"]


def test_get_validations_create_workflow() -> None:
    fields = [
        {
            "name": "field1",
            "type": "str",
            "modifiable": False,
            "validations": [{"id": "min_length"}],
        },
        {
            "name": "field2",
            "type": "str",
            "modifiable": True,
            "validations": [{"id": "max_length"}],
        },
    ]
    validations, imports = get_validations(fields, workflow="create")
    assert len(validations) == 2
    assert imports == ["min_length_validator", "max_length_validator"]


def test_get_validations_modify_workflow() -> None:
    fields = [
        {
            "name": "field1",
            "type": "str",
            "modifiable": False,
            "validations": [{"id": "min_length"}],
        },
        {
            "name": "field2",
            "type": "str",
            "modifiable": True,
            "validations": [{"id": "max_length"}],
        },
    ]
    validations, imports = get_validations(fields, workflow="modify")
    assert len(validations) == 1
    assert validations[0]["field"]["name"] == "field2"
    assert imports == ["max_length_validator"]


def test_get_validations_modify_workflow_no_modifiable() -> None:
    fields = [
        {
            "name": "field1",
            "type": "str",
            "modifiable": False,
            "validations": [{"id": "min_length"}],
        },
    ]
    validations, imports = get_validations(fields, workflow="modify")
    assert validations == []
    assert imports == []
