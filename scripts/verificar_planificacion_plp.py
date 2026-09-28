"""La planificación manual no se alimenta de Proforma ni altera el cierre."""
import json
import os
from pathlib import Path
import sys
import zlib

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import ProformaPersonal, SeguimientoPersonalImportacion, Usuario
from app.routes import celda_seguimiento_automatica as cell, clave_horas_auxiliar_personal

app = create_app()
app.config['TESTING'] = True
with app.app_context(), app.test_client() as client:
    user = Usuario(nombre='Prueba', email='plp@example.test', rol='Admin', puesto='Administrador',
                   activo=True, debe_cambiar_password=False)
    user.set_password('Prueba12345')
    db.session.add(user)
    specs = {'base_objetivo_masivo': (25, 2), '2026': (33, 1),
             'auxiliar_horas_plp_masivo': (23, 1), 'precios': (19, 13), 'aux': (13, 1)}
    hojas = {key: {'cantidad_columnas': width, 'filas': [[cell() for _ in range(width)] for _ in range(headers)]}
             for key, (width, headers) in specs.items()}
    for tipo, horas in [('Diurnas', 100), ('Nocturnas', 20), ('Feriados', 5)]:
        db.session.add(ProformaPersonal(tipo_proforma='Masivo', estado_proforma='Proyectada',
                       fdv='FDV', periodo='202609', negocio='PPAY', sitio_proveedor='CAT',
                       segmento='Pay Digital', tipo_hora=tipo, total_horas=horas, precio=10,
                       monto_fijo=horas * 10, monto_variable=0, total_proyeccion=horas * 10))
    key = clave_horas_auxiliar_personal('202609', 'PPAY', 'Pay Digital', 'Diurnas')
    original = {'periodo': '202609', 'grupo': 'PPAY', 'campania': 'Pay Digital', 'tipo_vh': 'Diurnas',
                'proyectada': 100, 'definitiva': 77, 'brutas': 76, 'adh': -.05}
    config = SeguimientoPersonalImportacion(archivo='fixture.xlsx', contenido_xlsx=b'',
        contenido_hojas=zlib.compress(json.dumps({'hojas': hojas, 'ajustes_auxiliar_horas': {key: original}}).encode()))
    db.session.add(config); db.session.commit()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'plp-test'
    headers = {'X-CSRF-Token': 'plp-test'}
    def rows():
        response = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=auxiliar_horas_plp_masivo')
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.json['hoja']['filas'][1:]
    assert all(row[5]['v'] is None for row in rows()), 'Las horas antiguas de Proforma no son planificación'
    def objectives(period='202609', campaign='Pay Digital'):
        response = client.get(f'/api/seguimiento-personal/hoja?importacion_id={config.id}&hoja=base_objetivo_masivo')
        assert response.status_code == 200
        return {row[4]['v']: row for row in response.json['hoja']['filas'][2:]
                if row[3]['v'] == campaign and row[5]['v'].replace('-', '').startswith(period)}
    assert objectives()['Diurnas'][6]['v'] == -25, 'El blanco equivale a cero para SUMIFS, sin recortar negativos'
    identity = {k: original[k] for k in ('periodo', 'grupo', 'campania', 'tipo_vh')}
    def save(value, extra=None):
        return client.post('/api/seguimiento-personal/auxiliar-horas/lote', headers=headers,
                           json={'importacion_id': config.id, 'filas': [{**identity, 'planificadas_plp': value}] + (extra or [])})
    assert save('6.822,50').status_code == 200
    current = json.loads(zlib.decompress(config.contenido_hojas))['ajustes_auxiliar_horas'][key]
    assert current['planificadas_plp'] == 6822.5
    assert all(current[k] == original[k] for k in ('definitiva', 'brutas', 'adh'))
    assert sum(row[5]['v'] or 0 for row in rows()) == 6822.5
    assert sum(row[13]['v'] or 0 for row in rows()) == 125, 'No altera horas facturadas de Proforma'
    base = objectives()
    assert base['Diurnas'][6]['v'] == 6797.5
    assert base['Nocturnas'][6]['v'] == 20 and base['Feriados'][6]['v'] == 5
    assert base['Diurnas'][18]['v'] == 67975 and base['Diurnas'][20]['v'] == 67975
    invalid = [{**identity, 'tipo_vh': 'Nocturnas', 'planificadas_plp': -1}]
    assert save('5000', invalid).status_code == 400
    db.session.expire_all()
    assert sum(row[5]['v'] or 0 for row in rows()) == 6822.5, 'Un lote inválido no se guarda parcialmente'
    for invalid in ('NaN', 'Infinity', '-1', 'texto'):
        assert save(invalid).status_code == 400
    assert save('0').status_code == 200
    assert next(row for row in rows() if row[2]['v'] == 'Diurnas')[5]['v'] == 0
    assert save('').status_code == 200
    assert all(row[5]['v'] is None for row in rows())
    # Nuevas Proformas y meses aplican las mismas reglas sin fórmulas precargadas.
    for campaign in ('Pay Digital', 'Pay Onboarding'):
        for tipo, horas in [('Diurnas', 200), ('Nocturnas', 30), ('Feriados', 10)]:
            db.session.add(ProformaPersonal(tipo_proforma='Masivo', estado_proforma='Proyectada',
                           fdv='FDV', periodo='202610', negocio='PPAY', sitio_proveedor='CAT',
                           segmento=campaign, tipo_hora=tipo, total_horas=horas, precio=10,
                           monto_fijo=horas * 10, monto_variable=0, total_proyeccion=horas * 10))
    db.session.commit()
    assert all(row[5]['v'] is None for row in rows())
    assert objectives('202610')['Diurnas'][6]['v'] == -40
    response = client.post('/api/seguimiento-personal/auxiliar-horas/lote', headers=headers,
        json={'importacion_id': config.id, 'filas': [{**identity, 'periodo': '202610', 'planificadas_plp': 1000}]})
    assert response.status_code == 200
    assert objectives('202610')['Diurnas'][6]['v'] == 960
    assert objectives('202610', 'Pay Onboarding')['Diurnas'][6]['v'] == -40
    assert objectives()['Diurnas'][6]['v'] == -25, 'No cambia otro mes'
    # Al pasar a definitiva, una campaña estándar toma H sin restar jornadas.
    ProformaPersonal.query.filter_by(periodo='202609').update({'estado_proforma': 'Definitiva'})
    db.session.commit()
    assert objectives()['Diurnas'][6]['v'] == 77
    assert objectives()['Nocturnas'][6]['v'] == 0
    assert save('500').status_code == 200
    assert objectives()['Diurnas'][6]['v'] == 77, 'PLP no reemplaza el cierre'
    print('OK: planificación manual, fórmulas, negativos, cierre, lotes atómicos y nuevas Proformas/meses.')
