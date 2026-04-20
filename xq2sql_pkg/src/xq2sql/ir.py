from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class SQLExpr:
    sql: str
    is_aggregate: bool = False


@dataclass(frozen=True)
class Source:
    table: str
    alias: str


@dataclass(frozen=True)
class Projection:
    alias: str
    expr: SQLExpr


@dataclass(frozen=True)
class OrderBy:
    expr: SQLExpr
    direction: str = "ASC"


@dataclass
class QueryIR:
    sources: List[Source] = field(default_factory=list)
    filters: List[SQLExpr] = field(default_factory=list)
    projections: List[Projection] = field(default_factory=list)
    order_by: List[OrderBy] = field(default_factory=list)
    distinct: bool = False
    group_by: List[SQLExpr] = field(default_factory=list)
