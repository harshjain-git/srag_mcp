from typing import Any

from server.db import get_connection


def get_table_columns(
    cursor,
    table: str,
) -> set[str]:
    """Get valid column names for a table."""

    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table,),
    )

    return {row[0] for row in cursor.fetchall()}


def delete_records(
    operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Dynamically delete records from one or more existing tables.

    All operations are executed inside one transaction.
    If any operation fails, all changes are rolled back.
    """

    if not operations:
        raise ValueError("Operations cannot be empty.")

    results = []

    with get_connection() as conn:
        with conn.cursor() as cursor:

            for operation in operations:

                table = operation.get("table")
                where = operation.get("where") or operation.get("filter")

                if not table:
                    raise ValueError("Table name is required.")

                # Never allow DELETE without a WHERE condition.
                if not where:
                    raise ValueError(
                        f"WHERE conditions are required for "
                        f"table '{table}'."
                    )

                # Get actual columns dynamically.
                valid_columns = get_table_columns(cursor, table)

                if not valid_columns:
                    raise ValueError(
                        f"Table '{table}' does not exist."
                    )

                # Validate WHERE columns.
                invalid_columns = (
                    set(where.keys()) - valid_columns
                )

                if invalid_columns:
                    raise ValueError(
                        f"Invalid WHERE column(s) for table "
                        f"'{table}': "
                        f"{', '.join(sorted(invalid_columns))}"
                    )

                # Build WHERE clause dynamically.
                where_parts = [
                    f"{column} = %s"
                    for column in where
                ]

                where_sql = " AND ".join(where_parts)

                sql = f"""
                    DELETE FROM {table}
                    WHERE {where_sql}
                    RETURNING *
                """

                values = list(where.values())

                cursor.execute(sql, values)

                rows = cursor.fetchall()

                column_names = [
                    description.name
                    for description in cursor.description
                ]

                deleted_records = [
                    dict(zip(column_names, row))
                    for row in rows
                ]

                results.append({
                    "table": table,
                    "deleted_count": len(deleted_records),
                    "records": deleted_records,
                })

            # Commit only after ALL delete operations succeed.
            conn.commit()

    return results

