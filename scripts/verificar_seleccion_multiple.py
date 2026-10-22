"""Checks multiple filters using an isolated copy of the local database.

With --serve, exposes the copied app on port 8011 for the browser audit.
"""
from pathlib import Path
import json
import os
import sqlite3
import sys
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
cache = ROOT / '.cache' / 'multiple-filters'
cache.mkdir(parents=True, exist_ok=True)
database = cache / 'verification.db'
with sqlite3.connect(f'file:{(ROOT / "instance/facturacion.db").as_posix()}?mode=ro', uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
os.environ['TEMPLATES_AUTO_RELOAD'] = '1'

from app import create_app
from app.models import Usuario
from app.routes import filtrar_notificaciones_proyecciones
from werkzeug.datastructures import MultiDict

app = create_app()
app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
with app.app_context(), app.test_client() as client:
    user = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
    assert user
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
    options = client.get('/api/filtros').get_json()['filtros']
    for parameter, key in [('year','years'), ('mes','meses'), ('cliente','clientes'),
                           ('gerente','gerentes'), ('jefe_site','jefes_site'),
                           ('campania','campanias'), ('subcampania','subcampanias'),
                           ('tipo_negocio','tipos_negocio')]:
        selected = options[key][:2]
        query = urlencode([(parameter, value) for value in selected])
        combined = client.get('/api/datos?' + query).get_json()['data']
        individual = [client.get('/api/datos?' + urlencode({parameter:value})).get_json()['data'] for value in selected]
        assert {row['id'] for row in combined} == {row['id'] for rows in individual for row in rows}, parameter
    items = [dict(mes='2026-01', estado='positiva', metricas_cambiadas=['horas'], site='A', cliente='A', campania='A', detalle=''),
             dict(mes='2026-02', estado='negativa', metricas_cambiadas=['precio'], site='B', cliente='B', campania='B', detalle=''),
             dict(mes='2026-03', estado='mixta', metricas_cambiadas=['dotacion'], site='C', cliente='C', campania='C', detalle='')]
    params = MultiDict([('mes','2026-01'),('mes','2026-02'),('estado','positiva'),('estado','negativa'),('metrica','horas'),('metrica','precio')])
    assert filtrar_notificaciones_proyecciones(items, params) == items[:2]
    summary = client.get('/api/resumen-horas?year=2026').get_json()
    names = [item['nombre'] for item in summary['detalle_jefaturas'][:2]]
    selected_summary = client.get('/api/resumen-horas?' + urlencode([('year','2026'), *[('jefatura',name) for name in names]])).get_json()
    for field in ['total_facturado','horas_objetivo','horas_facturadas']:
        expected = sum(item['total'][field] for item in summary['detalle_jefaturas'][:2])
        assert abs(selected_summary['detalle_seleccionado']['total'][field] - expected) < .05, field
    for endpoint, key, parameter, dimension in [('/api/dashboard-operativo','filas','mes','mes'), ('/api/historial','historial','accion','accion')]:
        response = client.get(endpoint + '?year=2026&limite=300').get_json()
        selected = list(dict.fromkeys(row[dimension] for row in response[key]))[:2]
        if selected:
            result = client.get(endpoint + '?' + urlencode([('year','2026'),('limite','300'), *[(parameter,value) for value in selected]])).get_json()[key]
            assert all(row[dimension] in selected for row in result)
    export = client.get('/api/notificaciones-proyecciones/exportar?' + urlencode([('year','2026'), *params.items(multi=True)]))
    assert export.status_code == 200
    if '--serve' in sys.argv:
        token = client.get_cookie(app.config.get('SESSION_COOKIE_NAME','session'))
        (cache / 'session.json').write_text(json.dumps({'name':token.key,'value':token.value}), encoding='utf-8')
print('API OK: union de 8 dimensiones, jefaturas, historial, meses operativos y exportacion multiple.', flush=True)
if '--serve' in sys.argv:
    from waitress import serve
    print('Servidor aislado: http://127.0.0.1:8011', flush=True)
    try:
        serve(app, host='127.0.0.1', port=8011, threads=8)
    except KeyboardInterrupt:
        pass
    finally:
        (cache / 'session.json').unlink(missing_ok=True)
