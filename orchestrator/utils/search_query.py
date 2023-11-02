from enum import Enum
from itertools import chain
from typing import Optional, Iterable
import re


class Token(Enum):
    WORD = "WORD"
    OP_OR = "|"
    OP_NEG = "-"
    OP_PREFIX = "*"
    LPAREN = "("
    RPAREN = ")"
    SEMICOLON = ":"
    QUOTE = "\""
    END = "$"

    def __repr__(self):
        return self.name


SPECIAL_CHARS = {
    "|": Token.OP_OR,
    "-": Token.OP_NEG,
    "*": Token.OP_PREFIX,
    "(": Token.LPAREN,
    ")": Token.RPAREN,
    ":": Token.SEMICOLON,
    "\"": Token.QUOTE
}


class Lexer:

    def __init__(self, source: str):
        self.source = source
        self.pos = 0

    def peek(self) -> Optional[str]:
        return self.source[self.pos] if self.pos < len(self.source) else None

    def next_char(self) -> Optional[str]:
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            self.pos += 1
            return ch

    def read_word(self) -> str:
        chars = []
        while (ch := self.next_char()) and ch not in '()|!:<>*"' and not re.fullmatch(r'\s', ch):
            chars.append(ch)

        # Rewind one, since we read something not part of the word
        if ch:
            self.pos -= 1
        return ''.join(chars)

    def lex(self):
        self.pos = 0
        max_pos = len(self.source)

        while self.pos < max_pos:
            ch = self.peek()
            if ch in SPECIAL_CHARS:
                self.pos += 1
                yield SPECIAL_CHARS[ch],
            elif re.match(r'\s', ch):
                self.pos += 1
            else:
                yield Token.WORD, self.read_word()

        yield Token.END,


class Parser:
    """
    <Query> ::= <AndExpression> (<OrOperator> <AndExpression>)*
    <_OrOperator> ::= '|'
    <AndExpression> ::= <Term>*
    <_Term> ::= [<NegationOperator>] <PositiveTerm>
    <NegationOperator> ::= '-'
    <_PositiveTerm> ::= <Group> | <_Value> | <KVTerm>
    <Group> ::= '(' <Query> ')'
    <Phrase> ::= '"' (<Word> | <PrefixWord>)* '"'
    <KVTerm> ::= <Value> ':' (<_Value> | <ValueGroup>)
    <PrefixWord> ::= <Word> '*'
    <Word> ::= <text without "*()!:<> or whitespace>
    <_Value> ::= <Phrase> | <SearchWord>
    <ValueGroup> ::= '(' <Value> (<OrOperator> <Value>)* ')'
    """

    def __init__(self, tokens: Iterable):
        self.tokens = tokens
        self.it = None

    def peek(self):
        token = next(self.it, None)
        self.it = chain([token], self.it)
        return token

    def next_token(self):
        return next(self.it, None)

    def error(self, msg):
        print(msg)

    def expect(self, expected_type):
        nt = self.next_token()
        if nt[0] != expected_type:
            self.error(f"Expected {expected_type}, got {nt[0]}")
            raise Exception("Parse error")
        return nt

    def parse_value_group(self):
        self.expect(Token.LPAREN)
        values = [self.parse_value()]
        while next_token := self.peek():
            if next_token[0] == Token.END:
                self.error("Unexpected end of stream. Expected an ')'")
            elif next_token[0] == Token.RPAREN:
                break
            elif next_token[0] == Token.OP_OR:
                self.expect(Token.OP_OR)
                values.append(self.parse_value())
            else:
                self.error(f"Expected a Value or ')', got {next_token}")
        self.expect(Token.RPAREN)
        return 'ValueGroup', values

    def parse_value(self):
        next_token = self.peek()
        if next_token[0] == Token.QUOTE:
            return self.parse_phrase()
        elif next_token[0] == Token.WORD:
            return self.parse_search_word()
        else:
            return None

    def parse_search_word(self):
        word = self.expect(Token.WORD)
        next_token = self.peek()
        if next_token[0] == Token.OP_PREFIX:
            self.next_token()
            return 'PrefixWord', word[1]
        else:
            return 'Word', word[1]

    def parse_phrase(self):
        self.expect(Token.QUOTE)
        search_words = []
        while not self.peek()[0] == Token.QUOTE:
            search_word = self.parse_search_word()
            search_words.append(search_word)
        self.expect(Token.QUOTE)
        return 'Phrase', search_words

    def parse_group(self):
        self.expect(Token.LPAREN)
        query = self.parse_query()
        if not query:
            self.error("Expected a subquery inside a group.")
        else:
            self.expect(Token.RPAREN)
            return 'Group', query[1]

    def parse_positive_term(self):
        # Should return None if not a valid term
        token = self.peek()
        if token[0] == Token.LPAREN:
            return self.parse_group()
        else:
            value = self.parse_value()
            if not value:
                return
            next_token = self.peek()
            if next_token and next_token[0] == Token.SEMICOLON:
                self.next_token()
                next_token = self.peek()
                if next_token[0] == Token.END:
                    self.error("Unexpected end of stream. Expected a Value or ValueGroup")
                elif next_token[0] == Token.LPAREN:
                    return 'KVTerm', (value, self.parse_value_group())
                else:
                    return 'KVTerm', (value, self.parse_value())
            else:
                return value

    def parse_term(self):
        token = self.peek()
        if token[0] == Token.OP_NEG:
            self.next_token()
            term = self.parse_positive_term()
            print("Negative term", term)
            if not term:
                self.error(f"Expected a TERM, but got {self.peek()}")
                return
            else:
                return 'Negation', term
        else:
            return self.parse_positive_term()

    def parse_and_expression(self):
        terms = []
        while term := self.parse_term():
            terms.append(term)

        return ('AndExpression', terms) if terms else None

    def parse_query(self):
        expressions = []
        and_expression = self.parse_and_expression()
        if not and_expression:
            return

        expressions.append(and_expression)

        while (next_token := self.peek())[0]:
            if next_token[0] == Token.OP_OR:
                self.expect(Token.OP_OR)
                and_expression = self.parse_and_expression()
                expressions.append(and_expression)
            else:
                break
        return 'Query', expressions

    def parse(self):
        self.it = iter(self.tokens)
        query = self.parse_query()
        self.expect(Token.END)
        return query


class TSQueryVisitor:

    @staticmethod
    def visit_group(node, acc):
        acc.append('(')
        for expr in node[1]:
            TSQueryVisitor.visit_and_expression(expr, acc)
            acc.append(' | ')
        acc.pop()
        acc.append(')')

    @staticmethod
    def visit_kv_term(node, acc):
        key_node, value_node = node[1]
        # Re-use visit_term
        TSQueryVisitor.visit_term(key_node, acc)
        acc.append(' <-> ')

        if value_node[0] == 'ValueGroup':
            acc.append('(')
            for v in value_node[1]:
                TSQueryVisitor.visit_search_word(v, acc)
                acc.append(' | ')
            acc.pop()
            acc.append(')')
        else:
            TSQueryVisitor.visit_term(value_node, acc)

    @staticmethod
    def visit_search_word(node, acc):
        if node[0] == 'Word':
            acc.append(node[1])
        elif node[0] == 'PrefixWord':
            acc.append(f"{node[1]}:*")
        else:
            print(f"Invalid SearchWord type {node[0]}")

    @staticmethod
    def visit_phrase(node, acc):
        for search_word in node[1]:
            TSQueryVisitor.visit_search_word(search_word, acc)
            acc.append(' <-> ')

        if len(node[1]):
            acc.pop()  # Remove trailing space

    @staticmethod
    def visit_term(node, acc):
        node_type = node[0]
        if node_type == 'Phrase':
            TSQueryVisitor.visit_phrase(node, acc)
        elif node_type in ['Word', 'PrefixWord']:
            TSQueryVisitor.visit_search_word(node, acc)
        elif node_type == 'KVTerm':
            TSQueryVisitor.visit_kv_term(node, acc)
        elif node_type == 'Group':
            TSQueryVisitor.visit_group(node, acc)
        elif node_type == 'Negation':
            acc.append('!')
            TSQueryVisitor.visit_term(node[1], acc)
        else:
            print(f'Unexpected term node type: {node_type}')

    @staticmethod
    def visit_and_expression(node, acc):
        for term in node[1]:
            TSQueryVisitor.visit_term(term, acc)
            acc.append(' & ')
        if len(node[1]):
            acc.pop()

    @staticmethod
    def visit_query(node, acc):
        for expression in node[1]:
            TSQueryVisitor.visit_and_expression(expression, acc)
            acc.append(' | ')

        if len(node[1]):
            acc.pop()

    @staticmethod
    def visit(parse_tree):
        acc = []
        node_type = parse_tree[0]
        if node_type == 'Query':
            TSQueryVisitor.visit_query(parse_tree, acc)
        return ''.join(acc)
