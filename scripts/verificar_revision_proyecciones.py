"""Check review purity and parity against the existing save on an isolated DB."""
from pathlib import Path
import os
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
folder = ROOT / '.cache' / 'revision-proyecciones'
folder.mkdir(parents=True, exist_ok=True)
database = folder / 'verification.db'
with sqlite3.connect(f'file:{(ROOT / "instance/facturacion.db").as_posix()}?mode=ro', uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()

from app import create_app
from app.models import ProyeccionMatriz, Usuario

app = create_app()
app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

def snapshot():
    with sqlite3.connect(database) as connection:
        return '\n'.join(connection.iterdump())

with app.app_context(), app.test_client() as client:
    user = Usuario.query.filter_by(activo=True).filter(Usuario.rol.in_(('Admin', 'Full'))).first()
    assert user
    with client.session_transaction() as session:
        session['usuario_id'] = user.id
        session['csrf_token'] = 'verification-token'
    headers = {'X-CSRF-Token': 'verification-token'}
    general = ProyeccionMatriz.query.filter_by(tipo_plp=None).filter(ProyeccionMatriz.mes.like('2026-%')).first()
    assert general
    payload = dict(
        id=general.id, cliente=general.cliente, campania=general.campania,
        year=general.year, mes=general.mes, jornadas=[item.to_dict() for item in general.jornadas],
        dotacion_requerida=general.dotacion_requerida, carga_horaria=general.carga_horaria,
        carga_semanal=general.carga_semanal, porcentaje_cumplimiento=general.porcentaje_cumplimiento,
        dias_objetivo_manual=general.dias_objetivo_manual,
        horas_requeridas_override=general.horas_requeridas_manual,
    )
    before = snapshot()
    response = client.post('/api/matriz-proyecciones/revision', json=payload, headers=headers)
    assert response.status_code == 200, response.get_json()
    review = response.get_json()['filas']
    assert len(review) == 13 - int(general.mes[-2:])
    assert snapshot() == before, 'Review must not change any database row'
    saved = client.post('/api/matriz-proyecciones', json=payload, headers=headers)
    assert saved.status_code == 200, saved.get_json()
    records = {item['mes']: item for item in saved.get_json()['proyecciones']}
    for row in review:
        assert row['horas_propuestas'] == records[row['mes']]['horas_proyectadas']
        assert row['dias_objetivo'] == records[row['mes']]['dias_objetivo']
    before = snapshot()
    bulk = client.post('/api/matriz-proyecciones/revision', json={'modo': 'plp', 'year': 2026, 'filas': []}, headers=headers)
    assert bulk.status_code == 200
    assert snapshot() == before, 'PLP review must not recalculate or write data'
    assert client.post('/api/matriz-proyecciones/revision', json={}, headers=headers).status_code == 400
    assert client.post('/api/matriz-proyecciones/revision', json={'modo': 'plp', 'year': 0}, headers=headers).status_code == 400
    assert client.post('/api/matriz-proyecciones/revision', json=payload).status_code == 403
    plp = ProyeccionMatriz.query.filter(ProyeccionMatriz.tipo_plp.isnot(None), ProyeccionMatriz.tipo_plp != '').first()
    if plp:
        payload = dict(cliente='Personal', campania_plp=plp.campania, tipo_plp=plp.tipo_plp,
                       year=plp.year, mes=plp.mes, horas_requeridas_manual=plp.horas_requeridas,
                       carga_horaria_plp=plp.carga_horaria, carga_semanal_plp=plp.carga_semanal,
                       porcentaje_cumplimiento=plp.porcentaje_cumplimiento)
        before = snapshot()
        result = client.post('/api/matriz-proyecciones/revision', json=payload, headers=headers).get_json()
        assert result['success'] and len(result['filas']) == 1
        assert snapshot() == before
print('OK: review writes nothing; monthly hours/days equal saved results; PLP affects one month; validation and CSRF preserved.')
