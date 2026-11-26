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


def workbook(negocio, campania, horas, bono=0):
    book = Workbook()
    sheet = book.active
    sheet.append(list(ENCABEZADOS_PROFORMA_PERSONAL))
    porcentaje_bono = bono / (horas * 100) * 100 if horas else 0
    sheet.append(['FDV', 202608, negocio, 'CAT', campania, '', 'NORMAL', horas,
                  100, horas * 100, porcentaje_bono, bono, 0, 0, bono, horas * 100 + bono])
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
        jefe_maestro = 'Del Soto, Alejandro' if campania == 'Campaña M' else 'Canalini, Walter'
        db.session.add(AsignacionComercial(campania_id=1, cliente='Personal', gerente='Gerente',
                       jefe_site=jefe_maestro, campania=campania, subcampania=campania,
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

    def upload(tipo, negocio, campania, horas, estado='Proyectada', bono=0):
        post('/api/proforma-personal/importar', data={'tipo_proforma': tipo,
             'estado_proforma': estado,
             'archivo': (workbook(negocio, campania, horas, bono), 'proforma.xlsx')})
        return HistorialCambio.query.filter_by(entidad='proforma_personal', accion='importacion').order_by(HistorialCambio.id.desc()).first().id

    def publish():
        return post('/api/seguimiento-personal/dashboard', json={'importacion_id': config.id, 'periodo': '202608'})

    def planificar(grupo, campania, horas):
        post('/api/seguimiento-personal/auxiliar-horas/lote', json={'importacion_id': config.id, 'filas': [{
            'periodo': '2026-08', 'grupo': grupo, 'campania': campania, 'tipo_vh': 'Diurnas', 'planificadas_plp': horas,
        }]})

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

    first = upload('Masivo', 'MASIVO', 'Campaña M', 10, bono=250)
    check_sheets(1)
    previo_soporte = Facturacion2026(fecha=date(2026, 8, 1), mes='2026-08', cliente='Personal',
        campania='Anterior soporte', tipo_negocio='Personal Soporte', tipo_jornada='Diurnas',
        horas_objetivo=2, horas_facturadas=2, valor_hora=10, es_next_gen=False)
    db.session.add(previo_soporte)
    db.session.commit()
    preview = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=base_objetivo_masivo').get_json()
    impacto = preview['impacto_dashboard']['202608']
    assert impacto['filas_actuales'] == 0 and impacto['filas_nuevas'] == 1
    assert impacto['estados'] == ['Proyectada'] and 'Personal Soporte' in impacto['grupos_ausentes']
    db.session.delete(previo_soporte)
    db.session.commit()
    assert preview['controles_dashboard']['202608']['Auxiliar Horas PLP']['errores']
    assert client.post('/api/seguimiento-personal/dashboard', headers=headers,
                       json={'importacion_id': config.id, 'periodo': '202608'}).status_code == 400
    planificar('MASIVO', 'Campaña M', 0)
    assert publish()['creadas'] == 1
    assert dashboard_hours() == [10]
    fila_bono = query_reemplazo_personal_mes({'mes': '2026-08'}).one()
    assert fila_bono.jefe_site == 'Del Soto, Alejandro', 'Datos Maestros debe gobernar la jefatura'
    assert float(fila_bono.variable_productivo) == 250
    assert float(fila_bono.variable_objetivo) == 0, 'El bono adicional no puede integrar el teórico'
    assert float(fila_bono.valor_hora_objetivo) == 100
    assert float(fila_bono.control_objetivo_total) == float(fila_bono.horas_objetivo) * 100
    assert float(fila_bono.total_dashboard) == float(fila_bono.facturado_horas) + 250
    publish()
    assert dashboard_hours() == [10], 'La publicación repetida no duplica filas'
    second = upload('Soporte', 'SOPORTE', 'Campaña S', 20)
    planificar('SOPORTE', 'Campaña S', 20)
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
    assert fila_agosto[5]['v'] is None, 'La planificacion manual empieza vacia'
    planificar('MASIVO', 'Campaña M', 12)
    publish()
    assert dashboard_hours() == [12]
    upload('Masivo', 'MASIVO', 'Campaña M', 12, 'Definitiva')
    assert {item.estado_proforma for item in ProformaPersonal.query.all()} == {'Definitiva'}
    definitiva_antes = [item.to_dict() for item in ProformaPersonal.query.all()]
    rechazo = client.post('/api/proforma-personal/importar', headers=headers, data={
        'tipo_proforma': 'Masivo', 'estado_proforma': 'Proyectada',
        'archivo': (workbook('MASIVO', 'Campaña M', 99), 'proyectada_tardia.xlsx'),
    })
    assert rechazo.status_code == 400
    assert 'no puede reemplazar una definitiva' in rechazo.get_json()['diagnostico']['correccion']
    assert [item.to_dict() for item in ProformaPersonal.query.all()] == definitiva_antes
    mixto = Workbook()
    hoja_mixta = mixto.active
    hoja_mixta.append(list(ENCABEZADOS_PROFORMA_PERSONAL))
    for periodo in (202608, 202609):
        hoja_mixta.append(['FDV', periodo, 'MASIVO', 'CAT', 'Campaña M', '', 'NORMAL', 10,
                           100, 1000, 0, 0, 0, 0, 0, 1000])
    archivo_mixto = io.BytesIO()
    mixto.save(archivo_mixto)
    archivo_mixto.seek(0)
    rechazo_mixto = client.post('/api/proforma-personal/importar', headers=headers, data={
        'tipo_proforma': 'Masivo', 'estado_proforma': 'Proyectada',
        'archivo': (archivo_mixto, 'proyectada_dos_meses.xlsx'),
    })
    assert rechazo_mixto.status_code == 400
    assert not ProformaPersonal.query.filter_by(periodo='202609').first()
    assert [item.to_dict() for item in ProformaPersonal.query.all()] == definitiva_antes
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
    upload('Soporte', 'SOPORTE', 'Campaña nueva', 8)
    def nombres_aux():
        filas = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=aux').get_json()['hoja']['filas']
        return {fila[1]['v']: fila for fila in filas[1:]}

    assert nombres_aux()['Campaña nueva'][1]['segmento_pendiente']
    assert not nombres_aux()['Campaña M'][1].get('segmento_pendiente')
    assert nombres_aux()['Campaña M'][3]['de_maestros']
    assert not nombres_aux()['Campaña nueva'][3]['de_maestros']
    catalogo = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=aux').get_json()
    assert set(catalogo['jefes_site_disponibles']) == {'Canalini, Walter', 'Del Soto, Alejandro'}
    manual = {'origen': 'Campaña M', 'segmento': 'Campaña M', 'jefatura': 'Jefatura nueva',
              'tipo_negocio': 'Negocio nuevo', 'proforma': 'Proforma nueva'}
    post('/api/seguimiento-personal/aux-normalizacion/lote',
         json={'importacion_id': config.id, 'filas': [manual]})
    assert [c['v'] for c in nombres_aux()['Campaña M'][3:6]] == ['Jefatura nueva', 'Negocio nuevo', 'Proforma nueva']
    correspondencia = {'origen': 'Campaña nueva', 'segmento': 'Segmento asignado',
                       'jefatura': 'Canalini, Walter', 'tipo_negocio': 'Soporte', 'proforma': 'Personal Soporte'}
    for confirmar in (False, True):
        correspondencia['confirmar_segmento'] = confirmar
        post('/api/seguimiento-personal/aux-normalizacion/lote',
             json={'importacion_id': config.id, 'filas': [correspondencia]})
        fila = nombres_aux()['Campaña nueva']
        assert fila[1]['segmento_pendiente'] == (not confirmar)
        assert fila[2]['v'] == 'Segmento asignado'
        assert fila[3]['v'] == 'Canalini, Walter'
        for hoja in ('aux', 'auxiliar_horas_plp_masivo'):
            datos = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja={hoja}').get_json()
            assert ('Campaña nueva' in datos['pendientes_normalizacion']) == (not confirmar)
    upload('Soporte', 'SOPORTE', 'Campaña nueva', 9)
    assert not nombres_aux()['Campaña nueva'][1]['segmento_pendiente']
    hoja_url = f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=aux'
    def falta_gerente_segmento():
        errores = client.get(hoja_url).get_json()['validaciones_dashboard']['202608']
        return any('Segmento asignado' in error and 'gerente' in error for error in errores)

    assert not falta_gerente_segmento()
    db.session.add(AsignacionComercial(campania_id=1, cliente='Personal', gerente='Otro gerente',
                   jefe_site='Canalini, Walter', campania='Otra campaña', subcampania='Otra campaña',
                   tipo_negocio='Soporte', activa=True))
    db.session.commit()
    assert falta_gerente_segmento(), 'Una jefatura con dos gerentes requiere una asignación específica'
    print('OK: importar, publicar sin duplicados, reemplazar, deshacer por tipo, vaciar y volver a cargar.')
