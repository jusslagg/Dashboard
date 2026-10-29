"""Operational settings, access, race protection and financial parity on a DB copy."""
from pathlib import Path
import json
import os
import secrets
import sqlite3
import sys
from unittest.mock import patch
from flask import g
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
folder = ROOT / '.cache' / 'administracion'
folder.mkdir(parents=True,exist_ok=True)
database = folder / 'verification.db'
with sqlite3.connect(f'file:{(ROOT / "instance/facturacion.db").as_posix()}?mode=ro',uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ.update(DATABASE_URL='sqlite:///' + database.as_posix(),APP_ENV='development',APP_DEFAULT_YEAR='2026')
from app import create_app
from app.models import AsignacionComercial, Campania, ConfiguracionOperativa, Facturacion2026, HistorialCambio, Usuario, db
from app.operacion import anio_operativo

app = create_app()
app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
password = secrets.token_urlsafe(20)
token = secrets.token_urlsafe(20)

def authenticate(client,user_id):
    with client.session_transaction() as session:
        session['usuario_id'] = user_id
        session['csrf_token'] = token

with app.app_context(),app.test_client() as client:
    ConfiguracionOperativa.query.delete()
    user = Usuario(nombre='Operational admin test',email='operational-admin@example.test',rol='Admin',
                   puesto='Administrador',activo=True,debe_cambiar_password=False)
    user.set_password(password)
    db.session.add(user)
    reader = Usuario(nombre='Operational reader test',email='operational-reader@example.test',rol='Tesorero',
                     activo=True,debe_cambiar_password=False)
    reader.set_password(password)
    db.session.add(reader)
    db.session.commit()
    admin_id, reader_id = user.id, reader.id
    assert client.get('/api/administracion/configuracion').status_code == 403
    authenticate(client,reader_id)
    for path in ('/administracion','/api/administracion/configuracion','/api/administracion/pendientes'):
        assert client.get(path).status_code in (302,403),path
    authenticate(client,admin_id)
    assert client.get('/administracion').status_code == 200
    financial_before = client.get('/api/kpis?year=2026').get_json()
    with sqlite3.connect(database) as connection:
        before_get = list(connection.iterdump())
    current = client.get('/api/administracion/configuracion').get_json()
    assert current['anio'] == 2026 and current['version'] == 0
    for year in (2026,2030):
        checks = client.get(f'/api/administracion/pendientes?year={year}')
        assert checks.status_code == 200 and len(checks.get_json()['revisiones']) == 2
    with sqlite3.connect(database) as connection:
        assert before_get == list(connection.iterdump()),'Admin GET checks must not write data'
    assert client.get('/api/administracion/pendientes?year=bad').status_code == 400
    fixture_campaign = Campania(cliente='000 Admin fixture', nombre='Next Gen fixture', activa=True)
    db.session.add(fixture_campaign)
    db.session.flush()
    db.session.add(AsignacionComercial(campania_id=fixture_campaign.id, cliente=fixture_campaign.cliente,
                                      campania=fixture_campaign.nombre, gerente='NextGen', jefe_site='NextGen',
                                      subcampania='Fixture', es_next_gen=True))
    db.session.commit()
    checks = client.get('/api/administracion/pendientes?year=2026').get_json()['revisiones'][0]
    assert not any(row['cliente'] == fixture_campaign.cliente for row in checks['detalle']), 'Next Gen-only campaigns do not require value-hour setup'
    payload = {'anio':2030,'version':0,'password_confirmacion':password}
    assert client.patch('/api/administracion/configuracion',json=payload).status_code == 403,'CSRF required'
    headers = {'X-CSRF-Token':token}
    assert client.patch('/api/administracion/configuracion',json={**payload,'password_confirmacion':'wrong'},headers=headers).status_code == 403
    for invalid in (True,'2030',2030.5,2019,2101):
        assert client.patch('/api/administracion/configuracion',json={**payload,'anio':invalid},headers=headers).status_code == 400
    assert client.patch('/api/administracion/configuracion',json=[1],headers=headers).status_code == 400
    assert client.patch('/api/administracion/configuracion',json={**payload,'version':2**64},headers=headers).status_code == 400
    response = client.patch('/api/administracion/configuracion',json=payload,headers=headers)
    assert response.status_code == 200 and response.get_json()['anio'] == 2030
    assert client.patch('/api/administracion/configuracion',json=payload,headers=headers).status_code == 409,'Reject stale first version'
    payload.update(anio=2031,version=1)
    assert client.patch('/api/administracion/configuracion',json=payload,headers=headers).status_code == 200
    assert client.patch('/api/administracion/configuracion',json=payload,headers=headers).status_code == 409,'Reject stale later version'
    assert client.get('/api/matriz-precios').get_json()['year'] == 2031
    assert client.get('/api/matriz-precios?year=2026').get_json()['year'] == 2026
    assert client.get('/api/matriz-proyecciones').get_json()['year'] == 2031
    assert client.get('/api/kpis?year=2026').get_json() == financial_before
    assert 'value="2031"' in client.get('/administracion').get_data(as_text=True)
    movements = HistorialCambio.query.filter_by(entidad='configuracion_operativa').all()
    assert len(movements) == 2 and json.loads(movements[-1].despues)['anio'] == 2031
    assert all(password not in (item.despues or '') and password not in (item.antes or '') for item in movements)
    # Verify the setting is shared by a second app instance, not stored in process config.
    second = create_app()
    with second.test_request_context('/'):
        assert anio_operativo() == 2031
    assert client.patch('/api/administracion/configuracion',json={'modo':'calendario','version':2,'password_confirmacion':password},headers=headers).status_code == 200
    for calendar_year in (2027,2028,2035):
        with patch('app.operacion.anio_calendario',return_value=calendar_year):
            # The test keeps an outer app context; simulate each real request's fresh g.
            g.pop('anio_operativo',None)
            assert client.get('/api/matriz-precios').get_json()['year'] == calendar_year
            assert client.get('/api/matriz-precios?year=2026').get_json()['year'] == 2026
    # Return the fixture to its initial fixed default for browser checks.
    assert client.patch('/api/administracion/configuracion',json={'anio':2026,'modo':'fijo','version':3,'password_confirmacion':password},headers=headers).status_code == 200
    if '--serve' in sys.argv:
        cookie = client.get_cookie(app.config.get('SESSION_COOKIE_NAME','session'))
        (folder / 'browser.json').write_text(json.dumps({'cookie':{'name':cookie.key,'value':cookie.value},'password':password}),encoding='utf-8')
print('OK: admin authorization, read-only checks, CSRF/password, input validation, stale edits, shared persistence, explicit filters, audit and financial parity.',flush=True)
if '--serve' in sys.argv:
    from waitress import serve
    print('Isolated admin browser server: http://127.0.0.1:8012',flush=True)
    try:
        serve(app,host='127.0.0.1',port=8012,threads=4)
    except KeyboardInterrupt:
        pass
    finally:
        (folder / 'browser.json').unlink(missing_ok=True)
