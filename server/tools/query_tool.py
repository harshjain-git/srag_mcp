from typing import Any

from server.db import get_connection


def execute_query(sql: str) -> list[dict[str, Any]]:
    """
    Execute a read-only SQL query and return the results.
    """

    # Normalize and strip comments/whitespace
    normalized_sql = sql.strip().lower()
    while normalized_sql.startswith("/*") or normalized_sql.startswith("--"):
        if normalized_sql.startswith("/*"):
            end_idx = normalized_sql.find("*/")
            if end_idx == -1:
                break
            normalized_sql = normalized_sql[end_idx + 2:].strip()
        elif normalized_sql.startswith("--"):
            end_idx = normalized_sql.find("\n")
            if end_idx == -1:
                break
            normalized_sql = normalized_sql[end_idx + 1:].strip()

    if not (normalized_sql.startswith("select") or normalized_sql.startswith("with")):
        raise ValueError("Only read-only SELECT or WITH (CTE) queries are allowed.")

    forbidden = ["insert into", "update ", "delete from", "drop ", "alter table", "truncate "]
    if any(kw in normalized_sql for kw in forbidden):
        raise ValueError("Modifications are not allowed in the read-only query tool.")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)

            rows = cursor.fetchall()

            column_names = [
                description.name
                for description in cursor.description
            ]

    return [
        dict(zip(column_names, row))
        for row in rows
    ]