class XQ2SQLError(Exception):
    """Base exception for xq2sql."""


class ParseError(XQ2SQLError):
    """Raised when input XQuery does not match the supported grammar."""


class UnsupportedConstructError(XQ2SQLError):
    """Raised when an XQuery feature is outside the supported subset."""


class SchemaMappingError(XQ2SQLError):
    """Raised when a path or field has no schema mapping."""
