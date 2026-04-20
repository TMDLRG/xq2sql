from __future__ import annotations

from .lowering import Lowerer
from .parser import parse
from .schema import SchemaRegistry
from .sql import SQLEmitter


class Translator:
    def __init__(self, schema: SchemaRegistry):
        self.schema = schema
        self.lowerer = Lowerer(schema)
        self.emitter = SQLEmitter()

    def translate(self, xquery: str) -> str:
        query = parse(xquery)
        ir = self.lowerer.lower(query)
        return self.emitter.emit(ir)
