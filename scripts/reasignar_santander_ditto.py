"""Pasa Santander bajo Ditto, Mariela a Sin gerencia, sin alterar importes."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app, db  # noqa: E402
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio  # noqa: E402

NUMERICOS = ('horas_objetivo', 'horas_facturadas', 'valor_hora', 'facturado_horas_manual',
             'total_facturado_manual', 'variable_productivo', 'bonos', 'penalizaciones',
             'netx_gen', 'otros')
base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-santander-ditto-sin-gerencia-{marca}.db'
shutil.copy2(base, respaldo)

app = create_app()
with app.app_context():
    registros = Facturacion2026.query.filter(
        Facturacion2026.cliente == 'Santander',
        Facturacion2026.jefe_site == 'Ditto, Mariela',
    ).all()
    maestros = AsignacionComercial.query.filter(
        AsignacionComercial.cliente == 'Santander',
        AsignacionComercial.jefe_site == 'Ditto, Mariela',
    ).all()
    antes = {campo: round(sum(float(getattr(r, campo) or 0) for r in registros), 4)
             for campo in NUMERICOS}
    for registro in registros:
        registro.gerente = 'Sin gerencia'
    for maestro in maestros:
        maestro.gerente = 'Sin gerencia'
    db.session.flush()
    despues = {campo: round(sum(float(getattr(r, campo) or 0) for r in registros), 4)
               for campo in NUMERICOS}
    assert antes == despues, 'La reasignación modificó valores numéricos'
    db.session.add(HistorialCambio(
        accion='edicion', entidad='asignacion_comercial', entidad_id='santander-ditto',
        resumen='Santander / Ditto, Mariela reasignado a Sin gerencia',
        detalle=f'{len(maestros)} maestros y {len(registros)} registros de facturación. Valores numéricos intactos. Respaldo: {respaldo.name}',
        antes='Quesada, Mariano', despues='Sin gerencia',
    ))
    db.session.commit()
print(f'Reasignación OK: {len(maestros)} maestros y {len(registros)} registros. Respaldo: {respaldo}')
