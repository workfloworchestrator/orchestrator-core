import pytest

from orchestrator.api.helpers import getattr_in, product_block_paths, update_in


def test_product_block_paths(sub_list_union_overlap_subscription_1):
    paths = product_block_paths(sub_list_union_overlap_subscription_1)
    assert paths == [
        "product",
        "test_block.sub_block",
        "test_block.sub_block_2",
        "test_block.sub_block_list.0",
        "test_block",
        "list_union_blocks.0",
        "list_union_blocks.1",
    ]

    # Check that SubscriptionModel and subscription dict work the same
    assert product_block_paths(sub_list_union_overlap_subscription_1) == product_block_paths(
        sub_list_union_overlap_subscription_1.model_dump()
    )


class BasicObject:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


SAMPLE_OBJECT = BasicObject(foo=BasicObject(bar="a", baz=[BasicObject(fooo=123)]))


@pytest.mark.parametrize(
    "input_object,path,expected_result",
    [
        ({"foo": "bar"}, "fizz", None),
        ({"foo": "bar"}, "foo", "bar"),
        ({"foo": {"bar": {"fizz": "buzz"}}}, "foo.bar.fizz", "buzz"),
        ({"foo": {"barbar": {"fizz": "buzz"}}}, "foo.bar.fizz", None),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar.fizz.1", "b"),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar.fizz.4", IndexError),
        ({"foo": {"bar": {"fizz": ["a", "b", "c"]}}}, "foo.bar", {"fizz": ["a", "b", "c"]}),
        (BasicObject(), "foo.bar", None),
        (SAMPLE_OBJECT, "foo.bar", "a"),
        (SAMPLE_OBJECT, "foo.barbar", None),
        (SAMPLE_OBJECT, "foo.baz.0.fooo", 123),
        (SAMPLE_OBJECT, "foo.baz.10.fooo", IndexError),
    ],
)
def test_getattr_in(input_object, path, expected_result):
    if isinstance(expected_result, type) and issubclass(expected_result, Exception):
        with pytest.raises(expected_result):
            getattr_in(input_object, path)
    else:
        assert getattr_in(input_object, path) == expected_result


@pytest.mark.parametrize(
    "input_dict,path,value,expected_result",
    [
        pytest.param({}, "foo", "bar", {"foo": "bar"}),
        pytest.param(
            {},
            "foo.x",
            "bar",
            {"foo": {"x": "bar"}},
            marks=[pytest.mark.xfail(reason="Intermediate dicts not created")],
        ),
        pytest.param({"foo": {}}, "foo.x", "bar", {"foo": {"x": "bar"}}),
        pytest.param(
            {},
            "foo.x.y",
            "bar",
            {"foo": {"x": {"y": "bar"}}},
            marks=[pytest.mark.xfail(reason="Intermediate dicts not created")],
        ),
        pytest.param({"foo": "bar"}, "fizz", "buzz", {"foo": "bar", "fizz": "buzz"}),
        pytest.param(
            {"foo": ["bar"]}, "foo.0", "buzz", {"foo": ["buzz"]}, marks=[pytest.mark.xfail(reason="Raises TypeError")]
        ),
    ],
)
def test_update_in(input_dict, path, value, expected_result):
    # TODO fix the failing scenarios
    assert update_in(input_dict, path, value) is None
    assert input_dict == expected_result
