"""Clone a PostgreSQL schema (tables + data + sequences) for fast tenant provisioning."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Iterable

from django.db import DatabaseError, connection, transaction

logger = logging.getLogger(__name__)


def try_set_session_replication_role_replica(cursor) -> bool:
    """
    When allowed (superuser / replication-capable role), set replica mode so
    triggers/FKs are relaxed during bulk INSERT…SELECT. Many hosted Postgres
    roles cannot set ``session_replication_role``; in that case we skip and rely
    on topological table order (and alphabetical fallback if the FK graph has cycles).

    The SET is run inside a **savepoint**: on permission failure Postgres aborts only
    that subtransaction; without ROLLBACK TO SAVEPOINT the whole outer transaction
    would stay aborted and every later command would error with "current transaction
    is aborted, commands ignored until end of transaction block".
    """
    sid = transaction.savepoint()
    try:
        cursor.execute("SET LOCAL session_replication_role = 'replica';")
    except DatabaseError as e:
        transaction.savepoint_rollback(sid)
        msg = str(e).lower()
        if "permission denied" in msg or "session_replication_role" in msg:
            logger.warning(
                "schema_clone: cannot set session_replication_role=replica (%s); "
                "continuing without trigger bypass (normal for non-superuser DB users).",
                e,
            )
            return False
        raise
    else:
        transaction.savepoint_commit(sid)
        return True


class CloneSchemaError(Exception):
    """Raised when schema cloning cannot proceed safely."""


def _quote_ident(ident: str) -> str:
    """Quote a PostgreSQL identifier (schema or table name)."""
    return connection.ops.quote_name(ident)


def _schema_exists(cursor, schema: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM information_schema.schemata WHERE schema_name = %s
        )
        """,
        [schema],
    )
    row = cursor.fetchone()
    return bool(row and row[0])


def _list_ordinary_tables(cursor, schema: str) -> list[str]:
    cursor.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = 'r' AND NOT c.relispartition
        ORDER BY c.relname
        """,
        [schema],
    )
    return [row[0] for row in cursor.fetchall()]


def _fk_edges_same_schema(cursor, schema: str) -> list[tuple[str, str]]:
    """Return (child_table, parent_table) for foreign keys wholly inside ``schema``."""
    cursor.execute(
        """
        SELECT clf.relname AS child_table, clf2.relname AS parent_table
        FROM pg_constraint con
        JOIN pg_class clf ON clf.oid = con.conrelid
        JOIN pg_namespace nsf ON nsf.oid = clf.relnamespace
        JOIN pg_class clf2 ON clf2.oid = con.confrelid
        JOIN pg_namespace nsf2 ON nsf2.oid = clf2.relnamespace
        WHERE con.contype = 'f'
          AND nsf.nspname = %s
          AND nsf2.nspname = %s
        """,
        [schema, schema],
    )
    return [(row[0], row[1]) for row in cursor.fetchall()]


def _topological_table_order(
    tables: Iterable[str], edges: list[tuple[str, str]]
) -> list[str]:
    """Order tables so referenced (parent) rows exist before dependent (child) inserts."""
    table_set = set(tables)
    in_degree: dict[str, int] = {t: 0 for t in table_set}
    children_of: dict[str, list[str]] = defaultdict(list)

    for child, parent in edges:
        if child not in table_set or parent not in table_set or child == parent:
            continue
        children_of[parent].append(child)
        in_degree[child] += 1

    queue = deque(sorted(t for t in table_set if in_degree[t] == 0))
    ordered: list[str] = []

    while queue:
        t = queue.popleft()
        ordered.append(t)
        for child in sorted(children_of.get(t, ())):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(ordered) != len(table_set):
        logger.warning(
            "schema_clone: cycle or unresolved FK order in source schema; "
            "falling back to alphabetical order with session_replication_role=replica"
        )
        return sorted(table_set)

    return ordered


def _sync_sequences_for_table(cursor, dest_schema: str, table: str) -> None:
    qi_dest = _quote_ident(dest_schema)
    qi_table = _quote_ident(table)
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_default LIKE 'nextval%%'
        """,
        [dest_schema, table],
    )
    sequence_columns = [row[0] for row in cursor.fetchall()]
    for column in sequence_columns:
        qi_col = _quote_ident(column)
        cursor.execute(
            "SELECT pg_get_serial_sequence(%s, %s)",
            [f"{dest_schema}.{table}", column],
        )
        result = cursor.fetchone()
        if not result or not result[0]:
            continue
        sequence_name = result[0]
        cursor.execute(
            f"""
            SELECT setval(
                %s,
                COALESCE((SELECT MAX({qi_col}) FROM {qi_dest}.{qi_table}), 1),
                true
            )
            """,
            [sequence_name],
        )


def clone_schema(source: str, dest: str) -> None:
    """
    Clone ``source`` schema to ``dest``: CREATE SCHEMA, CREATE TABLE LIKE, copy rows,
    sync sequences. Runs in a single transaction.

    Raises:
        CloneSchemaError: if ``source`` is missing or ``dest`` already exists.
    """
    if source == dest:
        raise CloneSchemaError("source and dest must differ")

    with transaction.atomic():
        with connection.cursor() as cursor:
            if not _schema_exists(cursor, source):
                raise CloneSchemaError(
                    f"Source schema {source!r} does not exist; run rebuild_template_schema."
                )
            if _schema_exists(cursor, dest):
                raise CloneSchemaError(
                    f"Destination schema {dest!r} already exists; refusing to overwrite."
                )

            try_set_session_replication_role_replica(cursor)

            qi_dest = _quote_ident(dest)
            cursor.execute(f"CREATE SCHEMA {qi_dest}")

            tables = _list_ordinary_tables(cursor, source)
            edges = _fk_edges_same_schema(cursor, source)
            ordered = _topological_table_order(tables, edges)

            qi_src = _quote_ident(source)
            for table in ordered:
                qi_tbl = _quote_ident(table)
                cursor.execute(
                    f"CREATE TABLE {qi_dest}.{qi_tbl} "
                    f"(LIKE {qi_src}.{qi_tbl} INCLUDING ALL)"
                )
                cursor.execute(
                    f"INSERT INTO {qi_dest}.{qi_tbl} SELECT * FROM {qi_src}.{qi_tbl};"
                )

            for table in ordered:
                _sync_sequences_for_table(cursor, dest, table)

    logger.info("schema_clone: cloned schema %s -> %s", source, dest)
