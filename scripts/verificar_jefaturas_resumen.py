"""Verifica que Resumen consolide una sola fila por jefatura."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Usuario


app = create_app()
with app.app_context():
    usuario = Usuario.query.filter_by(activo=True).first()
    cliente = app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id
    datos = cliente.get("/api/resumen-horas?year=2026").get_json()
    nombres = [fila["nombre"].strip().casefold() for fila in datos["jefaturas"]]
    suma_objetivo = round(sum(fila["horas_objetivo"] for fila in datos["jefaturas"]), 2)
    suma_facturada = round(sum(fila["horas_facturadas"] for fila in datos["jefaturas"]), 2)
    total_objetivo = round(datos["total"]["horas_objetivo"], 2)
    total_facturada = round(datos["total"]["horas_facturadas"], 2)
    assert len(nombres) == len(set(nombres)), "Hay jefaturas duplicadas"
    assert suma_objetivo == total_objetivo, (suma_objetivo, total_objetivo)
    assert suma_facturada == total_facturada, (suma_facturada, total_facturada)
    print(
        f"OK: {len(nombres)} jefaturas únicas; "
        f"objetivo={total_objetivo}; facturadas={total_facturada}"
    )
