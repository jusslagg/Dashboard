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
from app.routes import metricas_matriz


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
assert {(fila['jefatura'], fila['nombre']) for fila in datos['apertura_jefe_site']} == {
    ('Antelo, Micaela', 'Abonos'), ('Del Soto, Alejandro', 'Retención Cable'),
}
assert sum(fila['total']['horas_objetivo'] for fila in datos['resumen_segmento']) == 300

for seccion in ('total_gerencia', 'resumen_segmento', 'resumen_jefatura', 'apertura_jefe_site'):
    for grupo in datos[seccion]:
        celdas = [grupo['total'], *(valor for valor in grupo['meses'].values() if valor)]
        for celda in celdas:
            objetivo = celda['valor_hora_objetivo']
            realizado = celda['valor_hora_realizado']
            esperado = round(realizado / objetivo * 100, 2) if objetivo else 0
            assert celda['porcentaje_valor_hora'] == esperado, (seccion, grupo['nombre'], celda)

# Reproduce las excepciones que rompían la equivalencia con el Excel:
# el importe real puede ser manual y el objetivo de horas puede usar el VH
# alcanzado cuando el ajuste se informa como bono separado.
registro_excepcion = Facturacion2026(
    fecha=date(2026, 2, 1), mes='2026-02', cliente='Personal', gerente='Personal',
    jefe_site='Antelo, Micaela', campania='Servicio con ajuste',
    subcampania='Servicio con ajuste', tipo_negocio='Personal CX',
    tipo_jornada='Diurna', horas_objetivo=100, horas_facturadas=80,
    horas_penalizadas=10, valor_hora_objetivo=12, valor_hora=10,
    facturado_horas_manual=400, objetivo_separar_ajuste_vh=True,
)
metricas = metricas_matriz([registro_excepcion])
assert metricas['valor_hora_objetivo'] == 10
assert metricas['valor_hora_realizado'] == 5
assert metricas['porcentaje_valor_hora'] == 50

registro_objetivo_negativo = Facturacion2026(
    fecha=date(2026, 3, 1), mes='2026-03', cliente='Personal', gerente='Personal',
    jefe_site='Antelo, Micaela', campania='Servicio con objetivo negativo',
    subcampania='Servicio con objetivo negativo', tipo_negocio='Personal CX',
    tipo_jornada='Diurna', horas_objetivo=100, horas_facturadas=80,
    horas_penalizadas=0, valor_hora_objetivo=-10, valor_hora=5,
)
metricas_negativas = metricas_matriz([registro_objetivo_negativo])
assert metricas_negativas['valor_hora_objetivo'] == -10
assert metricas_negativas['valor_hora_realizado'] == 5
assert metricas_negativas['porcentaje_valor_hora'] == -50
print('OK: matriz por segmento, jefatura y servicio alineada con Datos Maestros.')
