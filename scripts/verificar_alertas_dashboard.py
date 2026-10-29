"""Check read-only alert details, financial criteria and manager scope on a copy."""
from pathlib import Path
import os
import sqlite3
import sys
from datetime import date
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
folder=ROOT/'.cache'/'alertas-dashboard'
folder.mkdir(parents=True,exist_ok=True)
database=folder/'verification.db'
with sqlite3.connect(f'file:{(ROOT/"instance/facturacion.db").as_posix()}?mode=ro',uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ['DATABASE_URL']='sqlite:///'+database.as_posix()
from app import create_app
from app.models import Usuario,Facturacion2026,db
from app.alertas_dashboard import apertura_alerta

app=create_app()
app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
with app.app_context(),app.test_client() as client:
    admin=Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin','Full'))).first()
    assert client.get('/api/alertas/apertura?alerta=negativo').status_code==403
    with client.session_transaction() as session:
        session['usuario_id']=admin.id
    with sqlite3.connect(database) as connection:
        before=list(connection.iterdump())
    assert client.get('/api/alertas/apertura?alerta=unknown').status_code==400
    for query in ('year=2026','mes=2026-01','year=1900'):
        alerts=client.get('/api/alertas?'+query).get_json()['alertas']
        kpi=client.get('/api/kpis?'+query).get_json()['kpis']['desvio']
        ranking=client.get('/api/alertas/apertura?'+query+'&alerta=desvio').get_json()
        assert ranking['total_desvio']==kpi, 'Ranking must use the dashboard KPI formula'
        assert abs(sum(account['desvio'] for account in ranking['clientes'])-kpi)<.011*max(1,len(ranking['clientes']))
        for account in ranking['clientes']:
            assert abs(sum(row['desvio'] for row in account['campanias'])-account['desvio'])<.011*max(1,len(account['campanias']))
            for campaign in account['campanias']:
                assert abs(sum(month['desvio'] for month in campaign['meses'])-campaign['desvio'])<.011*max(1,len(campaign['meses']))
        negative_alert=next((alert for alert in alerts if alert['titulo']=='Desvio negativo'),None)
        assert (negative_alert is not None)==(kpi<0)
        if negative_alert:
            assert negative_alert['importe']==kpi
        assert all(alert['titulo']=='Alertas' for alert in alerts if alert.get('apertura'))
        for alert in alerts:
            if not alert.get('apertura'):
                continue
            data=client.get('/api/alertas/apertura?'+query+'&alerta='+alert['apertura']).get_json()
            assert data['success'] and isinstance(data['filas'],list)
            for row in data['filas']:
                if query.startswith('mes=') and row['meses']:
                    assert {month['mes'] for month in row['meses']}=={'2026-01'}
                if alert['apertura']=='negativo':
                    assert row['desvio']<0
            assert len({(row['cliente'],row['campania']) for row in data['filas']})==len(data['filas'])
            assert len({row['cliente'] for row in data['clientes']})==len(data['clientes'])
            for account in data['clientes']:
                assert abs(sum(row['desvio'] or 0 for row in account['campanias'])-(account['desvio'] or 0)) < .011*max(1,len(account['campanias']))
    with sqlite3.connect(database) as connection:
        assert before==list(connection.iterdump()),'Reading details must not write billing data'
    manager=Facturacion2026.query.filter(Facturacion2026.gerente.isnot(None),Facturacion2026.gerente!='').first().gerente
    reader=Usuario(nombre='Alert scope fixture',email='alert-scope@example.test',rol='RMO_OPS',puesto='Gte ops',activo=True,debe_cambiar_password=False,gerente_asignado=manager,password_hash='not-a-login')
    db.session.add(reader);db.session.commit()
    with client.session_transaction() as session:
        session['usuario_id']=reader.id
    scoped={(row.cliente,row.campania,row.mes) for row in Facturacion2026.query.filter_by(gerente=manager)}
    for kind in ('cumplimiento_bajo','debajo_objetivo','negativo','horas','riesgo'):
        response=client.get('/api/alertas/apertura?'+urlencode({'alerta':kind,'year':2026}))
        assert response.status_code==200
        assert all((row['cliente'],row['campania'],month['mes']) in scoped for row in response.get_json()['filas'] for month in row['meses'])
        restricted=client.get('/api/alertas/apertura?'+urlencode({'alerta':kind,'gerente':'nonexistent-outside-scope'})).get_json()
        assert not restricted['filas']

    def record(client,campaign,goal,actual):
        return Facturacion2026(fecha=date(2026,1,1),mes='2026-01',cliente=client,campania=campaign,tipo_jornada='Completa',
                               horas_objetivo=goal,horas_facturadas=actual,horas_penalizadas=0,valor_hora=1,
                               objetivo_separar_ajuste_vh=False,es_next_gen=False,variable_objetivo=0,variable_productivo=0,
                               bonos=0,penalizaciones=0,netx_gen=0,otros=0)
    rows=[record('Offset client','Low campaign',100,80),record('Offset client','High campaign',100,120),record('Risk client','Campaign',100,40)]
    negative=apertura_alerta(rows,'negativo')['filas']
    assert len(negative)==2 and sum(row['desvio'] for row in negative)==-80
    risk=apertura_alerta(rows,'riesgo')['filas']
    assert {row['cliente'] for row in risk}=={'Risk client'}
    hours=apertura_alerta(rows,'horas')['filas']
    assert len(hours)==1 and hours[0]['campania']=='High campaign'
    assert not apertura_alerta([record('Good','Campaign',100,120)],'negativo')['filas']
    january=record('Accumulated client','Mixed months',100,80)
    february=record('Accumulated client','Mixed months',100,110);february.mes='2026-02'
    accumulated=apertura_alerta([january,february],'negativo')['filas']
    assert len(accumulated)==1 and accumulated[0]['desvio']==-10
    assert [month['desvio'] for month in accumulated[0]['meses']]==[-20,10]
    assert sum(month['desvio'] for month in accumulated[0]['meses'])==accumulated[0]['desvio']
    february.horas_facturadas=120
    assert all(row['cliente']!='Accumulated client' for row in apertura_alerta([january,february,record('Risk','Other',100,20)],'negativo')['filas'])
    february.horas_objetivo=900;february.horas_facturadas=450;january.horas_facturadas=0
    weighted=apertura_alerta([january,february],'cumplimiento_bajo')['filas'][0]
    assert weighted['cumplimiento']==45,'Accumulated compliance must use totals, not mean monthly percentages'
    hierarchy=apertura_alerta([record('Mixed client','Negative',100,80),record('Mixed client','Positive',100,110)],'negativo')['clientes']
    assert len(hierarchy)==1 and hierarchy[0]['desvio']==-10
    assert {campaign['desvio'] for campaign in hierarchy[0]['campanias']}=={-20,10},'Parent must include offsetting campaigns'
    ranking=apertura_alerta([
        record('Small loss','Campaign',100,90),record('Positive','Campaign',100,130),
        record('Largest loss','Campaign',100,30),record('Zero','Campaign',100,100)
    ],'desvio')
    assert [row['desvio'] for row in ranking['clientes']]==[-70,-10,0,30]
    assert sum(row['desvio'] for row in ranking['clientes'])==ranking['total_desvio']==-50
    assert sum(row['desvio'] for row in ranking['filas'])==ranking['total_desvio']
    variable=record('Comparable','Variable',100,80)
    variable.variable_productivo=10
    excluded=record('Next Gen','Excluded',100,10)
    excluded.es_next_gen=True
    from app.routes import resumen_dashboard,resumen_registros
    records=[variable,excluded]
    comparable=apertura_alerta(records,'desvio')
    assert comparable['total_desvio']==resumen_dashboard(records)['desvio']
    assert comparable['total_desvio']!=resumen_registros(records)['desvio']
    assert next(account for account in comparable['clientes'] if account['cliente']=='Next Gen')['desvio']==0
print('OK: ranked clients reconcile to the alert total; campaign/monthly totals, permissions and read-only checks passed.')
