"""Controles de portabilidad y limpieza para la entrega a Desarrollo."""

from __future__ import annotations

from pathlib import Path
import re
import sys

from sqlalchemy.dialects import postgresql, sqlite


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.database_contract import model_metadata
from scripts.generar_esquema_base_datos import contenido_ddl


def main() -> int:
    errors = []
    forbidden = {
        "ruta absoluta de usuario": re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
        "IP privada fija": re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b"),
    }
    files = [
        *ROOT.joinpath("app").rglob("*.py"),
        *ROOT.joinpath("app").rglob("*.html"),
        *ROOT.joinpath("scripts").glob("*.py"),
        ROOT / "run.py",
        ROOT / ".env.example",
    ]
    for path in files:
        content = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            if pattern.search(content):
                errors.append(f"{path.relative_to(ROOT)} contiene {label}.")

    routes = (ROOT / "app" / "routes.py").read_text(encoding="utf-8")
    if "jefatura_personal_por_tipo_negocio" in routes:
        errors.append("La jefatura de Personal todavía tiene una asignación fija en código.")

    expected = {
        "sqlite": contenido_ddl("sqlite", sqlite.dialect()),
        "postgresql": contenido_ddl("postgresql", postgresql.dialect()),
    }
    for engine, content in expected.items():
        path = ROOT / "docs" / f"esquema_base_datos_{engine}.sql"
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            errors.append(f"{path.relative_to(ROOT)} está desactualizado respecto de app/models.py.")

    metadata = model_metadata()
    if "segmento" not in metadata.tables["asignaciones_comerciales"].columns:
        errors.append("El contrato de asignaciones no contiene segmento.")
    required_docs = (
        ROOT / "docs" / "ENTREGA_DESARROLLO.md",
        ROOT / "docs" / "base_actual_manifest.json",
    )
    for path in required_docs:
        if not path.exists():
            errors.append(f"Falta {path.relative_to(ROOT)}.")

    if errors:
        print("HANDOFF FALLIDO")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"HANDOFF OK: {len(metadata.tables)} tablas, DDL sincronizados y sin rutas/IP locales fijas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
