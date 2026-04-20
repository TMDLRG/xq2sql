from __future__ import annotations

from .ir import QueryIR


class SQLEmitter:
    def emit(self, ir: QueryIR) -> str:
        if not ir.sources:
            raise ValueError("Cannot emit SQL without sources")
        distinct = "DISTINCT " if ir.distinct else ""
        select_sql = ", ".join(f"{p.expr.sql} AS {p.alias}" for p in ir.projections) or "*"
        from_sql = ", ".join(f"{src.table} {src.alias}" for src in ir.sources)

        parts = [
            f"SELECT {distinct}{select_sql}",
            f"FROM {from_sql}",
        ]

        if ir.filters:
            parts.append("WHERE " + " AND ".join(f.sql for f in ir.filters))

        if ir.group_by:
            unique = []
            seen = set()
            for expr in ir.group_by:
                if expr.sql not in seen:
                    unique.append(expr.sql)
                    seen.add(expr.sql)
            parts.append("GROUP BY " + ", ".join(unique))

        if ir.order_by:
            parts.append("ORDER BY " + ", ".join(f"{item.expr.sql} {item.direction}" for item in ir.order_by))

        return "\n".join(parts) + ";"
