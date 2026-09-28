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


def update_records(
    operations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Dynamically update records in one or more existing tables.

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
                updates = operation.get("updates")
                where = operation.get("where")

                if not table:
                    raise ValueError("Table name is required.")

                if not updates:
                    raise ValueError(
                        f"Updates cannot be empty for table '{table}'."
                    )

                if not where:
                    raise ValueError(
                        f"WHERE conditions are required for table '{table}'."
                    )

                # Get actual columns dynamically.
                valid_columns = get_table_columns(cursor, table)

                if not valid_columns:
                    raise ValueError(
                        f"Table '{table}' does not exist."
                    )

                # Validate columns being updated.
                invalid_update_columns = (
                    set(updates.keys()) - valid_columns
                )

                if invalid_update_columns:
                    raise ValueError(
                        f"Invalid update column(s) for table "
                        f"'{table}': "
                        f"{', '.join(sorted(invalid_update_columns))}"
                    )

                # Validate WHERE columns.
                invalid_where_columns = (
                    set(where.keys()) - valid_columns
                )

                if invalid_where_columns:
                    raise ValueError(
                        f"Invalid WHERE column(s) for table "
                        f"'{table}': "
                        f"{', '.join(sorted(invalid_where_columns))}"
                    )

                # Build SET clause.
                set_parts = [
                    f"{column} = %s"
                    for column in updates
                ]

                set_sql = ", ".join(set_parts)

                # Build WHERE clause.
                where_parts = [
                    f"{column} = %s"
                    for column in where
                ]

                where_sql = " AND ".join(where_parts)

                sql = f"""
                    UPDATE {table}
                    SET {set_sql}
                    WHERE {where_sql}
                    RETURNING *
                """

                values = (
                    list(updates.values())
                    + list(where.values())
                )

                cursor.execute(sql, values)

                rows = cursor.fetchall()

                column_names = [
                    description.name
                    for description in cursor.description
                ]

                updated_records = [
                    dict(zip(column_names, row))
                    for row in rows
                ]

                results.append({
                    "table": table,
                    "updated_count": len(updated_records),
                    "records": updated_records,
                })

            conn.commit()

    return results

