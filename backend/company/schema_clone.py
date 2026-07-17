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
    """Advance serial/identity sequences to MAX(column) after data is copied."""
    qi_dest = _quote_ident(dest_schema)
    qi_table = _quote_ident(table)

    # Classic serial / nextval defaults
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
    columns = {row[0] for row in cursor.fetchall()}

    # GENERATED … AS IDENTITY (Django 5+ AutoField) — no nextval() default
    cursor.execute(
        """
        SELECT a.attname
        FROM pg_attribute a
        JOIN pg_class cl ON cl.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        WHERE n.nspname = %s
          AND cl.relname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND a.attidentity IN ('a', 'd')
        """,
        [dest_schema, table],
    )
    columns.update(row[0] for row in cursor.fetchall())

    for column in sorted(columns):
        qi_col = _quote_ident(column)
        # format('%I.%I') quotes schema/table so names with spaces work
        # (e.g. "Item Images").
        cursor.execute(
            "SELECT pg_get_serial_sequence(format('%%I.%%I', %s, %s), %s)",
            [dest_schema, table, column],
        )
        result = cursor.fetchone()
        if not result or not result[0]:
            continue
        sequence_name = result[0]
        cursor.execute("SELECT to_regclass(%s)", [sequence_name])
        reg = cursor.fetchone()
        if not reg or not reg[0]:
            logger.warning(
                "schema_clone: sequence %s for %s.%s.%s not found; skipping",
                sequence_name,
                dest_schema,
                table,
                column,
            )
            continue

        cursor.execute(f"SELECT MAX({qi_col}) FROM {qi_dest}.{qi_table}")
        max_row = cursor.fetchone()
        max_val = max_row[0] if max_row else None
        if max_val is None:
            # Empty table: next nextval() should return 1
            cursor.execute(
                "SELECT setval(%s::regclass, 1, false)",
                [sequence_name],
            )
        else:
            cursor.execute(
                "SELECT setval(%s::regclass, %s, true)",
                [sequence_name, int(max_val)],
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


def sync_all_sequences(schema_name: str) -> None:
    """
    Re-align every serial/identity sequence in ``schema_name`` to MAX(column).

    Safe to call after template clone or when identity sequences were skipped
    (Django 5 uses GENERATED AS IDENTITY, which older sync logic missed).
    """
    with connection.cursor() as cursor:
        if not _schema_exists(cursor, schema_name):
            raise CloneSchemaError(f"Schema {schema_name!r} does not exist")
        tables = _list_ordinary_tables(cursor, schema_name)
        for table in tables:
            _sync_sequences_for_table(cursor, schema_name, table)
    logger.info("schema_clone: synced sequences for schema %s", schema_name)
