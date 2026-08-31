"""Crea maestros faltantes respaldados por dimensiones ya facturadas."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app, db  # noqa: E402
from app.models import HistorialCambio  # noqa: E402
from app.routes import obtener_o_crear_asignacion  # noqa: E402

ALTAS = [
    dict(cliente='BiBank', gerente='Multicuentas', jefe_site='Surace, Carolina',
         campania='BiBank', subcampania='BiBank', tipo_negocio=None, es_next_gen=False),
    dict(cliente='Santander Getnet', gerente='Quesada, Mariano', jefe_site='De la Vega, Roxana',
         campania='Santander Getnet', subcampania='Farming & Hunting', tipo_negocio=None, es_next_gen=False),
    dict(cliente='SET UP', gerente='NextGen', jefe_site='Ditto, Mariela',
         campania='SET UP', subcampania='SET UP', tipo_negocio=None, es_next_gen=True),
]

base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-completar-maestros-{marca}.db'
shutil.copy2(base, respaldo)
app = create_app()
with app.app_context():
    creadas = []
    for campos in ALTAS:
        asignacion, creada = obtener_o_crear_asignacion(campos)
        if creada:
            creadas.append(asignacion.label)
    db.session.add(HistorialCambio(
        accion='creacion', entidad='asignacion_comercial', entidad_id='integridad-importacion',
        resumen=f'Datos Maestros completados: {len(creadas)} asignaciones',
        detalle=f'{"; ".join(creadas)}. Respaldo: {respaldo.name}',
    ))
    db.session.commit()
print(f'Maestros OK: {len(creadas)} creados. Respaldo: {respaldo}')
