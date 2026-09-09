import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db, get_csrf_token
from app.models import ProyeccionMatriz

app = create_app()
payload = {
    'id': 35,
    'cliente': 'Gire',
    'campania': 'Gire',
    'year': '2026',
    'mes': '2026-06',
    'jornadas': [
        {'dotacion_requerida': 11, 'carga_semanal': 'L a V', 'carga_horaria': 6},
        {'dotacion_requerida': 6, 'carga_semanal': 'S', 'carga_horaria': 5},
    ],
    'porcentaje_cumplimiento': '95',
    'dias_objetivo_manual': '',
    'horas_requeridas_override': '',
    'tipo_plp': '',
}

with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['csrf_token'] = 'verificacion-gire'
    with app.app_context():
        original_commit = db.session.commit
        db.session.commit = db.session.flush
        try:
            response = client.post(
                '/api/matriz-proyecciones',
                json={**payload, 'csrf_token': 'verificacion-gire'},
                headers={'X-CSRF-Token': 'verificacion-gire'},
            )
            print({'status': response.status_code, 'json': response.get_json()})
            assert response.status_code == 200
            current = db.session.get(ProyeccionMatriz, 35)
            assert len(current.jornadas) == 2
            assert len(response.get_json()['proyecciones']) == 7
        finally:
            db.session.rollback()
            db.session.commit = original_commit
