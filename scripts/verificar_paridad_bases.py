"""Compara el contenido del origen con un destino o una línea base JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from database_contract import (
    database_manifest,
    default_database_url,
    engine_for,
    manifest_differences,
    safe_url,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "base_actual_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica esquema, filas y contenido sin escribir en ninguna base."
    )
    parser.add_argument("--source-url", default=default_database_url())
    parser.add_argument("--target-url", help="DATABASE_URL de la base migrada")
    parser.add_argument("--manifest", type=Path, help="Compara el origen contra este manifiesto")
    parser.add_argument("--write-manifest", type=Path, help="Genera una línea base desde el origen")
    args = parser.parse_args()

    source_engine = engine_for(args.source_url)
    try:
        source = database_manifest(source_engine)
    finally:
        source_engine.dispose()
    print(f"Origen auditado: {safe_url(args.source_url)}")

    if args.write_manifest:
        args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_manifest.write_text(
            json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Manifiesto generado: {args.write_manifest}")

    expected = None
    actual = None
    label = None
    if args.target_url:
        target_engine = engine_for(args.target_url)
        try:
            actual = database_manifest(target_engine)
        finally:
            target_engine.dispose()
        label = safe_url(args.target_url)
    elif args.manifest:
        expected = json.loads(args.manifest.read_text(encoding="utf-8"))
        actual = source
        label = str(args.manifest)
    elif not args.write_manifest and DEFAULT_MANIFEST.exists():
        expected = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        actual = source
        label = str(DEFAULT_MANIFEST)

    if args.target_url:
        expected = source
    if expected is None or actual is None:
        print("Auditoría finalizada; no se indicó destino ni manifiesto para comparar.")
        return 0

    differences = manifest_differences(expected, actual)
    if differences:
        print(f"PARIDAD FALLIDA contra {label}")
        for difference in differences:
            print(f"- {difference}")
        return 1
    print(f"PARIDAD OK contra {label}: esquema y contenido coinciden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
