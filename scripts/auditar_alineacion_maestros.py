"""Audita dimensiones de facturación frente a las asignaciones activas."""
from collections import Counter
from pathlib import Path
import re
import sys
import unicodedata

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app  # noqa: E402
from app.models import AsignacionComercial, Facturacion2026  # noqa: E402


def clave(valor):
    texto = ''.join(c for c in unicodedata.normalize('NFD', str(valor or ''))
                    if unicodedata.category(c) != 'Mn').lower()
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


app = create_app()
with app.app_context():
    maestros = AsignacionComercial.query.filter_by(activa=True).all()
    exactos = {}
    for asignacion in maestros:
        exactos.setdefault((clave(asignacion.cliente), clave(asignacion.campania),
                            clave(asignacion.subcampania)), []).append(asignacion)
    por_subcampania = {}
    for asignacion in maestros:
        por_subcampania.setdefault(clave(asignacion.subcampania), []).append(asignacion)

    registros = Facturacion2026.query.all()
    sin_coincidencia = Counter()
    dimensiones_distintas = Counter()
    exactos_ok = 0
    for registro in registros:
        llave = (clave(registro.cliente), clave(registro.campania), clave(registro.subcampania))
        candidatos_exactos = exactos.get(llave, [])
        maestro = next((a for a in candidatos_exactos
                        if clave(a.jefe_site) == clave(registro.jefe_site)
                        and clave(a.gerente) == clave(registro.gerente)), None)
        if not maestro and len(candidatos_exactos) == 1:
            maestro = candidatos_exactos[0]
        if not maestro:
            candidatos = por_subcampania.get(clave(registro.subcampania), [])
            if len(candidatos) == 1:
                maestro = candidatos[0]
            else:
                sin_coincidencia[(registro.cliente, registro.campania, registro.subcampania)] += 1
                continue
        diferencias = []
        for campo in ('cliente', 'gerente', 'jefe_site', 'campania', 'subcampania', 'tipo_negocio'):
            if clave(getattr(registro, campo)) != clave(getattr(maestro, campo)):
                diferencias.append(campo)
        if diferencias:
            dimensiones_distintas[(registro.cliente, registro.campania, registro.subcampania,
                                    maestro.cliente, maestro.campania, ','.join(diferencias))] += 1
        else:
            exactos_ok += 1

    print(f'Registros: {len(registros)}; alineados: {exactos_ok}; con diferencias: {sum(dimensiones_distintas.values())}; sin maestro: {sum(sin_coincidencia.values())}')
    print('\nDIFERENCIAS')
    for item, cantidad in dimensiones_distintas.most_common():
        print(cantidad, item)
    print('\nSIN COINCIDENCIA')
    for item, cantidad in sin_coincidencia.most_common():
        print(cantidad, item)
