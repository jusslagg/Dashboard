import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import HistorialCambio, Usuario

app = create_app()
email = 'verificacion.historial@local.invalid'

with app.app_context():
    Usuario.query.filter_by(email=email).delete()
    user = Usuario(
        nombre='Verificación Historial',
        email=email,
        rol='Full',
        puesto='Controller',
        permisos_personalizados=json.dumps({
            'visualizar': True,
            'cargar': False,
            'editar': False,
            'eliminar': True,
            'administrar_perfiles': False,
            'modulos': ['facturacion_total'],
        }),
        activo=True,
    )
    user.set_password('Temporal123')
    db.session.add(user)
    db.session.commit()
    user_id = user.id
    no_reversible = HistorialCambio.query.filter_by(entidad='facturacion').order_by(HistorialCambio.id.desc()).first()
    item_id = no_reversible.id if no_reversible else None

try:
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['usuario_id'] = user_id
        page = client.get('/historial')
        api = client.get('/api/historial?limite=1')
        assert page.status_code == 200, page.status_code
        assert api.status_code == 200, api.status_code
        if item_id:
            with client.session_transaction() as session:
                csrf_token = session['csrf_token']
            undo = client.post(
                f'/api/historial/{item_id}/deshacer',
                headers={'X-CSRF-Token': csrf_token},
            )
            assert undo.status_code == 400, undo.status_code
            assert undo.get_json()['errores'][0] == 'Este tipo de movimiento todavía no admite deshacer'
        print({'page': page.status_code, 'api': api.status_code, 'undo_authorized': bool(item_id)})
finally:
    with app.app_context():
        Usuario.query.filter_by(email=email).delete()
        db.session.commit()
