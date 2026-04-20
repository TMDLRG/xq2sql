from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .errors import SchemaMappingError
from . import ast


def _normalize_root_path(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    return path.rstrip("/") if path != "/" else path


def _normalize_field_path(path: str) -> str:
    path = path.strip().strip("/")
    while "//" in path:
        path = path.replace("//", "/")
    return path


@dataclass(frozen=True)
class RootMapping:
    path: str
    table: str
    fields: Dict[str, str]
    alias_hint: Optional[str] = None

    def resolve_field(self, rel_steps: list[str]) -> str:
        key = _normalize_field_path("/".join(rel_steps))
        if key in self.fields:
            return self.fields[key]
        raise SchemaMappingError(f"No field mapping for relative path {key!r} under root {self.path!r}")


class SchemaRegistry:
    def __init__(self):
        self._roots: Dict[str, RootMapping] = {}

    def register_root(self, path: str, table: str, fields: Dict[str, str], alias_hint: Optional[str] = None) -> None:
        normalized_fields = {_normalize_field_path(k): v for k, v in fields.items()}
        normalized_root = _normalize_root_path(path)
        self._roots[normalized_root] = RootMapping(
            path=normalized_root,
            table=table,
            fields=normalized_fields,
            alias_hint=alias_hint,
        )

    def register_from_dict(self, payload: dict) -> None:
        roots = payload.get("roots", [])
        for item in roots:
            self.register_root(
                path=item["path"],
                table=item["table"],
                fields=item["fields"],
                alias_hint=item.get("alias_hint"),
            )

    def resolve_root(self, source: ast.Expr) -> RootMapping:
        path = self._root_expr_to_path(source)
        normalized = _normalize_root_path(path)
        if normalized not in self._roots:
            available = ", ".join(sorted(self._roots.keys()))
            raise SchemaMappingError(f"No root mapping for {normalized!r}. Available roots: {available}")
        return self._roots[normalized]

    def _root_expr_to_path(self, expr: ast.Expr) -> str:
        if isinstance(expr, ast.PathExpr) and isinstance(expr.base, (ast.AbsoluteRoot, ast.DocSource)):
            return "/" + "/".join(expr.steps)
        if isinstance(expr, ast.PathExpr) and isinstance(expr.base, ast.VarRef):
            raise SchemaMappingError("Relative variable-based source bindings are not supported; use an absolute root path")
        raise SchemaMappingError(f"Unsupported source binding expression: {type(expr).__name__}")
