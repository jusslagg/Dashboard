import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import ProyeccionMatriz

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['csrf_token'] = 'verificacion-carga-personal'
    with app.app_context():
        registro = ProyeccionMatriz.query.filter(
            ProyeccionMatriz.tipo_plp.isnot(None),
            ProyeccionMatriz.tipo_plp != '',
            ProyeccionMatriz.mes.like('2026-%'),
        ).first()
        assert registro is not None
        payload = {
            'year': '2026',
            'filas': [{
                'id': registro.id,
                'eliminar': False,
                'tipo_plp': registro.tipo_plp,
                'mes': registro.mes,
                'campania': registro.campania,
                'horas': registro.horas_requeridas,
                'carga_semanal': registro.carga_semanal or 'L a V',
                'carga_horaria': registro.carga_horaria or 6,
                'porcentaje_cumplimiento': registro.porcentaje_cumplimiento,
            }],
        }
        original_commit = db.session.commit
        db.session.commit = db.session.flush
        try:
            response = client.post(
                '/api/carga-datos-personal', json=payload,
                headers={'X-CSRF-Token': 'verificacion-carga-personal'},
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            assert response.get_json()['success'] is True
            assert len(response.get_json()['proyecciones']) == 1
            print({'status': response.status_code, 'mensaje': response.get_json()['mensaje']})
        finally:
            db.session.rollback()
            db.session.commit = original_commit
