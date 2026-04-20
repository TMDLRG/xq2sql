from __future__ import annotations

from typing import List, Optional

from . import ast
from .errors import ParseError, UnsupportedConstructError
from .lexer import tokenize


class Parser:
    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.i = 0

    def current(self):
        return self.tokens[self.i]

    def peek(self, offset: int = 1):
        idx = min(self.i + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def advance(self):
        token = self.current()
        self.i += 1
        return token

    def match(self, *types: str):
        if self.current().type in types:
            return self.advance()
        return None

    def expect(self, *types: str):
        token = self.current()
        if token.type not in types:
            expected = ", ".join(types)
            raise ParseError(f"Expected {expected} at position {token.pos}, got {token.type} ({token.value!r})")
        return self.advance()

    def parse(self) -> ast.Query:
        query = self.parse_query()
        self.expect("EOF")
        return query

    def parse_query(self) -> ast.Query:
        for_bindings = self.parse_for_bindings()
        let_bindings = self.parse_let_bindings()
        where = None
        if self.match("WHERE"):
            where = self.parse_expr()
        order_by = []
        if self.match("ORDER"):
            self.expect("BY")
            order_by = self.parse_order_items()
        self.expect("RETURN")
        returns = self.parse_return_spec()
        return ast.Query(
            for_bindings=for_bindings,
            let_bindings=let_bindings,
            where=where,
            order_by=order_by,
            returns=returns,
        )

    def parse_for_bindings(self) -> List[ast.ForBinding]:
        bindings: List[ast.ForBinding] = []
        if not self.match("FOR"):
            raise ParseError("A supported query must begin with 'for'")
        while True:
            bindings.extend(self.parse_for_binding_group())
            if self.current().type != "FOR":
                break
            self.advance()
        return bindings

    def parse_for_binding_group(self) -> List[ast.ForBinding]:
        group: List[ast.ForBinding] = []
        while True:
            var = self.expect("VAR").value[1:]
            self.expect("IN")
            source = self.parse_expr()
            group.append(ast.ForBinding(var=var, source=source))
            if not self.match("COMMA"):
                break
        return group

    def parse_let_bindings(self) -> List[ast.LetBinding]:
        bindings: List[ast.LetBinding] = []
        while self.match("LET"):
            while True:
                var = self.expect("VAR").value[1:]
                self.expect("ASSIGN")
                value = self.parse_expr()
                bindings.append(ast.LetBinding(var=var, value=value))
                if not self.match("COMMA"):
                    break
        return bindings

    def parse_order_items(self) -> List[ast.OrderItem]:
        items: List[ast.OrderItem] = []
        while True:
            expr = self.parse_expr()
            direction = "ascending"
            if self.match("ASCENDING"):
                direction = "ascending"
            elif self.match("DESCENDING"):
                direction = "descending"
            items.append(ast.OrderItem(expr=expr, direction=direction))
            if not self.match("COMMA"):
                break
        return items

    def parse_return_spec(self) -> ast.ReturnSpec:
        if self.current().type == "LBRACE":
            return self.parse_return_map()
        if self.current().type == "LPAREN":
            self.advance()
            items = [self.parse_expr()]
            while self.match("COMMA"):
                items.append(self.parse_expr())
            self.expect("RPAREN")
            return ast.ReturnExprs(items=items)

        first = self.parse_expr()
        items = [first]
        while self.match("COMMA"):
            items.append(self.parse_expr())
        return ast.ReturnExprs(items=items)

    def parse_return_map(self) -> ast.ReturnMap:
        self.expect("LBRACE")
        items: List[tuple[str, ast.Expr]] = []
        if self.current().type != "RBRACE":
            while True:
                if self.current().type == "STRING":
                    key = self._unquote(self.advance().value)
                elif self.current().type == "IDENT":
                    key = self.advance().value
                else:
                    token = self.current()
                    raise ParseError(f"Expected string or identifier as return-map key at {token.pos}")
                self.expect("COLON")
                value = self.parse_expr()
                items.append((key, value))
                if not self.match("COMMA"):
                    break
        self.expect("RBRACE")
        return ast.ReturnMap(items=items)

    def parse_expr(self) -> ast.Expr:
        return self.parse_or()

    def parse_or(self) -> ast.Expr:
        expr = self.parse_and()
        while self.match("OR"):
            rhs = self.parse_and()
            expr = ast.BinaryOp("or", expr, rhs)
        return expr

    def parse_and(self) -> ast.Expr:
        expr = self.parse_compare()
        while self.match("AND"):
            rhs = self.parse_compare()
            expr = ast.BinaryOp("and", expr, rhs)
        return expr

    def parse_compare(self) -> ast.Expr:
        expr = self.parse_additive()
        while self.current().type in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            op_token = self.advance()
            op_map = {
                "EQ": "=",
                "NE": "!=",
                "LT": "<",
                "LE": "<=",
                "GT": ">",
                "GE": ">=",
            }
            rhs = self.parse_additive()
            expr = ast.BinaryOp(op_map[op_token.type], expr, rhs)
        return expr

    def parse_additive(self) -> ast.Expr:
        expr = self.parse_multiplicative()
        while self.current().type in {"PLUS", "MINUS"}:
            op = self.advance().value
            rhs = self.parse_multiplicative()
            expr = ast.BinaryOp(op, expr, rhs)
        return expr

    def parse_multiplicative(self) -> ast.Expr:
        expr = self.parse_unary()
        while self.current().type == "STAR":
            op = self.advance().value
            rhs = self.parse_unary()
            expr = ast.BinaryOp(op, expr, rhs)
        return expr

    def parse_unary(self) -> ast.Expr:
        if self.match("MINUS"):
            return ast.UnaryOp("-", self.parse_unary())
        return self.parse_path_expr()

    def parse_path_expr(self) -> ast.Expr:
        expr = self.parse_atom()
        while self.match("SLASH"):
            step = self.parse_step()
            if isinstance(expr, ast.PathExpr):
                expr = ast.PathExpr(expr.base, expr.steps + [step])
            elif isinstance(expr, (ast.VarRef, ast.DocSource, ast.AbsoluteRoot)):
                expr = ast.PathExpr(expr, [step])
            else:
                raise UnsupportedConstructError(f"Cannot apply path navigation to {type(expr).__name__}")
        return expr

    def parse_atom(self) -> ast.Expr:
        token = self.current()

        if self.match("VAR"):
            return ast.VarRef(token.value[1:])

        if self.match("STRING"):
            return ast.Literal(self._unquote(token.value))

        if self.match("FLOAT"):
            return ast.Literal(float(token.value))

        if self.match("INT"):
            return ast.Literal(int(token.value))

        if self.match("TRUE"):
            return ast.Literal(True)

        if self.match("FALSE"):
            return ast.Literal(False)

        if self.match("LPAREN"):
            inner = self.parse_expr()
            self.expect("RPAREN")
            return inner

        if self.match("SLASH"):
            root = ast.AbsoluteRoot()
            step = self.parse_step()
            return ast.PathExpr(root, [step])

        if token.type == "IDENT":
            name = self.advance().value
            if self.match("LPAREN"):
                args: List[ast.Expr] = []
                if self.current().type != "RPAREN":
                    args.append(self.parse_expr())
                    while self.match("COMMA"):
                        args.append(self.parse_expr())
                self.expect("RPAREN")
                if name == "doc":
                    if len(args) != 1 or not isinstance(args[0], ast.Literal) or not isinstance(args[0].value, str):
                        raise ParseError("doc(...) expects a single string literal argument")
                    return ast.DocSource(args[0].value)
                return ast.FunctionCall(name=name, args=args)
            raise UnsupportedConstructError(
                f"Bare identifier '{name}' is not supported here; use a variable path, literal, or function call."
            )

        raise ParseError(f"Unexpected token {token.type} ({token.value!r}) at position {token.pos}")

    def parse_step(self) -> str:
        step_tokens = {
            "IDENT",
            "FOR",
            "IN",
            "LET",
            "WHERE",
            "ORDER",
            "BY",
            "RETURN",
            "ASCENDING",
            "DESCENDING",
            "AND",
            "OR",
            "TRUE",
            "FALSE",
        }
        if self.match("AT"):
            ident_token = self.current()
            if ident_token.type not in step_tokens:
                raise ParseError(f"Expected attribute name at position {ident_token.pos}, got {ident_token.type}")
            ident = self.advance().value
            return "@" + ident
        if self.current().type in step_tokens:
            return self.advance().value
        if self.match("STAR"):
            return "*"
        token = self.current()
        raise ParseError(f"Expected path step at position {token.pos}, got {token.type}")

    @staticmethod
    def _unquote(value: str) -> str:
        quote = value[0]
        inner = value[1:-1]
        inner = inner.replace(f"\\{quote}", quote).replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
        return inner

def parse(text: str) -> ast.Query:
    return Parser(text).parse()
