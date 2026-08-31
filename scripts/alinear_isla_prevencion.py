"""Alinea la facturación histórica de Isla Prevención con Datos Maestros."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app, db  # noqa: E402
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio  # noqa: E402

base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-alinear-isla-prevencion-{marca}.db'
shutil.copy2(base, respaldo)

app = create_app()
with app.app_context():
    maestro = AsignacionComercial.query.filter_by(campania_id=85, activa=True).one()
    registros = Facturacion2026.query.filter(
        Facturacion2026.cliente == 'Santander Isla Prevencion de Fraudes'
    ).all()
    assert registros, 'No se encontraron registros históricos para alinear'
    antes = {
        'cantidad': len(registros),
        'cliente': registros[0].cliente, 'gerente': registros[0].gerente,
        'jefe_site': registros[0].jefe_site, 'campania': registros[0].campania,
        'subcampania': registros[0].subcampania,
    }
    for registro in registros:
        registro.cliente = maestro.cliente
        registro.gerente = maestro.gerente
        registro.jefe_site = maestro.jefe_site
        registro.campania = maestro.campania
        registro.subcampania = maestro.subcampania
        registro.tipo_negocio = maestro.tipo_negocio
    despues = {
        'cantidad': len(registros), 'cliente': maestro.cliente,
        'gerente': maestro.gerente, 'jefe_site': maestro.jefe_site,
        'campania': maestro.campania, 'subcampania': maestro.subcampania,
    }
    db.session.add(HistorialCambio(
        accion='edicion', entidad='facturacion', entidad_id='campania-maestra-85',
        resumen=f'Alineación Isla Prevención: {len(registros)} registros',
        detalle=f'Respaldo: {respaldo.name}', antes=str(antes), despues=str(despues),
    ))
    db.session.commit()
print(f'Alineación OK: {len(registros)} registros. Respaldo: {respaldo}')
