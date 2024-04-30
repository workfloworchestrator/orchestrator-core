import uuid

import pytest
from sqlalchemy import Column, Integer, String, func, select

from orchestrator.db import db
from orchestrator.db.database import BaseModel
from orchestrator.db.helpers import to_sql_string
from orchestrator.utils.search_query import Lexer, ParseError, Parser, TSQueryVisitor, create_sqlalchemy_select


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
        ("tag:(a | *b(", "Unexpected token in ValueGroup"),
        ('this "is unbalanced', "Missing closing quote"),
        ("a (unclosed group", "Missing closing parenthesis"),
    ],
)
def test_parse_errors(query, msg):
    with pytest.raises(ParseError):
        _parse_tree_and_tsquery(query)


def test_parse_edge_cases():
    # Just test whether this parses without error
    q = "aa*bb@cc?dd>ee'ff_g<g[hh]ij$kk%;\\=+12`3€crazy!text kk|ll:m"
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert tsquery.startswith("aa:*")
    assert tsquery.endswith("| ll <-> m")


@pytest.mark.parametrize(
    "query,expected_tsquery",
    [
        ("basic query example", "basic & query & example"),
        ("example status:(suspended | terminated)", "example & status <-> (suspended | terminated)"),
        (
            "subscription_id:849fb72a-4366-4d41-9d37-3821d73e4dd4",
            "(subscription <-> id) <-> (849fb72a <-> 4366 <-> 4d41 <-> 9d37 <-> 3821d73e4dd4)",
        ),
        ("something aaa_bbb else", "something & (aaa <-> bbb) & else"),
    ],
)
def test_common_queries(query, expected_tsquery):
    _, tsquery = _parse_tree_and_tsquery(query)
    assert tsquery == expected_tsquery


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
    q = 'word_with_underscores prefix_word* key_value:term_1 key_value2:(val1 | "val2" | val3*)'
    parse_tree, tsquery = _parse_tree_and_tsquery(q)
    assert (
        tsquery
        == "(word <-> with <-> underscores) & (prefix <-> word:*) & (key <-> value) <-> (term <-> 1) & (key <-> value2) <-> (val1 | val2 | val3:*)"
    )


def test_query_kv_camelcasing():
    q = "productTag:myTag"
    q2 = "product_tag:myTag"
    assert _parse_tree_and_tsquery(q)[1] == _parse_tree_and_tsquery(q2)[1]


@pytest.mark.parametrize(
    "search_query,substrings",
    [
        ("name:Bob", ["WHERE my_table.name LIKE 'bob'"]),
        ("empty:column", ["WHERE false"]),
        ("bob| joe", ["WHERE my_table.name LIKE 'bob'", "UNION SELECT", "WHERE my_table.name LIKE 'joe'"]),
        ("(bob) | -(joe)", ["WHERE my_table.name LIKE 'bob'", "UNION SELECT", "WHERE my_table.name LIKE 'joe'"]),
        ("-(joe)", ["WITH", "LEFT OUTER JOIN", ".id IS NULL"]),
    ],
)
def test_sqlalchemy_visitor(search_query, substrings):
    class MyTable(BaseModel):
        __tablename__ = "my_table"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    mappings = {"name": lambda node: MyTable.name.like(node[1].lower())}
    stmt = select(MyTable)
    stmt = create_sqlalchemy_select(stmt, search_query, mappings, MyTable, MyTable.id)
    for substring in substrings:
        assert substring in to_sql_string(stmt)

    MyTable.metadata.clear()


@pytest.mark.parametrize("i", range(100))
def test_uuid_queries(i):
    # Tests whether a text search vector containing a UUID can be successfully queried
    # This used to fail sometimes in Postgres <14 versions.

    # TODO: Remove when support for Postgres <14 is dropped
    uid = uuid.uuid4()

    query = f"subscription_id:{uid}"
    tsv = func.to_tsvector("simple", func.replace(query, "-", "_"))

    _, ts_query = _parse_tree_and_tsquery(query)

    stmt = select(tsv.op("@@")(func.to_tsquery("simple", ts_query)))

    matches = db.session.scalar(stmt)
    assert matches
