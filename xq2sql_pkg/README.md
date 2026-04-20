# xq2sql

`xq2sql` is a **working Python package** that translates a **practical, explicitly supported subset of XQuery** into ANSI-style SQL.

It is designed to be:

- deterministic
- dependency-free
- testable
- reusable across relational schemas through a schema registry

## Important scope note

This package **fully works for the supported subset described below**.

It is **not** a full implementation of the complete W3C XQuery language. A full XQuery implementation would require a much larger compiler/runtime and XML data model. This package instead targets the part of the problem that is usually useful for XML-to-relational translation pipelines.

## Supported subset

### Query shape

```xquery
for $var in /root/path
for $var2 in /other/path
let $x := <expression>
where <boolean expression>
order by <expression> ascending|descending, ...
return {"alias": <expression>, "alias2": <expression>}
```

Also supported:

- `doc("file.xml")/root/path`
- variable path access, e.g. `$b/title`, `$o/@id`
- literals: strings, integers, floats, booleans
- boolean operators: `and`, `or`
- comparison operators: `=`, `!=`, `<`, `<=`, `>`, `>=`
- arithmetic operators: `+`, `-`, `*`, `/`
- SQL-ish function lowering for common functions such as `count(...)`, `sum(...)`, `avg(...)`, `min(...)`, `max(...)`, `lower-case(...)`, `upper-case(...)`
- return as:
  - mapping/object style: `{"title": $b/title, "price": $b/price}`
  - single expression
  - comma-separated expression list
  - parenthesized expression list

### Explicitly unsupported

- arbitrary XQuery function declarations
- recursive queries
- XPath axes beyond simple child/attribute paths
- sequence-heavy semantics
- XML constructors
- update facility
- namespaces
- full XDM semantics

When an unsupported construct is encountered, the package raises a clear exception instead of hallucinating SQL.

## Installation

```bash
pip install .
```

## Quick start

```python
from xq2sql import SchemaRegistry, Translator

schema = SchemaRegistry()
schema.register_root(
    "/books/book",
    table="books",
    fields={
        "@id": "id",
        "title": "title",
        "author": "author_name",
        "price": "price",
    },
)

translator = Translator(schema)

query = '''
for $b in doc("books.xml")/books/book
where $b/price > 30
order by $b/title ascending
return {"title": $b/title, "price": $b/price}
'''

sql = translator.translate(query)
print(sql)
```

Output:

```sql
SELECT b.title AS title, b.price AS price
FROM books b
WHERE (b.price > 30)
ORDER BY b.title ASC;
```

## Schema registry model

The translator depends on a schema registry that maps XML roots and fields to relational tables and columns.

```python
schema.register_root(
    "/orders/order",
    table="orders",
    fields={
        "@id": "order_id",
        "customerId": "customer_id",
        "total": "total_amount",
    },
)
```

For a bound variable like `$o` created from `/orders/order`, the path `$o/customerId` maps to `o.customer_id`.

Nested relative paths are also allowed if you register them literally:

```python
schema.register_root(
    "/people/person",
    table="people",
    fields={
        "name/first": "first_name",
        "name/last": "last_name",
    },
)
```

## CLI

You can translate a query from the command line:

```bash
xq2sql schema.json query.xq
```

Example `schema.json`:

```json
{
  "roots": [
    {
      "path": "/books/book",
      "table": "books",
      "fields": {
        "@id": "id",
        "title": "title",
        "author": "author_name",
        "price": "price"
      }
    }
  ]
}
```

## Design

Pipeline:

1. tokenize
2. parse into AST
3. lower AST against schema registry
4. emit SQL

Because the package is deterministic, every failure can be classified as one of:

- parse failure
- unsupported construct
- root mapping missing
- field mapping missing

## Tests

```bash
python -m pytest
```
