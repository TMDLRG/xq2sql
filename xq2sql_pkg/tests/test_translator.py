from xq2sql import ParseError, SchemaMappingError, Translator, SchemaRegistry
from xq2sql.cli import main as cli_main


def make_schema():
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
    schema.register_root(
        "/orders/order",
        table="orders",
        fields={
            "@id": "order_id",
            "customerId": "customer_id",
            "total": "total_amount",
        },
    )
    schema.register_root(
        "/customers/customer",
        table="customers",
        fields={
            "@id": "id",
            "name": "name",
            "tier": "tier",
        },
    )
    return schema


def test_simple_projection():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $b in /books/book
        return {"title": $b/title, "price": $b/price}
        '''
    )
    assert sql == (
        "SELECT b.title AS title, b.price AS price\n"
        "FROM books b;"
    )


def test_where_and_order():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $b in doc("books.xml")/books/book
        where $b/price > 30
        order by $b/title ascending
        return {"title": $b/title, "price": $b/price}
        '''
    )
    assert sql == (
        "SELECT b.title AS title, b.price AS price\n"
        "FROM books b\n"
        "WHERE (b.price > 30)\n"
        "ORDER BY b.title ASC;"
    )


def test_join_with_two_for_bindings():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $o in /orders/order
        for $c in /customers/customer
        where $o/customerId = $c/@id
        return {"order_id": $o/@id, "customer_name": $c/name}
        '''
    )
    assert sql == (
        "SELECT o.order_id AS order_id, c.name AS customer_name\n"
        "FROM orders o, customers c\n"
        "WHERE (o.customer_id = c.id);"
    )


def test_let_binding():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $b in /books/book
        let $p := $b/price
        where $p >= 20
        return {"price": $p}
        '''
    )
    assert sql == (
        "SELECT b.price AS price\n"
        "FROM books b\n"
        "WHERE (b.price >= 20);"
    )


def test_count_aggregate():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $o in /orders/order
        return {"n": count($o)}
        '''
    )
    assert sql == (
        "SELECT COUNT(*) AS n\n"
        "FROM orders o;"
    )


def test_group_by_when_mixing_aggregate_and_scalar():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $o in /orders/order
        return {"customer": $o/customerId, "n": count($o)}
        '''
    )
    assert sql == (
        "SELECT o.customer_id AS customer, COUNT(*) AS n\n"
        "FROM orders o\n"
        "GROUP BY o.customer_id;"
    )


def test_expression_list_alias_inference():
    t = Translator(make_schema())
    sql = t.translate(
        '''
        for $b in /books/book
        return ($b/title, $b/price)
        '''
    )
    assert sql == (
        "SELECT b.title AS title, b.price AS price\n"
        "FROM books b;"
    )


def test_unknown_field_raises():
    t = Translator(make_schema())
    try:
        t.translate(
            '''
            for $b in /books/book
            return {"x": $b/unknown}
            '''
        )
        assert False, "Expected SchemaMappingError"
    except SchemaMappingError:
        pass


def test_invalid_query_raises_parse_error():
    t = Translator(make_schema())
    try:
        t.translate("where $x = 1 return 1")
        assert False, "Expected ParseError"
    except ParseError:
        pass


def test_cli_help_flag():
    assert cli_main(["--help"]) == 0
