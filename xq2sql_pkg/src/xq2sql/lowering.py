from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from . import ast
from .errors import SchemaMappingError, UnsupportedConstructError
from .ir import OrderBy, Projection, QueryIR, SQLExpr, Source
from .schema import RootMapping, SchemaRegistry


_AGG_FUNCS = {"count", "sum", "avg", "min", "max"}
_FUNC_SQL_MAP = {
    "lower-case": "LOWER",
    "upper-case": "UPPER",
    "count": "COUNT",
    "sum": "SUM",
    "avg": "AVG",
    "min": "MIN",
    "max": "MAX",
}


@dataclass
class BoundVar:
    alias: str
    root: RootMapping


class Lowerer:
    def __init__(self, schema: SchemaRegistry):
        self.schema = schema

    def lower(self, query: ast.Query) -> QueryIR:
        ir = QueryIR()
        bound_vars: Dict[str, BoundVar] = {}
        let_bindings: Dict[str, ast.Expr] = {}

        for fb in query.for_bindings:
            root = self.schema.resolve_root(fb.source)
            alias = fb.var
            if alias in bound_vars:
                raise UnsupportedConstructError(f"Duplicate binding for variable ${alias}")
            bound_vars[alias] = BoundVar(alias=alias, root=root)
            ir.sources.append(Source(table=root.table, alias=alias))

        for lb in query.let_bindings:
            let_bindings[lb.var] = lb.value

        if query.where is not None:
            ir.filters.append(self.lower_expr(query.where, bound_vars, let_bindings))

        for item in query.order_by:
            expr = self.lower_expr(item.expr, bound_vars, let_bindings)
            ir.order_by.append(OrderBy(expr=expr, direction="ASC" if item.direction == "ascending" else "DESC"))

        if isinstance(query.returns, ast.ReturnMap):
            for alias, expr in query.returns.items:
                ir.projections.append(Projection(alias=alias, expr=self.lower_expr(expr, bound_vars, let_bindings)))
        elif isinstance(query.returns, ast.ReturnExprs):
            for idx, expr in enumerate(query.returns.items):
                alias = self.infer_alias(expr, idx)
                ir.projections.append(Projection(alias=alias, expr=self.lower_expr(expr, bound_vars, let_bindings)))
        else:
            raise UnsupportedConstructError(f"Unsupported return spec type: {type(query.returns).__name__}")

        self._derive_group_by(ir)
        return ir

    def lower_expr(self, expr: ast.Expr, bound_vars: Dict[str, BoundVar], let_bindings: Dict[str, ast.Expr]) -> SQLExpr:
        if isinstance(expr, ast.Literal):
            if isinstance(expr.value, str):
                safe = expr.value.replace("'", "''")
                return SQLExpr(f"'{safe}'")
            if isinstance(expr.value, bool):
                return SQLExpr("TRUE" if expr.value else "FALSE")
            return SQLExpr(str(expr.value))

        if isinstance(expr, ast.VarRef):
            if expr.name in let_bindings:
                return self.lower_expr(let_bindings[expr.name], bound_vars, let_bindings)
            if expr.name in bound_vars:
                return SQLExpr(f"{bound_vars[expr.name].alias}.*")
            raise SchemaMappingError(f"Unknown variable ${expr.name}")

        if isinstance(expr, ast.UnaryOp):
            operand = self.lower_expr(expr.operand, bound_vars, let_bindings)
            return SQLExpr(f"({expr.op}{operand.sql})", is_aggregate=operand.is_aggregate)

        if isinstance(expr, ast.BinaryOp):
            left = self.lower_expr(expr.left, bound_vars, let_bindings)
            right = self.lower_expr(expr.right, bound_vars, let_bindings)
            op = expr.op.upper() if expr.op in {"and", "or"} else expr.op
            return SQLExpr(f"({left.sql} {op} {right.sql})", is_aggregate=left.is_aggregate or right.is_aggregate)

        if isinstance(expr, ast.PathExpr):
            return self.lower_path(expr, bound_vars, let_bindings)

        if isinstance(expr, ast.FunctionCall):
            func = expr.name
            sql_name = _FUNC_SQL_MAP.get(func)
            if not sql_name:
                raise UnsupportedConstructError(f"Unsupported function '{func}'")
            lowered_args = [self.lower_expr(arg, bound_vars, let_bindings) for arg in expr.args]
            if func == "count" and len(lowered_args) == 1 and lowered_args[0].sql.endswith(".*"):
                return SQLExpr("COUNT(*)", is_aggregate=True)
            return SQLExpr(
                f"{sql_name}(" + ", ".join(arg.sql for arg in lowered_args) + ")",
                is_aggregate=(func in _AGG_FUNCS) or any(arg.is_aggregate for arg in lowered_args),
            )

        if isinstance(expr, ast.DocSource):
            raise UnsupportedConstructError("doc(...) may only appear as part of a source path")

        if isinstance(expr, ast.AbsoluteRoot):
            raise UnsupportedConstructError("A bare absolute root is not a valid scalar expression")

        raise UnsupportedConstructError(f"Unsupported expression node: {type(expr).__name__}")

    def lower_path(self, expr: ast.PathExpr, bound_vars: Dict[str, BoundVar], let_bindings: Dict[str, ast.Expr]) -> SQLExpr:
        base = expr.base
        if isinstance(base, ast.VarRef):
            if base.name in let_bindings:
                expanded = let_bindings[base.name]
                if not isinstance(expanded, ast.PathExpr):
                    raise UnsupportedConstructError(f"Let-bound variable ${base.name} is not path-like, cannot apply /path")
                merged = ast.PathExpr(expanded.base, expanded.steps + expr.steps)
                return self.lower_path(merged, bound_vars, let_bindings)
            if base.name not in bound_vars:
                raise SchemaMappingError(f"Unknown variable ${base.name}")
            binding = bound_vars[base.name]
            column = binding.root.resolve_field(expr.steps)
            return SQLExpr(f"{binding.alias}.{column}")

        raise UnsupportedConstructError("Only variable-relative paths can appear in scalar expressions")

    @staticmethod
    def infer_alias(expr: ast.Expr, idx: int) -> str:
        if isinstance(expr, ast.PathExpr) and expr.steps:
            step = expr.steps[-1]
            return step[1:] if step.startswith("@") else step.replace("-", "_")
        if isinstance(expr, ast.FunctionCall):
            return expr.name.replace("-", "_")
        return f"expr_{idx + 1}"

    @staticmethod
    def _derive_group_by(ir: QueryIR) -> None:
        has_aggregate = any(p.expr.is_aggregate for p in ir.projections)
        if not has_aggregate:
            return
        for proj in ir.projections:
            if not proj.expr.is_aggregate:
                ir.group_by.append(proj.expr)
