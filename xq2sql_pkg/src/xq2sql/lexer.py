from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .errors import ParseError


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    pos: int


_KEYWORDS = {
    "for",
    "in",
    "let",
    "where",
    "order",
    "by",
    "return",
    "ascending",
    "descending",
    "and",
    "or",
    "true",
    "false",
}

_TOKEN_SPEC = [
    ("WHITESPACE", r"[ \t\r\n]+"),
    ("COMMENT", r"\(:.*?:\)"),
    ("ASSIGN", r":="),
    ("NE", r"!="),
    ("LE", r"<="),
    ("GE", r">="),
    ("EQ", r"="),
    ("LT", r"<"),
    ("GT", r">"),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("COMMA", r","),
    ("COLON", r":"),
    ("SLASH", r"/"),
    ("AT", r"@"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("VAR", r"\$[A-Za-z_][A-Za-z0-9_]*"),
    ("FLOAT", r"(?:\d+\.\d*|\d*\.\d+)"),
    ("INT", r"\d+"),
    ("STRING", r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\''),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_\-]*"),
]

_MASTER = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPEC), re.DOTALL)


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    n = len(text)
    while pos < n:
        match = _MASTER.match(text, pos)
        if not match:
            snippet = text[pos: pos + 30]
            raise ParseError(f"Unexpected character at position {pos}: {snippet!r}")
        kind = match.lastgroup
        value = match.group()
        if kind not in {"WHITESPACE", "COMMENT"}:
            if kind == "IDENT" and value.lower() in _KEYWORDS:
                kind = value.lower().upper()
            tokens.append(Token(kind, value, pos))
        pos = match.end()
    tokens.append(Token("EOF", "", pos))
    return tokens
