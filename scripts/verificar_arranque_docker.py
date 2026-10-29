"""Smoke-test Docker runtime settings on the host; does not replace a Docker build."""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
from contextlib import nullcontext
from uuid import uuid4
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / '.cache').mkdir(exist_ok=True)

with nullcontext(ROOT / '.cache' / ('docker-smoke-' + uuid4().hex)) as folder:
    # Inherit workspace ACLs on Windows instead of tempfile's private-directory ACL.
    folder.mkdir()
    os.environ.update(
        DATABASE_URL='sqlite:///' + (folder / 'facturacion.db').as_posix(),
        APP_ENV='production', SECRET_KEY=secrets.token_urlsafe(48),
        FLASK_HOST='127.0.0.1', USE_DEV_SERVER='0', FLASK_DEBUG='0',
        CORS_ORIGINS='https://dashboard.example.test',
    )
    from app import create_app
    from app.models import db, Usuario

    app = create_app()
    app.config['TESTING'] = True
    assert app.config['SESSION_COOKIE_SECURE']
    password = secrets.token_urlsafe(24)
    with app.test_client() as client:
        who = client.get('/api/auth/me', base_url='https://dashboard.example.test').get_json()
        assert who['requiere_setup']
        setup = client.post('/api/usuarios/setup', base_url='https://dashboard.example.test',
                            json={'nombre':'Container smoke', 'email':'docker@example.test', 'password':password},
                            headers={'X-CSRF-Token':who['csrf_token'], 'Origin':'https://dashboard.example.test'})
        assert setup.status_code == 200 and setup.get_json()['success']
        assert 'Secure' in setup.headers.get('Set-Cookie', '')
        for path in ('/', '/matriz-proyecciones', '/api/dashboard/desvios?year=2026', '/guia-usuario', '/guia-usuario/descargar'):
            response = client.get(path, base_url='https://dashboard.example.test')
            assert response.status_code == 200, (path, response.status_code)
    with app.app_context():
        db.session.remove()
        db.engine.dispose()

    restarted = create_app()
    restarted.config['TESTING'] = True
    with restarted.app_context():
        assert Usuario.query.filter_by(email='docker@example.test').count() == 1
    with restarted.test_client() as client:
        token = client.get('/api/auth/me', base_url='https://dashboard.example.test').get_json()['csrf_token']
        login = client.post('/api/auth/login', base_url='https://dashboard.example.test',
                            json={'email':'docker@example.test','password':password},
                            headers={'X-CSRF-Token':token,'Origin':'https://dashboard.example.test'})
        assert login.status_code == 200 and login.get_json()['success']
    with restarted.app_context():
        db.session.remove()
        db.engine.dispose()

    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    environment = {**os.environ, 'PORT':str(port)}
    with (folder / 'server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable,'run.py'], cwd=ROOT, env=environment, stdout=log, stderr=log)
        try:
            opener = build_opener(ProxyHandler({}))
            deadline = time.monotonic() + 40
            while True:
                if process.poll() is not None:
                    raise AssertionError('Waitress exited before startup; inspect the test configuration.')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/login', timeout=1) as response:
                        if response.status == 200:
                            break
                except (OSError,URLError):
                    pass
                if time.monotonic() > deadline:
                    raise AssertionError('Waitress startup timed out.')
                time.sleep(.2)
            health = subprocess.run([sys.executable,'scripts/docker_healthcheck.py'],cwd=ROOT,env=environment,capture_output=True)
            assert health.returncode == 0
        finally:
            process.terminate()
            process.wait(timeout=15)
    health = subprocess.run([sys.executable,'scripts/docker_healthcheck.py'],cwd=ROOT,env=environment,capture_output=True)
    assert health.returncode == 1, 'Stopped service must fail the healthcheck'
    os.environ['SECRET_KEY'] = 'generar-invalid-placeholder'
    try:
        create_app()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Production must reject placeholder secrets.')

print('OK: isolated fresh DB, HTTPS setup/login, Secure cookies, key validation, views/guide/API, persistence and Waitress healthcheck success/failure.')
print('Host smoke test only: Docker build and container execution still require Docker Engine.')
