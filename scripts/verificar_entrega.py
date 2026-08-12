"""Controles reproducibles previos a entregar o desplegar el proyecto."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys


RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def verificar() -> None:
    database_path = RAIZ / "instance" / "verificacion_entrega.db"
    database_path.unlink(missing_ok=True)
    try:
        os.environ["APP_ENV"] = "development"
        os.environ["SECRET_KEY"] = "clave-exclusiva-para-verificacion-local"
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
        os.environ["APP_DEFAULT_YEAR"] = "2026"

        from app import create_app, db
        from app.models import ProyeccionMatriz, Usuario

        app = create_app()
        app.config.update(TESTING=True)
        with app.app_context():
            assert len(db.metadata.tables) == 16, "La cantidad de tablas cambio sin actualizar el contrato."
            assert "facturacion_anio" in db.metadata.tables
            assert "facturacion_2026" not in db.metadata.tables
            usuario = Usuario(
                nombre="Verificacion",
                email="verificacion@example.invalid",
                rol="administrador",
                activo=True,
            )
            usuario.set_password("solo-pruebas")
            db.session.add(usuario)
            db.session.commit()
            usuario_id = usuario.id

        client = app.test_client()
        with client.session_transaction() as session:
            session["usuario_id"] = usuario_id
            session["csrf_token"] = "csrf-verificacion"

        routes = (
            "/", "/control", "/matriz", "/matriz-precios",
            "/matriz-proyecciones", "/resumen", "/variable",
            "/suma-fija", "/calendario-operativo", "/api/matriz?year=2026",
        )
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200, f"{route} devolvio HTTP {response.status_code}."
        assert client.get("/api/matriz?year=invalido").status_code == 400

        response = client.post(
            "/api/proyecciones-plp/edicion-masiva",
            json={
                "year": 2026,
                "csrf_token": "csrf-verificacion",
                "filas": [{
                    "tipo_plp": "Personal",
                    "mes": "2026-08",
                    "campania": "PRUEBA EDICION RAPIDA",
                    "horas": 1234.56,
                    "carga_semanal": "L a V",
                    "carga_horaria": 6,
                    "porcentaje_cumplimiento": 100,
                }],
            },
            headers={"X-CSRF-Token": "csrf-verificacion"},
        )
        assert response.status_code == 200, response.get_json()
        with app.app_context():
            registro = ProyeccionMatriz.query.filter_by(campania="PRUEBA EDICION RAPIDA").one()
            assert registro.horas_requeridas == 1234.56
            registro_id = registro.id
        response = client.post(
            "/api/proyecciones-plp/edicion-masiva",
            json={
                "year": 2026,
                "csrf_token": "csrf-verificacion",
                "filas": [{"id": registro_id, "eliminar": True}],
            },
            headers={"X-CSRF-Token": "csrf-verificacion"},
        )
        assert response.status_code == 200, response.get_json()
        with app.app_context():
            assert db.session.get(ProyeccionMatriz, registro_id) is None

        ddl_path = RAIZ / "docs" / "esquema_base_datos_sqlite.sql"
        with sqlite3.connect(":memory:") as connection:
            connection.executescript(ddl_path.read_text(encoding="utf-8"))
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            assert len(tables) == 16, "El DDL SQLite no crea las 16 tablas documentadas."

        local_database = RAIZ / "instance" / "facturacion.db"
        if local_database.exists():
            with sqlite3.connect(local_database) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert not connection.execute("PRAGMA foreign_key_check").fetchall()

        os.environ["APP_ENV"] = "production"
        os.environ["SECRET_KEY"] = "generar-un-secreto-de-ejemplo"
        try:
            create_app()
        except RuntimeError:
            pass
        else:
            raise AssertionError("Produccion acepto una SECRET_KEY de ejemplo.")
    finally:
        if "app" in locals():
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        database_path.unlink(missing_ok=True)


if __name__ == "__main__":
    verificar()
    print("OK: esquema, seguridad, rutas Flask y DDL SQLite verificados.")
