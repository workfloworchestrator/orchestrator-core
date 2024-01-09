import pytest

from orchestrator.utils.search_query import Lexer, ParseError, Parser, TSQueryVisitor


def _parse_tree_and_tsquery(q: str) -> tuple[tuple, str]:
    tokens = Lexer(q).lex()
    tree = Parser(tokens).parse()
    tsquery = TSQueryVisitor.visit(tree)
    return tree, tsquery


def test_parse_simple_query():
    q = "simple query with words"
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert parse_tree == (
        "Query",
        [("AndExpression", [("Word", "simple"), ("Word", "query"), ("Word", "with"), ("Word", "words")])],
    )
    assert tsquery == "simple & query & with & words"


def test_parse_query_with_phrase():
    q = 'word1 "some consecutive words" end'
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert parse_tree == (
        "Query",
        [
            (
                "AndExpression",
                [
                    ("Word", "word1"),
                    ("Phrase", [("Word", "some"), ("Word", "consecutive"), ("Word", "words")]),
                    ("Word", "end"),
                ],
            )
        ],
    )
    assert tsquery == "word1 & some <-> consecutive <-> words & end"


@pytest.mark.parametrize(
    "query, msg",
    [
        ("a )", "Right paren before left paren"),
        ('tag:""', "Empty Value in KVTerm"),
        ("tag:()", "Empty ValueGroup in KVTerm"),
        ('this "is unbalanced', "Missing closing quote"),
        ("a (unclosed group", "Missing closing parenthesis"),
    ],
)
def test_parse_errors(query, msg):
    with pytest.raises(
        ParseError,
    ):
        _parse_tree_and_tsquery(query)


def test_parse_edge_cases():
    # Just test whether this parses without error
    q = "aa*bb@cc?dd>ee'ff_g<g[hh]ij$kk%;\\=+12`3€crazy!text kk|ll:''"
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert tsquery.startswith("aa:*")
    assert tsquery.endswith('| ll <-> ""')


def test_parse_complex_query():
    q = "".join(
        [
            '"phrase1 phrase2 phrase3" word1 word2 prefixword* field1:(val1 | val2* | "val3 val4*")',
            " | ",
            '"phrase21 phrase22" ((klm tag:lp) | (sinica tag:fw)) -("not this" "or this") something else',
        ]
    )

    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert len(parse_tree[1]) == 2
    first_subexpression = parse_tree[1][0]
    second_subexpression = parse_tree[1][1]
    assert len(first_subexpression[1]) == 5, "subexpression 1 has 5 terms"
    assert len(second_subexpression[1]) == 5, "subexpression 2 has 5 terms"
    assert tsquery == "".join(
        [
            "phrase1 <-> phrase2 <-> phrase3 & word1 & word2 & prefixword:* & field1 <-> (val1 | val2:* | val3 <-> val4:*)",
            " | ",
            "phrase21 <-> phrase22 & ((klm & tag <-> lp) | (sinica & tag <-> fw))",
            " & !(not <-> this & or <-> this) & something & else",
        ]
    )


def test_query_with_underscores():
    q = 'word_with_underscores prefix_word* key_value:term_1 key_value2:(val_1 | "val_2" | val_3*)'
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert (
        tsquery
        == "word <-> with <-> underscores & prefix <-> word:* & key <-> value <-> term <-> 1 & key <-> value2 <-> (val <-> 1 | val <-> 2 | val <-> 3:*)"
    )
