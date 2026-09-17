"""Regresión de importar/publicar/deshacer Personal, sin tocar la base local."""
import io
import json
import os
from pathlib import Path
import sys
import zlib
from datetime import date

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from app import create_app, db
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio, ProformaPersonal, SeguimientoPersonalImportacion, Usuario
from app.routes import (
    ENCABEZADOS_PROFORMA_PERSONAL, celda_seguimiento_automatica as cell,
    clave_horas_auxiliar_personal, query_reemplazo_personal_mes,
)


def row(width, values=None):
    result = [cell() for _ in range(width)]
    for index, value in (values or {}).items():
        result[index] = cell(value)
    return result


def workbook(negocio, campania, horas):
    book = Workbook()
    sheet = book.active
    sheet.append(list(ENCABEZADOS_PROFORMA_PERSONAL))
    sheet.append(['FDV', 202608, negocio, 'CAT', campania, '', 'NORMAL', horas,
                  100, horas * 100, 0, 0, 0, 0, 0, horas * 100])
    stream = io.BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as client:
    user = Usuario(nombre='Prueba', email='proforma@example.test', rol='Admin',
                   puesto='Administrador', activo=True, debe_cambiar_password=False)
    user.set_password('Prueba12345')
    db.session.add(user)
    db.session.flush()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'test-proforma'
    headers = {'X-CSRF-Token': 'test-proforma'}
    # El libro contiene datos viejos del mismo mes y un mes ajeno que se conserva.
    specs = {'base_objetivo_masivo': (25, 2, 5), '2026': (33, 1, 2),
             'auxiliar_horas_plp_masivo': (23, 1, 3)}
    hojas = {}
    for key, (width, header_count, period_column) in specs.items():
        hojas[key] = {'cantidad_columnas': width, 'filas':
                     [row(width) for _ in range(header_count)] +
                     [row(width, {period_column: '2026-08-01T00:00:00'}),
                      row(width, {period_column: '2026-07-01T00:00:00'})]}
    hojas['aux'] = {'cantidad_columnas': 13, 'filas': [
        row(13),
        row(13, {1: 'Campaña M', 2: 'Campaña M', 3: 'Antelo, Micaela', 4: 'MASIVO', 5: 'Personal CX', 6: 'Campaña M'}),
        row(13, {1: 'Campaña S', 2: 'Campaña S', 3: 'Canalini, Walter', 4: 'SOPORTE', 5: 'Personal Soporte', 6: 'Campaña S'}),
    ]}
    hojas['precios'] = {'cantidad_columnas': 14, 'filas':
                       [row(14), row(14, {1: 'Diurnas', 9: 999})] +
                       [row(14) for _ in range(11)] +
                       [row(14, {1: '2026-08-01T00:00:00', 2: 999, 3: 'Diurnas'})]}
    ajustes = {}
    for negocio, campania in [('MASIVO', 'Campaña M'), ('SOPORTE', 'Campaña S')]:
        ajustes[clave_horas_auxiliar_personal('202608', negocio, campania, 'Diurnas')] = {
            'periodo': '202608', 'grupo': negocio, 'campania': campania,
            'proyectada': 30, 'definitiva': None,
        }
        db.session.add(AsignacionComercial(campania_id=1, cliente='Personal', gerente='Gerente',
                       jefe_site='Antelo, Micaela', campania=campania, subcampania=campania,
                       tipo_negocio=negocio, activa=True))
    config = SeguimientoPersonalImportacion(archivo='fixture.xlsx', contenido_xlsx=b'',
             contenido_hojas=zlib.compress(json.dumps({'hojas': hojas, 'ajustes_auxiliar_horas': ajustes}).encode()))
    db.session.add(config)
    ajenos = [Facturacion2026(fecha=date(2026, 8, 1), mes='2026-08', cliente='Otro cliente',
                             campania='Ajena', tipo_jornada='Diurnas', horas_facturadas=99),
              Facturacion2026(fecha=date(2026, 7, 1), mes='2026-07', cliente='Personal',
                             campania='Histórica', tipo_jornada='Diurnas', horas_facturadas=88)]
    db.session.add_all(ajenos)
    for registro in ajenos:
        registro.horas_objetivo = 100
        registro.valor_hora = 10
    db.session.commit()

    def post(url, **kwargs):
        response = client.post(url, headers=headers, **kwargs)
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()

    def upload(tipo, negocio, campania, horas, estado='Proyectada'):
        post('/api/proforma-personal/importar', data={'tipo_proforma': tipo,
             'estado_proforma': estado,
             'archivo': (workbook(negocio, campania, horas), 'proforma.xlsx')})
        return HistorialCambio.query.filter_by(entidad='proforma_personal', accion='importacion').order_by(HistorialCambio.id.desc()).first().id

    def publish():
        return post('/api/seguimiento-personal/dashboard', json={'importacion_id': config.id, 'periodo': '202608'})

    def undo(history_id):
        post(f'/api/historial/{history_id}/deshacer')

    def dashboard_hours():
        horas = sorted(float(r.horas_facturadas) for r in query_reemplazo_personal_mes({'mes': '2026-08'}).all())
        response = client.get('/api/datos?mes=2026-08')
        assert response.status_code == 200
        publicadas = [r for r in response.get_json()['data'] if r['cliente'].lower().startswith('personal')]
        assert sorted(float(r['horas_facturadas']) for r in publicadas) == horas
        return horas

    def check_sheets(count):
        for key, (_, header_count, period_column) in specs.items():
            response = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja={key}')
            assert response.status_code == 200, response.get_data(as_text=True)
            rows = response.get_json()['hoja']['filas'][header_count:]
            assert sum(str(r[period_column]['v']).startswith('2026-08') for r in rows) == count, key
            assert sum(str(r[period_column]['v']).startswith('2026-07') for r in rows) == 1, key

    first = upload('Masivo', 'MASIVO', 'Campaña M', 10)
    check_sheets(1)
    assert publish()['creadas'] == 1
    assert dashboard_hours() == [10]
    publish()
    assert dashboard_hours() == [10], 'La publicación repetida no duplica filas'
    second = upload('Soporte', 'SOPORTE', 'Campaña S', 20)
    publish()
    assert dashboard_hours() == [10, 20]
    publicados = query_reemplazo_personal_mes({'mes': '2026-08'}).all()
    assert {item.cliente for item in publicados} == {'Personal'}
    assert {item.tipo_negocio for item in publicados} == {'Personal CX', 'Personal Soporte'}
    replacement = upload('Masivo', 'MASIVO', 'Campaña M', 15)
    publish()
    assert dashboard_hours() == [15, 20]
    undo(replacement)
    check_sheets(2)
    assert dashboard_hours() == [10, 20], 'Restaurar el lote previo recalcula el dashboard'
    undo(first)
    check_sheets(1)
    assert dashboard_hours() == [20], 'Deshacer Masivo conserva Soporte'
    undo(second)
    check_sheets(0)
    assert dashboard_hours() == []
    assert ProformaPersonal.query.count() == 0
    paquete = json.loads(zlib.decompress(config.contenido_hojas))
    assert paquete['ajustes_auxiliar_horas'] == {}, 'Deshacer debe borrar también las horas auxiliares'
    aux = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=aux').get_json()['hoja']
    campanias_aux = {str(r[1]['v']) for r in aux['filas'][1:] if r[1]['v']}
    assert not {'Campaña M', 'Campaña S'} & campanias_aux, 'Aux no debe conservar campañas deshechas'
    precios = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=precios').get_json()
    assert precios['hoja']['filas'][1][9]['v'] is None
    assert all(not str(r[1]['v']).startswith('2026-08') for r in precios['hoja']['filas'][13:])
    assert precios['periodos_proforma'] == []
    # Cargar otra vez vuelve a alimentar las hojas y el dashboard sin resucitar el Excel viejo.
    upload('Masivo', 'MASIVO', 'Campaña M', 12)
    check_sheets(1)
    auxiliar = client.get(
        f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=auxiliar_horas_plp_masivo'
    ).get_json()['hoja']['filas']
    fila_agosto = next(fila for fila in auxiliar[1:] if str(fila[3]['v']).startswith('2026-08'))
    assert float(fila_agosto[5]['v']) == 12, 'La planificación proyectada debe salir de la Proforma'
    publish()
    assert dashboard_hours() == [12]
    upload('Masivo', 'MASIVO', 'Campaña M', 12, 'Definitiva')
    assert {item.estado_proforma for item in ProformaPersonal.query.all()} == {'Definitiva'}
    respuesta_sin_cierre = client.post(
        '/api/seguimiento-personal/dashboard', headers=headers,
        json={'importacion_id': config.id, 'periodo': '202608'},
    )
    assert respuesta_sin_cierre.status_code == 400
    assert 'Brutas' in ' '.join(respuesta_sin_cierre.get_json()['errores'])
    assert all(db.session.get(Facturacion2026, r.id) is not None for r in ajenos)
    assert [float(r.horas_facturadas) for r in ajenos] == [99, 88]
    paquete = json.loads(zlib.decompress(config.contenido_hojas))
    paquete['ajustes_auxiliar_horas'] = {}
    config.contenido_hojas = zlib.compress(json.dumps(paquete).encode())
    db.session.commit()
    response = client.post('/api/seguimiento-personal/dashboard', headers=headers,
                           json={'importacion_id': config.id, 'periodo': '202608'})
    assert response.status_code == 400
    assert dashboard_hours() == [12], 'La validación fallida no modifica lo publicado'
    print('OK: importar, publicar sin duplicados, reemplazar, deshacer por tipo, vaciar y volver a cargar.')
