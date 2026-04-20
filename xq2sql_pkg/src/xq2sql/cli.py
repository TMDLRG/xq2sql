from __future__ import annotations

import json
import pathlib
import sys

from .schema import SchemaRegistry
from .translator import Translator


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 1 and argv[0] in {"-h", "--help"}:
        print("Usage: xq2sql <schema.json> <query.xq>")
        return 0

    if len(argv) != 2:
        print("Usage: xq2sql <schema.json> <query.xq>", file=sys.stderr)
        return 2

    schema_path = pathlib.Path(argv[0])
    query_path = pathlib.Path(argv[1])

    with schema_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    with query_path.open("r", encoding="utf-8") as f:
        query_text = f.read()

    schema = SchemaRegistry()
    schema.register_from_dict(payload)
    translator = Translator(schema)
    print(translator.translate(query_text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
