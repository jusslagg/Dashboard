"""Contrato reproducible para copiar y comparar bases del Dashboard.

No inicia Flask ni ejecuta migraciones automáticas. Esto permite auditar una
base de origen en modo lectura sin modificarla durante el traspaso.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys
import unicodedata

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.sql.sqltypes import Numeric


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGACY_EMPTY_TABLES = {"bajas_operativas"}


def model_metadata():
    from app import db
    import app.models  # noqa: F401 - registra todos los modelos

    return db.metadata


def default_database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured and configured != "sqlite:///facturacion.db":
        return configured
    return f"sqlite:///{(ROOT / 'instance' / 'facturacion.db').as_posix()}"


def safe_url(database_url: str) -> str:
    """Muestra motor y ubicación sin publicar credenciales."""
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        return f"sqlite:///{Path(url.database or '').name}"
    host = url.host or "servidor"
    database = url.database or "base"
    return f"{url.get_backend_name()}://{host}/{database}"


def engine_for(database_url: str | None = None) -> Engine:
    return create_engine(database_url or default_database_url(), future=True)


def _canonical_value(value, column):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, bool):
        return value
    if isinstance(column.type, Numeric) or isinstance(value, (Decimal, float)):
        scale = getattr(column.type, "scale", None)
        decimal_value = Decimal(str(value))
        if scale is not None:
            quantum = Decimal(1).scaleb(-scale)
            decimal_value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
        return format(decimal_value, "f")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.replace("\r\n", "\n"))
    return str(value)


def schema_contract(metadata=None) -> dict:
    metadata = metadata or model_metadata()
    tables = {}
    for table in metadata.sorted_tables:
        tables[table.name] = {
            "columns": [
                {
                    "name": column.name,
                    "type": str(column.type),
                    "nullable": bool(column.nullable),
                    "primary_key": bool(column.primary_key),
                }
                for column in table.columns
            ],
            "foreign_keys": sorted(
                f"{foreign_key.parent.name}->{foreign_key.target_fullname}"
                for foreign_key in table.foreign_keys
            ),
            "indexes": sorted([
                {
                    "name": index.name,
                    "columns": [column.name for column in index.columns],
                    "unique": bool(index.unique),
                }
                for index in table.indexes
            ], key=lambda item: item["name"] or ""),
        }
    return tables


def table_fingerprint(connection, table) -> dict:
    primary_key = list(table.primary_key.columns)
    order_columns = primary_key or list(table.columns)
    statement = select(table).order_by(*order_columns)
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(statement).mappings():
        canonical = [_canonical_value(row[column.name], column) for column in table.columns]
        digest.update(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
        count += 1
    return {"rows": count, "sha256": digest.hexdigest()}


def database_manifest(engine: Engine, metadata=None) -> dict:
    metadata = metadata or model_metadata()
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    expected = {table.name for table in metadata.sorted_tables}
    missing = sorted(expected - existing)
    extra_candidates = sorted(existing - expected)
    extra = []
    ignored_legacy = []
    physical_schema = {
        "missing_columns": {},
        "extra_columns": {},
        "missing_indexes": {},
        "missing_foreign_keys": {},
    }
    tables = {}
    with engine.connect() as connection:
        for table_name in extra_candidates:
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar_one()
            if table_name in LEGACY_EMPTY_TABLES and count == 0:
                ignored_legacy.append(table_name)
            else:
                extra.append(table_name)
        for table in metadata.sorted_tables:
            if table.name in existing:
                tables[table.name] = table_fingerprint(connection, table)
                actual_columns = {column["name"] for column in inspector.get_columns(table.name)}
                expected_columns = {column.name for column in table.columns}
                if missing_columns := sorted(expected_columns - actual_columns):
                    physical_schema["missing_columns"][table.name] = missing_columns
                if extra_columns := sorted(actual_columns - expected_columns):
                    physical_schema["extra_columns"][table.name] = extra_columns

                actual_indexes = {
                    index["name"] for index in inspector.get_indexes(table.name) if index.get("name")
                }
                expected_indexes = {index.name for index in table.indexes if index.name}
                if missing_indexes := sorted(expected_indexes - actual_indexes):
                    physical_schema["missing_indexes"][table.name] = missing_indexes

                expected_foreign_keys = {
                    f"{foreign_key.parent.name}->{foreign_key.target_fullname}"
                    for foreign_key in table.foreign_keys
                }
                actual_foreign_keys = {
                    f"{source}->{target_table}.{target}"
                    for foreign_key in inspector.get_foreign_keys(table.name)
                    for source, target in zip(
                        foreign_key.get("constrained_columns") or [],
                        foreign_key.get("referred_columns") or [],
                    )
                    for target_table in [foreign_key.get("referred_table")]
                }
                if missing_foreign_keys := sorted(expected_foreign_keys - actual_foreign_keys):
                    physical_schema["missing_foreign_keys"][table.name] = missing_foreign_keys
        integrity = {"foreign_keys": "not_applicable", "database": "not_applicable"}
        if engine.dialect.name == "sqlite":
            integrity["database"] = connection.execute(text("PRAGMA integrity_check")).scalar_one()
            integrity["foreign_keys"] = len(connection.execute(text("PRAGMA foreign_key_check")).all())
    schema = schema_contract(metadata)
    schema_hash = hashlib.sha256(
        json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "format": 1,
        "engine": engine.dialect.name,
        "schema_sha256": schema_hash,
        "missing_tables": missing,
        "extra_tables": extra,
        "ignored_empty_legacy_tables": ignored_legacy,
        "physical_schema": physical_schema,
        "integrity": integrity,
        "tables": tables,
    }


def manifest_differences(expected: dict, actual: dict) -> list[str]:
    differences = []
    if expected.get("schema_sha256") != actual.get("schema_sha256"):
        differences.append("El contrato de columnas, claves o índices no coincide.")
    if actual.get("missing_tables"):
        differences.append(f"Faltan tablas: {', '.join(actual['missing_tables'])}.")
    if actual.get("extra_tables"):
        differences.append(f"Sobran tablas: {', '.join(actual['extra_tables'])}.")
    physical_schema = actual.get("physical_schema", {})
    physical_labels = {
        "missing_columns": "Faltan columnas físicas",
        "extra_columns": "Sobran columnas físicas",
        "missing_indexes": "Faltan índices físicos",
        "missing_foreign_keys": "Faltan claves foráneas físicas",
    }
    for key, label in physical_labels.items():
        for table, values in sorted((physical_schema.get(key) or {}).items()):
            differences.append(f"{label} en {table}: {', '.join(values)}.")
    all_tables = sorted(set(expected.get("tables", {})) | set(actual.get("tables", {})))
    for table in all_tables:
        left = expected.get("tables", {}).get(table)
        right = actual.get("tables", {}).get(table)
        if left != right:
            differences.append(
                f"{table}: origen={left or 'ausente'}; destino={right or 'ausente'}."
            )
    integrity = actual.get("integrity", {})
    if integrity.get("database") not in ("ok", "not_applicable"):
        differences.append(f"Integridad física: {integrity.get('database')}.")
    if integrity.get("foreign_keys") not in (0, "not_applicable"):
        differences.append(f"Claves foráneas inválidas: {integrity.get('foreign_keys')}.")
    return differences
