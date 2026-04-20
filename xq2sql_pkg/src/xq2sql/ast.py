from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Node:
    pass


@dataclass(frozen=True)
class Query(Node):
    for_bindings: List["ForBinding"]
    let_bindings: List["LetBinding"]
    where: Optional["Expr"]
    order_by: List["OrderItem"]
    returns: "ReturnSpec"


@dataclass(frozen=True)
class ForBinding(Node):
    var: str
    source: "Expr"


@dataclass(frozen=True)
class LetBinding(Node):
    var: str
    value: "Expr"


@dataclass(frozen=True)
class OrderItem(Node):
    expr: "Expr"
    direction: str = "ascending"


class Expr(Node):
    pass


@dataclass(frozen=True)
class VarRef(Expr):
    name: str


@dataclass(frozen=True)
class Literal(Expr):
    value: object


@dataclass(frozen=True)
class UnaryOp(Expr):
    op: str
    operand: Expr


@dataclass(frozen=True)
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class FunctionCall(Expr):
    name: str
    args: List[Expr]


@dataclass(frozen=True)
class DocSource(Expr):
    filename: str


@dataclass(frozen=True)
class PathExpr(Expr):
    base: Expr
    steps: List[str]


@dataclass(frozen=True)
class AbsoluteRoot(Expr):
    pass


class ReturnSpec(Node):
    pass


@dataclass(frozen=True)
class ReturnMap(ReturnSpec):
    items: List[tuple[str, Expr]]


@dataclass(frozen=True)
class ReturnExprs(ReturnSpec):
    items: List[Expr]
