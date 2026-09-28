"""Verifica los resúmenes por segmento, jefatura y servicio de la matriz."""

import os
from pathlib import Path
import sys
from datetime import date

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import AsignacionComercial, Campania, Facturacion2026, Usuario


app = create_app()
app.config['TESTING'] = True
with app.app_context():
    usuario = Usuario(nombre='Prueba', email='matriz-segmentos@example.test', rol='Admin', activo=True)
    usuario.set_password('Prueba12345')
    db.session.add(usuario)
    for servicio, jefe, segmento, horas in (
        ('Abonos', 'Antelo, Micaela', 'Customer', 100),
        ('Retención Cable', 'Del Soto, Alejandro', 'Retención', 200),
    ):
        campania = Campania(cliente='Personal', nombre=servicio, activa=True)
        db.session.add(campania)
        db.session.flush()
        db.session.add(AsignacionComercial(
            campania_id=campania.id, cliente='Personal', gerente='Personal', jefe_site=jefe,
            campania=servicio, subcampania=servicio, tipo_negocio='Personal CX',
            segmento=segmento, grupo_facturacion='Personal', activa=True,
        ))
        db.session.add(Facturacion2026(
            fecha=date(2026, 1, 1), mes='2026-01', cliente='Personal', gerente='Personal',
            jefe_site=jefe, campania=servicio, subcampania=servicio,
            tipo_negocio='Personal CX', tipo_jornada='Diurna', horas_objetivo=horas,
            horas_facturadas=horas, valor_hora_objetivo=10, valor_hora=10,
        ))
    db.session.commit()
    usuario_id = usuario.id

cliente = app.test_client()
with cliente.session_transaction() as sesion:
    sesion['usuario_id'] = usuario_id

respuesta = cliente.get('/api/matriz?year=2026&cliente=Personal')
assert respuesta.status_code == 200, respuesta.get_data(as_text=True)
datos = respuesta.get_json()
assert {fila['nombre'] for fila in datos['resumen_segmento']} == {'Customer', 'Retención'}
assert {fila['nombre'] for fila in datos['resumen_jefatura']} == {'Antelo, Micaela', 'Del Soto, Alejandro'}
assert {fila['nombre'] for fila in datos['apertura_jefe_site']} == {
    'Antelo, Micaela · Abonos', 'Del Soto, Alejandro · Retención Cable',
}
assert sum(fila['total']['horas_objetivo'] for fila in datos['resumen_segmento']) == 300
print('OK: matriz por segmento, jefatura y servicio alineada con Datos Maestros.')
