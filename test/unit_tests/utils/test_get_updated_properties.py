from orchestrator.utils.get_updated_properties import get_updated_properties


def test_get_updated_fields_with_root_props():
    obj1 = {
        "unchanged": "unchanged",
        "update": "to_update",
        "removed": "to_remove",
    }

    obj2 = {
        "unchanged": "unchanged",
        "update": "updated_prop",
        "new_prop": "new",
    }

    updated_props = get_updated_properties(obj1, obj2)

    assert updated_props == {
        "update": "updated_prop",
        "new_prop": "new",
    }


def test_get_updated_fields_with_list_props():
    obj1 = {
        "list_unchanged": [1, 2, 3],
        "list_update_item": [1, 2, 3],
        "list_update_and_new": [1, 2, 3],
        "list_update_and_new_and_remove": [1, 2, 3],
        "list_remove": [1, 2, 3],
    }

    obj2 = {
        "list_unchanged": [1, 2, 3],
        "list_update_item": [80, 2, 20],
        "list_update_and_new": [80, 2, 20, 30],
        "list_update_and_new_and_remove": [80, 2],
        "list_new": [10, 11, 12],
    }

    updated_props = get_updated_properties(obj1, obj2)

    assert updated_props == {
        "list_update_item": [80, 2, 20],
        "list_update_and_new": [80, 2, 20, 30],
        "list_update_and_new_and_remove": [80, 2],
        "list_new": [10, 11, 12],
    }


def test_get_updated_fields_with_dict_props():
    obj1 = {
        "dict_unchanged": {"unchanged": "unchanged"},
        "dict_update": {
            "unchanged": "unchanged",
            "update": "to update",
        },
        "dict_update_and_new": {
            "unchanged": "unchanged",
            "update": "to update",
        },
        "dict_update_and_remove": {
            "unchanged": "unchanged",
            "update": "to update",
            "update_dict": {"nested": "dict"},
            "remove": "to remove",
        },
        "dict_remove": {"remove": "to remove"},
    }

    obj2 = {
        "dict_unchanged": {"unchanged": "unchanged"},
        "dict_update": {
            "unchanged": "unchanged",
            "update": "updated prop",
        },
        "dict_update_and_new": {
            "unchanged": "unchanged",
            "update": "updated prop",
            "new_dict": {"nested": "dict"},
        },
        "dict_update_and_remove": {
            "unchanged": "unchanged",
            "update": "updated prop",
            "update_dict": {"nested": "dict update"},
        },
        "dict_new": {
            "new": "dict",
        },
    }

    updated_props = get_updated_properties(obj1, obj2)

    assert updated_props == {
        "dict_update": {"update": "updated prop"},
        "dict_update_and_new": {"update": "updated prop", "new_dict": {"nested": "dict"}},
        "dict_update_and_remove": {"update": "updated prop", "update_dict": {"nested": "dict update"}},
        "dict_new": {"new": "dict"},
    }


def test_get_updated_fields_with_mixed_props():
    obj1 = {
        "test": "test",
        "update": "test",
        "nested": {"key1": "value1", "key2": "value2"},
        "list": [1, 2, 3],
        "list_dict": [{"test": "test"}],
    }

    obj2 = {
        "test": "test",
        "update": "updated",
        "nested": {"key1": "value1", "key2": "updated_value"},
        "list": [1, 2, 4],
        "list_dict": [{"test": "update"}],
    }

    updated_props = get_updated_properties(obj1, obj2)

    assert updated_props == {
        "update": "updated",
        "nested": {"key2": "updated_value"},
        "list": [1, 2, 4],
        "list_dict": [{"test": "update"}],
    }
