"""Controles reproducibles previos a entregar o desplegar el proyecto."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sqlite3
import sys
from sqlalchemy import text


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

        from app import asegurar_administrador_inicial_db, create_app, db
        from app.models import AsignacionComercial, Campania, ProyeccionMatriz, Usuario

        app = create_app()
        app.config.update(TESTING=True)
        with app.app_context():
            assert len(db.metadata.tables) == 27, "La cantidad de tablas cambio sin actualizar el contrato."
            assert "facturacion_anio" in db.metadata.tables
            assert "facturacion_2026" not in db.metadata.tables
            assert "normalizacion_nombres_proyectados" in db.metadata.tables
            usuario = Usuario(
                nombre="Verificacion",
                email="verificacion@example.invalid",
                rol="administrador",
                activo=True,
            )
            usuario.set_password("solo-pruebas")
            db.session.add(usuario)
            usuario_full = Usuario(
                nombre="Verificacion Full",
                email="full@example.invalid",
                rol="Full",
                activo=True,
            )
            usuario_full.set_password("solo-pruebas")
            db.session.add(usuario_full)
            campania = Campania(cliente="Cliente prueba", nombre="Campaña prueba", activa=True)
            db.session.add(campania)
            db.session.commit()
            usuario_id = usuario.id
            usuario_full_id = usuario_full.id
            campania_id = campania.id

        client = app.test_client()
        with client.session_transaction() as session:
            session["usuario_id"] = usuario_id
            session["csrf_token"] = "csrf-verificacion"

        routes = (
            "/", "/control", "/matriz", "/matriz-precios",
            "/matriz-proyecciones", "/resumen", "/variable", "/resumen-horas",
            "/suma-fija", "/calendario-operativo", "/proyectado-vs-facturado",
            "/api/matriz?year=2026", "/api/proyectado-vs-facturado?year=2026",
            "/api/catalogos/normalizaciones-proyectados?year=2026",
        )
        for route in routes:
            response = client.get(route)
            assert response.status_code == 200, f"{route} devolvio HTTP {response.status_code}."
        assert client.get("/api/matriz?year=invalido").status_code == 400
        assert client.get("/api/resumen-horas?year=2026").status_code == 200

        # El catálogo canoniza al insertar: una variante de mayúsculas debe
        # encontrar la campaña existente antes de llegar a su clave única.
        with app.app_context():
            galicia = Campania(cliente="Galicia Seguros", nombre="GALICIA SEGUROS - LITIGIOS")
            db.session.add(galicia)
            db.session.flush()
            asignacion_galicia = AsignacionComercial(
                campania_catalogo=galicia, cliente="Galicia Seguros",
                gerente="Sin gerencia", jefe_site="Ditto, Mariela",
                campania=galicia.nombre, subcampania=galicia.nombre,
                tipo_negocio=None, es_next_gen=False, activa=True,
            )
            db.session.add(asignacion_galicia)
            db.session.commit()
            galicia_id = galicia.id
            asignacion_galicia_id = asignacion_galicia.id
            db.session.execute(text(
                "UPDATE asignaciones_comerciales SET jefe_site = 'Mariela Ditto' WHERE id = :id"
            ), {"id": asignacion_galicia_id})
            db.session.commit()

        payload_galicia = {
            "cliente": "GALICIA SEGUROS", "gerente": "Sin Gerente",
            "jefe_site": "Ditto, Mariela", "campania": "GALICIA SEGUROS - LITIGIOS",
            "subcampania": "GALICIA SEGUROS - LITIGIOS", "csrf_token": "csrf-verificacion",
        }
        response = client.post("/api/asignaciones", json=payload_galicia,
                               headers={"X-CSRF-Token": "csrf-verificacion"})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["asignacion"]["id"] == asignacion_galicia_id
        with app.app_context():
            assert Campania.query.filter_by(cliente="Galicia Seguros", nombre=payload_galicia["campania"]).count() == 1
            assert AsignacionComercial.query.filter_by(campania_id=galicia_id).count() == 1

        # Una subcampaña nueva sí puede compartir la campaña canónica.
        otra_subcampania = {**payload_galicia, "subcampania": "LITIGIOS BACKOFFICE"}
        response = client.post("/api/asignaciones", json=otra_subcampania,
                               headers={"X-CSRF-Token": "csrf-verificacion"})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["asignacion"]["campania_id"] == galicia_id
        with app.app_context():
            assert Campania.query.filter_by(cliente="Galicia Seguros", nombre=payload_galicia["campania"]).count() == 1
            assert AsignacionComercial.query.filter_by(campania_id=galicia_id).count() == 2

        assert b"Entrega a Desarrollo" not in client.get("/").data
        assert client.get("/entrega-desarrollo").status_code == 403
        assert b'href="/entrega-desarrollo"' not in client.get("/documentacion-tecnica").data

        full_client = app.test_client()
        with full_client.session_transaction() as session:
            session["usuario_id"] = usuario_full_id
        assert b"Entrega a Desarrollo" in full_client.get("/").data
        assert full_client.get("/entrega-desarrollo").status_code == 200
        assert full_client.get("/entrega-desarrollo/descargar").status_code == 200
        assert full_client.get("/entrega-desarrollo/manifiesto").status_code == 200
        assert full_client.get("/entrega-desarrollo/esquema/postgresql").status_code == 200
        assert full_client.get("/entrega-desarrollo/esquema/sqlite").status_code == 200
        assert full_client.get("/entrega-desarrollo/esquema/pdf").status_code == 200
        assert b'href="/entrega-desarrollo"' in full_client.get("/documentacion-tecnica").data

        for valor_esperado in (True, False, None):
            response = client.patch(
                f"/api/campanias/{campania_id}/valor-hora",
                json={"valor_hora_variable": valor_esperado, "csrf_token": "csrf-verificacion"},
                headers={"X-CSRF-Token": "csrf-verificacion"},
            )
            assert response.status_code == 200, response.get_json()
            assert response.get_json()["campania"]["valor_hora_variable"] is valor_esperado

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
            assert len(tables) == 27, "El DDL SQLite no crea las 27 tablas documentadas."

        local_database = RAIZ / "instance" / "facturacion.db"
        if local_database.exists():
            with sqlite3.connect(local_database) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert not connection.execute("PRAGMA foreign_key_check").fetchall()

        with app.app_context():
            administrador_full = db.session.get(Usuario, usuario_id)
            administrador_full.rol = "Full"
            administrador_full.permisos_personalizados = json.dumps({
                "visualizar": True,
                "cargar": True,
                "editar": True,
                "eliminar": True,
                "administrar_perfiles": True,
                "modulos": ["facturacion_total", "directorio", "proyecciones"],
            })
            db.session.commit()
            asegurar_administrador_inicial_db()
            assert administrador_full.rol == "Full", "El arranque degradó un Full con permisos administrativos."
        assert client.get("/api/auth/me").get_json()["usuario"]["rol"] == "Full"

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
