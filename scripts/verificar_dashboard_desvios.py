"""Reconciliation and read-only regression checks using an isolated DB copy."""
from pathlib import Path
from datetime import date
from urllib.parse import urlencode
import os
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
folder = ROOT / '.cache' / 'dashboard-desvios'
folder.mkdir(parents=True, exist_ok=True)
database = folder / 'verification.db'
with sqlite3.connect(f'file:{(ROOT / "instance/facturacion.db").as_posix()}?mode=ro', uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()

from app import create_app
from app.models import Usuario, Facturacion2026
from app.dashboard_desvios import resumen_desvio, construir_dashboard_desvios

app = create_app()
app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

def reconcile(summary):
    components = sum(summary[key] for key in ('desvio_horas', 'desvio_variable', 'penalizaciones_bonos', 'ajuste_objetivo', 'redondeo'))
    assert abs(components - summary['desvio']) < .011, summary

with app.app_context(), app.test_client() as client:
    user = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
    with sqlite3.connect(database) as connection:
        before = list(connection.iterdump())
    options = client.get('/api/filtros').get_json()['filtros']
    queries = ['', 'year=2026', 'mes=2026-01', 'year=1900']
    for key, name in [('cliente','clientes'), ('gerente','gerentes'), ('jefe_site','jefes_site'), ('campania','campanias')]:
        queries.append(urlencode([(key,value) for value in options[name][:2]]))
    total_clients = 0
    for query in queries:
        response = client.get('/api/dashboard/desvios?' + query)
        assert response.status_code == 200
        data = response.get_json()
        kpis = client.get('/api/kpis?' + query).get_json()['kpis']
        existing = client.get('/api/por-cliente?' + query).get_json()['clientes']
        expected = {item['cliente']:item for item in existing if item['registros']}
        assert set(expected) == {item['cliente'] for item in data['clientes']}
        assert abs(data['totales']['desvio'] - kpis['desvio']) < .011
        assert abs(sum(item['resumen']['desvio'] for item in data['clientes']) - kpis['desvio']) <= .011 * max(1,len(expected))
        for item in data['clientes']:
            assert item['resumen']['desvio'] == expected[item['cliente']]['desvio']
            reconcile(item['resumen'])
            for summary in item['meses'].values():
                reconcile(summary)
        for direction in ('positivo','negativo','sin_desvio'):
            filtered = client.get('/api/dashboard/desvios?' + query + '&direccion=' + direction).get_json()
            assert {item['cliente'] for item in filtered['clientes']} == {item['cliente'] for item in data['clientes'] if item['direccion'] == direction}
        total_clients += len(data['clientes'])
    data = client.get('/api/dashboard/desvios?year=2026').get_json()
    assert all('campanias' not in item for item in data['clientes']), 'Campaigns should be loaded only when requested'
    assert all('campanias' not in item for item in client.get('/api/dashboard/desvios?year=2026&apertura=campanias').get_json()['clientes'])
    for item in data['clientes'][:5]:
        for month in ('', '2026-01'):
            query = urlencode({'year':2026,'cliente_grupo':item['cliente'],'apertura':'campanias', **({'mes':month} if month else {})})
            detailed = client.get('/api/dashboard/desvios?' + query).get_json()
            for account in detailed['clientes']:
                campaigns = account['campanias']
                assert sum(campaign['registros'] for campaign in campaigns) == account['registros']
                assert abs(sum(campaign['resumen']['desvio'] for campaign in campaigns) - account['resumen']['desvio']) < .011 * max(1,len(campaigns))
                for campaign in campaigns:
                    reconcile(campaign['resumen'])
                    for summary in campaign['meses'].values():
                        reconcile(summary)
    if data['clientes']:
        name = data['clientes'][0]['cliente']
        result = client.get('/api/dashboard/desvios?' + urlencode({'year':2026,'cliente_grupo':name})).get_json()
        assert [item['cliente'] for item in result['clientes']] == [name]
    assert not client.get('/api/dashboard/desvios?buscar=nonexistent-ux-client').get_json()['clientes']
    with sqlite3.connect(database) as connection:
        assert list(connection.iterdump()) == before, 'GET exploration must not write billing records'

    def record(month, goal, actual, **extra):
        values = dict(fecha=date(2026,month,1), mes=f'2026-{month:02d}', cliente='UX fixture', tipo_jornada='Completa',
                      horas_objetivo=goal, horas_facturadas=actual, horas_penalizadas=0, valor_hora=10,
                      es_next_gen=False, objetivo_separar_ajuste_vh=False, bonos=0, penalizaciones=0,
                      variable_objetivo=0, variable_productivo=0, netx_gen=0, otros=0)
        values.update(extra)
        return Facturacion2026(**values)
    a, b = record(1,10,20), record(2,90,45)
    weighted = resumen_desvio([a,b])
    assert weighted['cumplimiento_horas'] == 65 and weighted['cumplimiento_facturacion'] == 65
    override = resumen_desvio([record(1,10,20,control_objetivo_total=125)])
    assert override['ajuste_objetivo'] == -25 and override['desvio'] == 75
    reconcile(override)
    zero = resumen_desvio([record(1,0,0)])
    assert zero['cumplimiento_facturacion'] is None and zero['cumplimiento_horas'] is None
    independent = resumen_desvio([record(1,10,20,es_next_gen=True,netx_gen=500)])
    assert independent['desvio'] == 0 and independent['total_teorico'] == 0
    assert resumen_desvio([record(1,10,20,tarifacion=500,otros=80)])['desvio'] == 100
    reconcile(independent)
    fixtures = [record(1,10,20,campania='Shared'),record(2,90,45,campania='Shared'),
                record(1,10,0,campania=None),record(1,10,30,campania='Sin campaña asignada'),
                record(1,10,999,cliente='Another client',campania='Shared')]
    grouped = construir_dashboard_desvios(fixtures,{'cliente_grupo':'UX fixture','apertura':'campanias','direccion':'negativo'})
    campaigns = grouped['clientes'][0]['campanias']
    assert len(campaigns) == 3, 'A missing campaign must not merge with a named campaign'
    shared = next(item for item in campaigns if item['campania'] == 'Shared')
    assert shared['resumen']['cumplimiento_horas'] == 65, 'Campaign percentages must be weighted'
    assert shared['resumen']['desvio'] == -350, 'Shared names must not mix clients'
    assert any(item['direccion'] == 'positivo' for item in campaigns), 'Show all campaign directions inside the selected negative client'
    assert next(item for item in campaigns if item['campania'] is None)['registros'] == 1
print(f'OK: {total_clients} client summaries reconcile; filters, weighted percentages, imported targets, independent concepts and read-only GET verified.')
