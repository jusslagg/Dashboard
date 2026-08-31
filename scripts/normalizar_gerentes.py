"""Normaliza gerentes actuales y conserva un respaldo recuperable."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app, db  # noqa: E402
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio, Usuario, normalizar_gerente  # noqa: E402

base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-normalizar-gerentes-{marca}.db'
shutil.copy2(base, respaldo)

app = create_app()
with app.app_context():
    cambios = []
    for modelo, campo, etiqueta, vacio in (
        (Facturacion2026, 'gerente', 'facturacion', None),
        (AsignacionComercial, 'gerente', 'datos_maestros', 'Sin gerencia'),
        (Usuario, 'gerente_asignado', 'usuarios', None),
    ):
        cantidad = 0
        for registro in modelo.query.all():
            anterior = getattr(registro, campo)
            nuevo = 'NextGen' if isinstance(registro, Facturacion2026) and registro.es_next_gen else (normalizar_gerente(anterior) or vacio)
            if anterior != nuevo:
                setattr(registro, campo, nuevo)
                cantidad += 1
        cambios.append((etiqueta, cantidad))
    detalle = ', '.join(f'{nombre}: {cantidad}' for nombre, cantidad in cambios)
    db.session.add(HistorialCambio(
        accion='edicion', entidad='gerentes', entidad_id='normalizacion',
        resumen='Normalización general del padrón de gerentes',
        detalle=f'{detalle}. Respaldo: {respaldo.name}',
    ))
    db.session.commit()
print(f'Normalización OK ({detalle}). Respaldo: {respaldo}')
