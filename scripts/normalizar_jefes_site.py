"""Normaliza el padrón de jefes de site y deja respaldo recuperable."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    AsignacionComercial, Facturacion2026, HistorialCambio, Usuario,
    normalizar_jefe_site,
)

base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-normalizar-jefes-{marca}.db'
shutil.copy2(base, respaldo)

app = create_app()
with app.app_context():
    cambios = []
    for modelo, campo, etiqueta in (
        (Facturacion2026, 'jefe_site', 'facturacion'),
        (AsignacionComercial, 'jefe_site', 'datos_maestros'),
        (Usuario, 'jefe_site_asignado', 'usuarios'),
    ):
        cantidad = 0
        for registro in modelo.query.all():
            anterior = getattr(registro, campo)
            nuevo = normalizar_jefe_site(anterior)
            if anterior != nuevo:
                setattr(registro, campo, nuevo)
                cantidad += 1
        cambios.append((etiqueta, cantidad))

    detalle = ', '.join(f'{nombre}: {cantidad}' for nombre, cantidad in cambios)
    db.session.add(HistorialCambio(
        accion='edicion', entidad='jefes_site', entidad_id='normalizacion',
        resumen='Normalización general del padrón de jefes de site',
        detalle=f'{detalle}. Respaldo: {respaldo.name}',
    ))
    db.session.commit()

print(f'Normalización OK ({detalle}). Respaldo: {respaldo}')
