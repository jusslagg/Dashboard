"""Prueba integral de definitivas y cierres con base aislada en memoria."""
import io
import json
import os
import sys
import zlib
from datetime import date, datetime
from pathlib import Path

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from app import create_app, db
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio, SeguimientoPersonalImportacion, Usuario
from app.routes import ENCABEZADOS_PROFORMA_PERSONAL, celda_seguimiento_automatica as cell, snapshot_modelo


def row(width, values=None):
    cells = [cell() for _ in range(width)]
    for index, value in (values or {}).items():
        cells[index] = cell(value)
    return cells


def proforma(negocio, campania, horas):
    book = Workbook()
    book.active.append(list(ENCABEZADOS_PROFORMA_PERSONAL))
    book.active.append(['FDV', 202608, negocio, 'CAT', campania, '', 'Diurnas', horas,
                        100, horas * 100, 0, 0, 0, 0, 0, horas * 100])
    result = io.BytesIO()
    book.save(result)
    result.seek(0)
    return result


def cierre(campania, horas):
    book = Workbook()
    sheet = book.active
    for col, name in [(2, 'Segmento'), (3, 'FECHA'), (7, 'Agentes productivos logueados'),
                      (8, 'Planificación'), (17, 'Tipo de Horas')]:
        sheet.cell(3, col, name)
    for col, value in [(2, campania), (3, datetime(2026, 8, 1)), (7, horas * 1.8),
                       (8, horas * 2), (17, 'Diurnas')]:
        sheet.cell(4, col, value)
    sheet.cell(5, 13, 'Indice de Adhesión')
    sheet.cell(5, 15, 0.9)
    result = io.BytesIO()
    book.save(result)
    result.seek(0)
    return result


app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as client:
    user = Usuario(nombre='Prueba', email='auto@example.test', rol='Admin', puesto='Administrador',
                   activo=True, debe_cambiar_password=False)
    user.set_password('Prueba12345')
    db.session.add(user)
    db.session.flush()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'test-auto'
    headers = {'X-CSRF-Token': 'test-auto'}
    hojas = {
        'base_objetivo_masivo': {'cantidad_columnas': 25, 'filas': [row(25), row(25)]},
        '2026': {'cantidad_columnas': 33, 'filas': [row(33)]},
        'auxiliar_horas_plp_masivo': {'cantidad_columnas': 23, 'filas': [row(23)]},
        'aux': {'cantidad_columnas': 13, 'filas': [row(13)]},
        'precios': {'cantidad_columnas': 14, 'filas': [row(14) for _ in range(13)]},
    }
    for negocio, campania, grupo in [('MASIVO', 'Ventas', 'Personal CX'),
                                      ('SOPORTE', 'Soporte', 'Personal Soporte'),
                                      ('PERSONAL PAY', 'Pay', 'Personal PPAY')]:
        hojas['aux']['filas'].append(row(13, {1: campania, 2: campania, 3: 'Jefe',
                                              4: negocio, 5: grupo, 6: campania}))
        db.session.add(AsignacionComercial(campania_id=1, cliente='Personal', gerente='Gerente',
                       jefe_site='Jefe', campania=campania, subcampania=campania,
                       tipo_negocio=negocio, activa=True))
    config = SeguimientoPersonalImportacion(archivo='config.xlsx', contenido_xlsx=b'',
             contenido_hojas=zlib.compress(json.dumps({'hojas': hojas}).encode()))
    db.session.add(config)
    for campania, grupo, horas, mes, cliente in [
        ('Ventas anterior', 'Personal CX', 11, '2026-08', 'Personal'),
        ('SMB anterior', 'Personal SMB', 12, '2026-08', 'Personal'),
        ('Soporte anterior', 'Personal Soporte', 13, '2026-08', 'Personal'),
        ('Pay anterior', 'Personal PPAY', 14, '2026-08', 'Personal'),
        ('Julio', 'Personal Soporte', 15, '2026-07', 'Personal'),
        ('Ajena', 'Otro', 16, '2026-08', 'Otro cliente'),
    ]:
        db.session.add(Facturacion2026(fecha=date.fromisoformat(mes + '-01'), mes=mes, cliente=cliente,
                       campania=campania, tipo_negocio=grupo, tipo_jornada='Diurnas',
                       horas_objetivo=horas, horas_facturadas=horas, valor_hora=100, es_next_gen=False))
    db.session.commit()

    def upload(tipo, negocio, campania, horas, estado):
        response = client.post('/api/proforma-personal/importar', headers=headers, data={
            'tipo_proforma': tipo, 'estado_proforma': estado,
            'archivo': (proforma(negocio, campania, horas), 'proforma.xlsx')})
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()

    def cargar_cierre(tipo, campania, horas):
        response = client.post('/api/seguimiento-personal/cierre-trafico/importar', headers=headers, data={
            'importacion_id': str(config.id), 'tipo_proforma': tipo,
            'archivo': (cierre(campania, horas), 'cierre.xlsx')})
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()

    def snapshot():
        return {item.campania: snapshot_modelo(item) for item in Facturacion2026.query.all()}

    original = snapshot()
    upload('Soporte', 'SOPORTE', 'Soporte', 20, 'Proyectada')
    pendiente = upload('Soporte', 'SOPORTE', 'Soporte', 30, 'Definitiva')
    assert pendiente['dashboard'][0]['estado'] == 'pendiente'
    assert snapshot() == original, 'Sin cierre no se toca ningún dato del dashboard'
    aplicado = cargar_cierre('Soporte', 'Soporte', 50)
    assert aplicado['aplicado'] and aplicado['dashboard']['estado'] == 'actualizado', aplicado
    actual = snapshot()
    assert actual['Soporte']['horas_facturadas'] == 30
    assert 'Soporte anterior' not in actual
    for clave in ('Ventas anterior', 'SMB anterior', 'Pay anterior', 'Julio', 'Ajena'):
        assert actual[clave] == original[clave], clave
    cierre_historial = HistorialCambio.query.filter_by(entidad='seguimiento_personal_cierre').order_by(HistorialCambio.id.desc()).first()
    response = client.post(f'/api/historial/{cierre_historial.id}/deshacer', headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    restored = snapshot()
    assert restored['Soporte anterior']['horas_facturadas'] == 13 and 'Soporte' not in restored
    assert cargar_cierre('Soporte', 'Soporte', 50)['dashboard']['estado'] == 'actualizado'
    upload('Personal Pay', 'PERSONAL PAY', 'Pay', 24, 'Proyectada')
    pendiente_pay = cargar_cierre('Personal Pay', 'Pay', 55)
    assert not pendiente_pay['aplicado']
    cierres = client.get(f'/api/seguimiento-personal/cierres-trafico?importacion_id={config.id}').get_json()['cierres']
    assert {item['tipo_proforma'] for item in cierres} == {'Soporte', 'Personal Pay'}
    final = upload('Personal Pay', 'PERSONAL PAY', 'Pay', 34, 'Definitiva')
    assert final['dashboard'][0]['estado'] == 'actualizado', final
    final_snapshot = snapshot()
    assert final_snapshot['Pay']['horas_facturadas'] == 34 and 'Pay anterior' not in final_snapshot
    assert final_snapshot['Soporte']['horas_facturadas'] == 30
    for clave in ('Ventas anterior', 'SMB anterior', 'Julio', 'Ajena'):
        assert final_snapshot[clave] == original[clave]
    ultima = HistorialCambio.query.filter_by(entidad='proforma_personal', accion='importacion').order_by(HistorialCambio.id.desc()).first()
    response = client.post(f'/api/historial/{ultima.id}/deshacer', headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert snapshot()['Pay anterior']['horas_facturadas'] == 14
    assert snapshot()['Soporte']['horas_facturadas'] == 30
    upload('Masivo', 'MASIVO', 'Ventas', 40, 'Proyectada')
    assert upload('Masivo', 'MASIVO', 'Ventas', 45, 'Definitiva')['dashboard'][0]['estado'] == 'pendiente'
    horas = client.post('/api/seguimiento-personal/auxiliar-horas/lote', headers=headers, json={
        'importacion_id': config.id, 'filas': [{
            'periodo': '202608', 'grupo': 'MASIVO', 'campania': 'Ventas', 'tipo_vh': 'Diurnas',
            'definitiva': 60, 'brutas': 54, 'adh': 90,
        }],
    })
    assert horas.status_code == 200, horas.get_data(as_text=True)
    assert horas.get_json()['dashboard'][0]['estado'] == 'actualizado'
    assert snapshot()['Ventas']['horas_facturadas'] == 45
    assert snapshot()['Soporte']['horas_facturadas'] == 30
    assert snapshot()['SMB anterior'] == original['SMB anterior'], 'Masivo CX no debe reemplazar SMB ajeno'
    print('OK: actualización automática por tipo y mes, cierres antes y después, preservación y deshacer.')
