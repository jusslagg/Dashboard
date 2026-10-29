"""Verify module boundaries using temporary users in an isolated database copy."""
from pathlib import Path
import os
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
folder = ROOT / '.cache' / 'acceso-proyectados'
folder.mkdir(parents=True, exist_ok=True)
database = folder / 'verification.db'
with sqlite3.connect(f'file:{(ROOT / "instance/facturacion.db").as_posix()}?mode=ro', uri=True) as source:
    with sqlite3.connect(database) as target:
        source.backup(target)
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()

from app import create_app
from app.models import Usuario, db
from app import routes

app = create_app()
app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
endpoints = ['/api/matriz-precios', '/api/resumen-proyeccion', '/api/personal-distribucion', '/api/tarifaciones', '/api/next-gen']
with app.app_context(), app.test_client() as client:
    users = []
    for role in ('Tesorero', 'RMO_OPS'):
        user = Usuario(nombre='UX verification', email=f'ux-access-{role}@example.invalid',
                       rol=role, password_hash='unused-test-account', activo=True, debe_cambiar_password=False)
        db.session.add(user)
        users.append(user)
    db.session.commit()
    projection_user, billing_user = users
    assert projection_user.puede_ver_proyecciones and not projection_user.puede_ver_facturacion
    assert not projection_user.puede_editar
    assert routes.modulo_solicitado('/resumen') == 'proyecciones'
    assert routes.modulo_solicitado('/resumen-horas') == 'facturacion'
    with client.session_transaction() as session:
        session['usuario_id'] = projection_user.id
        session['csrf_token'] = 'verification-only'
    current_routes = routes.RUTAS_PROYECCIONES
    added_prefixes = {'/api/matriz-precios', '/api/resumen-proyeccion', '/api/sites-proyeccion', '/api/tarifaciones', '/api/next-gen', '/api/personal-distribucion'}
    routes.RUTAS_PROYECCIONES = tuple(path for path in current_routes if path not in added_prefixes)
    for endpoint in endpoints:
        assert client.get(endpoint + '?year=2026').status_code == 403, endpoint + ': baseline must reproduce denial'
    routes.RUTAS_PROYECCIONES = current_routes
    for endpoint in endpoints:
        response = client.get(endpoint + '?year=2026')
        assert response.status_code == 200 and response.get_json()['success'], endpoint
    for endpoint in ['/api/matriz-precios', '/api/next-gen', '/api/tarifaciones', '/api/personal-distribucion', '/api/sites-proyeccion']:
        response = client.post(endpoint, json={}, headers={'X-CSRF-Token': 'verification-only'})
        assert response.status_code == 403, endpoint + ': read access must not permit edits'
    assert client.get('/resumen-horas').status_code == 403
    with client.session_transaction() as session:
        session['usuario_id'] = billing_user.id
    for endpoint in endpoints:
        assert client.get(endpoint + '?year=2026').status_code == 403, endpoint + ': billing-only user must not access projections'
    assert client.get('/resumen-horas').status_code == 200
print('OK: baseline reproduced; Proyectados-only profile can read all five APIs; edits and billing-only access remain denied.')
