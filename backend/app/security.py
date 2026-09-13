import re

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|"
    r"copy|call|do|execute|prepare|deallocate|listen|notify|load|"
    r"reindex|cluster|vacuum|comment|security|lock|unlock|"
    r"set\s+role|set\s+session|reset\s+role|pg_read_file|pg_write|"
    r"lo_import|lo_export|dblink|copy\s+"
    r")\b",
    re.I,
)


class UnsafeSqlError(ValueError):
    pass


def sanitize_sql(raw: str) -> str:
    sql = _COMMENT_BLOCK.sub(" ", raw or "")
    sql = _COMMENT_LINE.sub(" ", sql)
    sql = sql.strip()
    if not sql:
        raise UnsafeSqlError("Query is empty.")

    # Allow a single trailing semicolon, reject anything after it.
    parts = [p.strip() for p in sql.split(";") if p.strip()]
    if len(parts) != 1:
        raise UnsafeSqlError("Submit exactly one SELECT (or WITH) statement.")
    sql = parts[0]

    if _FORBIDDEN.search(sql):
        raise UnsafeSqlError(
            "Only read-only SELECT / WITH queries can be explained."
        )

    head = re.sub(r"\s+", " ", sql[:40]).strip().lower()
    if not (head.startswith("select") or head.startswith("with")):
        raise UnsafeSqlError("Query must start with SELECT or WITH.")

    return sql
