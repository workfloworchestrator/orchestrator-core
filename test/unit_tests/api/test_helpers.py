import pytest

from orchestrator.api.helpers import (
    _process_text_query,
    _quote_if_kv_pair,
    get_in,
    getattr_in,
    product_block_paths,
    update_in,
)


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


@pytest.mark.parametrize(
    "token,expected",
    [
        ("foo:bar", '"foo:bar"'),
        ("status:active", '"status:active"'),
        ("plaintoken", "plaintoken"),
        ("", ""),
        ("no-colon-here", "no-colon-here"),
        ("a:b:c", '"a:b:c"'),
    ],
)
def test_quote_if_kv_pair(token, expected):
    assert _quote_if_kv_pair(token) == expected


@pytest.mark.parametrize(
    "query,expected",
    [
        # plain tokens: passed through unchanged
        ("hello world", "hello world"),
        # quoted phrase: shlex non-posix mode preserves quotes
        ('"exact phrase"', '"exact phrase"'),
        # two tokens, first is quoted phrase; quotes preserved in non-posix shlex
        ('"foo bar" baz', '"foo bar" baz'),
        # unbalanced quote: closing quote added, then preserved
        ('"unclosed phrase', '"unclosed phrase"'),
        # token with colon: gets wrapped in quotes
        ("status:active", '"status:active"'),
        # plain token + kv pair
        ("hello status:active", 'hello "status:active"'),
        # kv pair inside quotes: shlex preserves quotes, colon triggers double-wrapping
        ('"status:active"', '""status:active""'),
        # empty query
        ("", ""),
    ],
)
def test_process_text_query(query, expected):
    assert _process_text_query(query) == expected


@pytest.mark.parametrize(
    "dct,path,expected",
    [
        # simple key lookup
        ({"a": 1}, "a", 1),
        # nested dict path
        ({"a": {"b": {"c": 42}}}, "a.b.c", 42),
        # nested: dict then list then dict (list in the middle, final lookup is dict key)
        ({"a": [{"b": 99}]}, "a.0.b", 99),
    ],
)
def test_get_in(dct, path, expected):
    assert get_in(dct, path) == expected


def test_get_in_list_as_final_segment_raises_type_error():
    # get_in uses prev[x] with string x at the end, which fails on list
    with pytest.raises(TypeError):
        get_in({"a": [10, 20, 30]}, "a.1")


def test_get_in_missing_key_raises():
    # dict.get(x) returns None, then prev[x] does a real key lookup and raises
    with pytest.raises(KeyError):
        get_in({"a": 1}, "b")


def test_get_in_missing_nested_key_raises():
    # dict.get("c") returns None, then prev["c"] raises KeyError
    with pytest.raises(KeyError):
        get_in({"a": {"b": 1}}, "a.c")


def test_get_in_list_index_out_of_range():
    with pytest.raises(IndexError):
        get_in({"a": [1, 2, 3]}, "a.10")
