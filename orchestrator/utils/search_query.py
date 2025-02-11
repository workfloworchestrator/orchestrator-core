import re
from collections.abc import Callable, Iterable, Iterator
from enum import Enum
from itertools import chain
from typing import Any, Union, cast

import structlog
from sqlalchemy import BinaryExpression, ColumnElement, CompoundSelect, Select, false, not_, or_
from sqlalchemy.orm import InstrumentedAttribute, MappedColumn

from orchestrator.db.database import BaseModel
from orchestrator.utils.helpers import camel_to_snake

logger = structlog.getLogger(__name__)


class Token(Enum):
    WORD = "WORD"
    OP_OR = "|"
    OP_NEG = "-"
    ASTERISK = "*"
    LPAREN = "("
    RPAREN = ")"
    COLON = ":"
    QUOTE = '"'
    END = "$"

    def __repr__(self) -> str:
        return self.name


SPECIAL_CHARS = {
    "|": Token.OP_OR,
    "-": Token.OP_NEG,
    "*": Token.ASTERISK,
    "(": Token.LPAREN,
    ")": Token.RPAREN,
    ":": Token.COLON,
    '"': Token.QUOTE,
}


class ParseError(RuntimeError):
    pass


Lexeme = Union[tuple[Token], tuple[Token, Any]]


class Lexer:
    word_boundary_regex = re.compile(r'[()|!:<>*\s"]')

    def __init__(self, source: str):
        self.source = source
        self.pos = 0

    def peek(self) -> str | None:
        return self.source[self.pos] if self.pos < len(self.source) else None

    def next_char(self) -> str | None:
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            self.pos += 1
            return ch
        return None

    def read_word(self) -> str:
        chars = []
        while (ch := self.next_char()) and not re.fullmatch(Lexer.word_boundary_regex, ch):
            chars.append(ch)

        # Rewind one, since we read something not part of the word
        if ch:
            self.pos -= 1
        return "".join(chars)

    def lex(self) -> Iterable[Lexeme]:
        self.pos = 0
        max_pos = len(self.source)

        while self.pos < max_pos:
            ch = cast(str, self.peek())  # We know ch can't be None here
            if ch in SPECIAL_CHARS:
                self.pos += 1
                yield SPECIAL_CHARS[ch],
            elif re.fullmatch(Lexer.word_boundary_regex, ch):
                self.pos += 1
            else:
                word = self.read_word()
                yield Token.WORD, word

        yield Token.END,


Node = tuple[str, Any]


class Parser:
    """Class for creating a parse tree from the list of tokens.

    The following grammar is used. Nodenames starting with a _ will not appear in the final parse tree.
    <Query> ::= <AndExpression> ('|' <AndExpression>)*
    <AndExpression> ::= <_Term>*
    <_Term> ::= [<Negation>] <_PositiveTerm>
    <Negation> ::= '-'
    <_PositiveTerm> ::= <Group> | <_Value> | <KVTerm>
    <Group> ::= '(' <Query> ')'
    <Phrase> ::= '"' (<Word> | <PrefixWord>)* '"'
    <KVTerm> ::= <Value> ':' (<_Value> | <ValueGroup>)
    <_SearchWord> ::= <Word> | <PrefixWord>
    <PrefixWord> ::= <Word> '*'
    <Word> ::= <text without "*()!:<> or whitespace>
    <_Value> ::= <Phrase> | <_SearchWord>
    <ValueGroup> ::= '(' <Value> ('|' <Value>)* ')'
    """

    def __init__(self, tokens: Iterable[Lexeme]):
        """Args: tokens - An iterable yielding lexemes.

        `tokens` must not be empty. The result from the Lexer class
        will always end with (END,) and so is never empty.
        Ensure that next_token() is never called after the (END,)
        token is consumed.
        """
        self.tokens = tokens
        self.it: Iterator[Lexeme] = iter([])

    def peek(self) -> Lexeme:
        token = next(self.it)
        self.it = chain([token], self.it)
        return token

    def next_token(self) -> Lexeme:
        return next(self.it)

    def error(self, msg: str) -> None:
        logger.debug(msg)

    def expect(self, expected_type: Token) -> Lexeme:
        nt = self.next_token()
        if nt[0] != expected_type:
            msg = f"Expected {expected_type}, got {nt[0]}"
            self.error(msg)
            raise ParseError(msg)
        return nt

    def parse_value_group(self) -> Node | None:
        self.expect(Token.LPAREN)
        value = self.parse_value()
        if not value:
            return None
        values = [value]
        while next_token := self.peek():
            if next_token[0] == Token.RPAREN:
                break
            if next_token[0] == Token.OP_OR:
                self.expect(Token.OP_OR)
                if next_value := self.parse_value():
                    values.append(next_value)
            else:
                raise ParseError(f"Expected a Value or ')', got {next_token}")

        self.expect(Token.RPAREN)
        return "ValueGroup", values

    def parse_value(self) -> Node | None:
        next_token = self.peek()
        if next_token[0] == Token.QUOTE:
            return self.parse_phrase()
        if next_token[0] == Token.WORD:
            return self.parse_search_word()
        return None

    def parse_search_word(self) -> Node:
        word = cast(tuple, self.expect(Token.WORD))
        next_token = self.peek()
        if next_token[0] == Token.ASTERISK:
            self.next_token()
            return "PrefixWord", word[1]
        return "Word", word[1]

    def parse_phrase(self) -> Node:
        self.expect(Token.QUOTE)
        search_words = []
        while not self.peek()[0] == Token.QUOTE:
            if not (self.peek()[0] == Token.WORD):
                self.error(f"Expected a Word or PrefixWord inside phrase. Got: {self.peek()}")
                break

            search_words.append(self.parse_search_word())

        self.expect(Token.QUOTE)
        return "Phrase", search_words

    def parse_group(self) -> Node:
        self.expect(Token.LPAREN)
        query = self.parse_query()
        self.expect(Token.RPAREN)
        return "Group", query[1] if query else []

    def parse_positive_term(self) -> Node | None:
        # Should return None if not a valid term
        token = self.peek()
        if token[0] == Token.LPAREN:
            return self.parse_group()

        value = self.parse_value()
        if not value:
            return None
        next_token = self.peek()
        if next_token and next_token[0] == Token.COLON:
            # It's a KVTerm, e.g. status:active
            self.next_token()
            next_token = self.peek()
            kv_value = self.parse_value_group() if next_token[0] == Token.LPAREN else self.parse_value()

            # An empty value is normally not a problem, but it is in a KVTerm, so we check for it.
            if not kv_value or kv_value[0] == "Phrase" and not kv_value[1]:
                raise ParseError("Value term in KVTerm can not be empty.")
            return "KVTerm", (value, kv_value)
        return value

    def parse_term(self) -> Node | None:
        token = self.peek()
        if token[0] == Token.OP_NEG:
            self.next_token()
            term = self.parse_positive_term()
            return ("Negation", term) if term else None
        return self.parse_positive_term()

    def parse_and_expression(self) -> Node | None:
        terms = []
        while term := self.parse_term():
            terms.append(term)

        return ("AndExpression", terms) if terms else None

    def parse_query(self) -> Node:
        expressions = []
        while True:
            and_expression = self.parse_and_expression()
            if and_expression:
                expressions.append(and_expression)
            if self.peek()[0] not in [Token.END, Token.RPAREN]:
                self.expect(Token.OP_OR)
            else:
                break
        return "Query", expressions

    def parse(self) -> Node:
        self.it = iter(self.tokens)
        query = self.parse_query()
        self.expect(Token.END)
        return query


class TSQueryVisitor:
    _glue_chars = re.compile(r"[-_@#$%^&]")

    @staticmethod
    def _split_term(term: str) -> list[str]:
        return [part.strip() for part in TSQueryVisitor._glue_chars.split(term) if part and not part.isspace()]

    @staticmethod
    def visit_group(node: Node, acc: list[str]) -> None:
        acc.append("(")
        for expr in node[1]:
            TSQueryVisitor.visit_and_expression(expr, acc)
            acc.append(" | ")
        acc.pop()
        acc.append(")")

    @staticmethod
    def visit_kv_term(node: Node, acc: list[str]) -> None:
        key_node, value_node = node[1]

        # Re-use visit_term
        if key_node[0] == "Word":
            # Camel case key term
            key_node = ["Word", camel_to_snake(key_node[1])]
        TSQueryVisitor.visit_term(key_node, acc)
        acc.append(" <-> ")

        if value_node[0] == "ValueGroup":
            acc.append("(")
            for v in value_node[1]:
                TSQueryVisitor.visit_term(v, acc)
                acc.append(" | ")
            acc.pop()
            acc.append(")")
        else:
            TSQueryVisitor.visit_term(value_node, acc)

    @staticmethod
    def visit_search_word(node: Node, acc: list[str]) -> None:

        if node[0] not in ["Word", "PrefixWord"]:
            raise Exception(f"Invalid SearchWord type {node[0]}")

        # Postgres is finicky with single quotes in the query. In some situations it throws an error.
        # To avoid the special handling of ' by PG, we replace it with double quotes.

        text = node[1].replace("'", '"')

        parts = TSQueryVisitor._split_term(text)

        if not parts:
            return

        text = " <-> ".join(parts)

        if node[0] == "PrefixWord":
            text = f"{text}:*"

        # Wrap parentheses for clarity, even though <-> has the highest operator precedence
        text = f"({text})" if len(parts) > 1 else text
        acc.append(text)

    @staticmethod
    def visit_phrase(node: Node, acc: list[str]) -> None:
        for search_word in node[1]:
            TSQueryVisitor.visit_search_word(search_word, acc)
            acc.append(" <-> ")

        if len(node[1]):
            acc.pop()  # Remove trailing space

    @staticmethod
    def visit_term(node: Node, acc: list[str]) -> None:
        node_type = node[0]
        if node_type == "Phrase":
            TSQueryVisitor.visit_phrase(node, acc)
        elif node_type in ["Word", "PrefixWord"]:
            TSQueryVisitor.visit_search_word(node, acc)
        elif node_type == "KVTerm":
            TSQueryVisitor.visit_kv_term(node, acc)
        elif node_type == "Group":
            TSQueryVisitor.visit_group(node, acc)
        elif node_type == "Negation":
            acc.append("!")
            should_group = node[1][0] in ["Phrase", "KVTerm"]
            if should_group:
                acc.append("(")
            TSQueryVisitor.visit_term(node[1], acc)
            if should_group:
                acc.append(")")
        else:
            raise Exception(f"Unexpected term node type: {node_type}")

    @staticmethod
    def visit_and_expression(node: Node, acc: list[str]) -> None:
        for term in node[1]:
            TSQueryVisitor.visit_term(term, acc)
            acc.append(" & ")
        if len(node[1]):
            acc.pop()

    @staticmethod
    def visit_query(node: Node, acc: list[str]) -> None:
        for expression in node[1]:
            TSQueryVisitor.visit_and_expression(expression, acc)
            acc.append(" | ")

        if len(node[1]):
            acc.pop()

    @staticmethod
    def visit(parse_tree: Node) -> str:
        acc: list[str] = []
        node_type = parse_tree[0]
        if node_type == "Query":
            TSQueryVisitor.visit_query(parse_tree, acc)
        return "".join(acc)


WhereCondGenerator = Callable[[Node], Union[BinaryExpression, ColumnElement[bool]]]


class SQLAlchemyVisitor:
    def __init__(
        self,
        stmt: Select,
        mappings: dict[str, WhereCondGenerator],
        *,
        base_table: type[BaseModel] | None = None,
        join_key: MappedColumn | InstrumentedAttribute | None = None,
    ):
        self.base_stmt = stmt
        self.mappings = mappings
        # base_table and join_key are required for group terms, because of the union join
        # If the query does not use grouping, these parameters are optional
        self.base_table = base_table
        self.join_key = join_key

    def visit_kv_term(self, stmt: Select, node: Node, is_negated: bool) -> Select:
        key_node, value_node = node[1]
        if key_node[0] == "Word":
            cond_expr_fn = self.mappings.get(camel_to_snake(key_node[1]))
            if not cond_expr_fn:
                # Non-existing columns will emit `where false`, returning no results
                return stmt.where(false())
            if value_node[0] in ["Word", "PrefixWord", "Phrase"]:
                cond_expr = cond_expr_fn(value_node)
                return stmt.where(cond_expr if not is_negated else not_(cond_expr))
            if value_node[0] == "ValueGroup":
                ors = [cond_expr_fn(vg_node) for vg_node in value_node[1]]
                or_expr = or_(False, *ors)
                cond_expr2 = or_expr if not is_negated else not_(or_expr)
                return stmt.where(cond_expr2)

        # Only Word or single-term Phrase key-nodes are supported.
        if key_node[0] == "Phrase" and len(key_node[1]) == 1:
            return self.visit_kv_term(stmt, ("KVTerm", (key_node[1][0], value_node)), is_negated)
        return stmt

    def visit_search_word(self, stmt: Select, node: Node, is_negated: bool) -> Select:
        # The dynamically generated list of expression may not be empty, so we prepend with a "default" False
        or_expr = or_(False, *(cond_expr_fn(node) for cond_expr_fn in self.mappings.values()))
        return stmt.where(or_expr if not is_negated else not_(or_expr))

    def visit_group(self, stmt: Select, node: Node, is_negated: bool) -> Select:
        if self.join_key is None or self.base_table is None:
            logger.error("Group statements not supported without a base_table and a join_key")
            return stmt
        subquery = self.visit_query(self.base_stmt, node).cte()
        if is_negated:
            return stmt.outerjoin_from(
                self.base_table, subquery, self.join_key == subquery.c[self.join_key.name]
            ).where(subquery.c[self.join_key.name].is_(None))
        return stmt.join_from(self.base_table, subquery, self.join_key == subquery.c[self.join_key.name])

    def visit_term(self, stmt: Select, node: Node, is_negated: bool = False) -> Select:
        node_type = node[0]
        if node_type == "KVTerm":
            return self.visit_kv_term(stmt, node, is_negated)
        if node_type == "Negation":
            return self.visit_term(stmt, node[1], is_negated=True)
        if node_type in ["Word", "PrefixWord", "Phrase"]:
            return self.visit_search_word(stmt, node, is_negated)
        if node_type == "Group":
            return self.visit_group(stmt, node, is_negated)
        raise Exception(f"Unexpected term node type: {node_type}")

    def visit_and_expression(self, stmt: Select, node: Node) -> Select:
        for term in node[1]:
            stmt = self.visit_term(stmt, term)
        return stmt

    def visit_query(self, stmt: Select, node: Node) -> Select | CompoundSelect:
        stmt = self.visit_and_expression(stmt, node[1][0])
        if len(node[1]) > 1:
            return stmt.union(*(self.visit_and_expression(self.base_stmt, expression) for expression in node[1][1:]))
        return stmt

    def visit(self, parse_tree: Node) -> Select | CompoundSelect:
        node_type = parse_tree[0]
        if node_type == "Query":
            return self.visit_query(self.base_stmt, parse_tree)
        return self.base_stmt


def create_ts_query_string(search_query: str) -> str:
    return TSQueryVisitor.visit(Parser(Lexer(search_query).lex()).parse())


def create_sqlalchemy_select(
    stmt: Select,
    search_query: str,
    mappings: dict[str, WhereCondGenerator],
    base_table: type[BaseModel],
    join_key: MappedColumn | InstrumentedAttribute,
) -> Select | CompoundSelect:
    return SQLAlchemyVisitor(stmt, mappings, base_table=base_table, join_key=join_key).visit(
        Parser(Lexer(search_query).lex()).parse()
    )
