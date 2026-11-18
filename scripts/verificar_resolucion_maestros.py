"""Comprueba resolución de altas por cliente y puntuación, en una base aislada."""
import os
from pathlib import Path
import sys

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, Campania
from app.routes import resolver_asignacion_importacion

app = create_app()
with app.app_context():
    for cliente, campania, subcampania, gerente in [
        ('Santander', 'SANTANDER GETNET', 'ESTANDAR', 'Gerente correcto'),
        ('Santander Getnet', 'SANTANDER GETNET', 'ESTANDAR', 'Gerente otra cuenta'),
        ('Mirgor', 'Mirgor', 'Samsung Care +', 'Gerente Mirgor'),
        ('Otro', 'Exclusiva', 'Exclusiva', 'Gerente otro'),
    ]:
        catalogo = Campania(cliente=cliente, nombre=campania, activa=True)
        db.session.add(catalogo)
        db.session.flush()
        db.session.add(AsignacionComercial(campania_id=catalogo.id, cliente=cliente, gerente=gerente,
                       jefe_site='Jefe', campania=campania, subcampania=subcampania, activa=True))
    db.session.commit()
    item = {'cliente': 'Santander', 'campania': 'SANTANDER GETNET', 'subcampania': 'ESTANDAR', 'mes': '2026-11'}
    alta, error = resolver_asignacion_importacion(item)
    assert not error and alta.cliente == 'Santander' and item['gerente'] == 'Gerente correcto'
    item = {'cliente': 'Mirgor', 'campania': 'Mirgor', 'subcampania': 'SAMSUNG CARE', 'mes': '2026-12'}
    alta, error = resolver_asignacion_importacion(item)
    assert not error and alta.subcampania == 'Samsung Care +'
    item = {'cliente': 'Santander', 'campania': 'Exclusiva', 'subcampania': 'Exclusiva', 'mes': '2026-12'}
    alta, error = resolver_asignacion_importacion(item)
    assert alta is None and error, 'Una cuenta conocida no debe usar una campaña de otro cliente'
    print('OK: priorización por cliente, puntuación y rechazo de coincidencias de otra cuenta.')
