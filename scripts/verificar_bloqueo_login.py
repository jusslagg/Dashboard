"""Prueba el bloqueo de cinco minutos sin esperar ni modificar la base operativa."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_COOKIE_SECURE'] = '0'
os.environ['LOGIN_MAX_ATTEMPTS'] = '5'
os.environ['LOGIN_WINDOW_SECONDS'] = '300'
os.environ['LOGIN_BLOCK_SECONDS'] = '300'

from app import create_app, db
from app.models import Usuario
from app import routes


def verificar():
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        usuario = Usuario(nombre='Prueba', email='bloqueo@example.test', rol='Admin',
                          puesto='Administrador', activo=True, debe_cambiar_password=False)
        usuario.set_password('Clave123')
        db.session.add(usuario)
        db.session.commit()

    client = app.test_client()

    def intentar(password='Incorrecta1', email='bloqueo@example.test'):
        token = client.get('/api/auth/me').get_json()['csrf_token']
        return client.post('/api/auth/login', json={'email': email, 'password': password},
                           headers={'X-CSRF-Token': token})

    def comprobar_bloqueo(response, segundos):
        assert response.status_code == 429, response.get_json()
        assert response.get_json()['retry_after'] == segundos
        assert response.headers['Retry-After'] == str(segundos)

    with patch('app.routes.time.monotonic') as reloj:
        for intento in range(4):
            reloj.return_value = 1000 + intento * 10
            assert intentar().status_code == 401
        reloj.return_value = 1040
        comprobar_bloqueo(intentar(), 300)
        # Clave correcta y solicitudes repetidas tampoco saltan ni extienden el bloqueo.
        reloj.return_value = 1041.2
        comprobar_bloqueo(intentar('Clave123'), 299)
        vista = client.get('/login').get_data(as_text=True)
        assert '"retry_after": 299' in vista
        assert '"email": "bloqueo@example.test"' in vista
        assert 'temporizadorLogin' in vista
        assert intentar(email='otra@example.test').status_code == 401
        reloj.return_value = 1339.9
        comprobar_bloqueo(intentar(email=' BLOQUEO@EXAMPLE.TEST '), 1)
        reloj.return_value = 1340
        assert intentar('Clave123').status_code == 200
        assert not routes.LOGIN_BLOCKED_UNTIL
        assert '127.0.0.1:bloqueo@example.test' not in routes.LOGIN_ATTEMPTS

        # Una clave incorrecta al vencer comienza una cuenta nueva, sin bloqueo perpetuo.
        for _ in range(4):
            assert intentar().status_code == 401
        comprobar_bloqueo(intentar(), 300)
        reloj.return_value = 1640
        assert intentar().status_code == 401
        for _ in range(3):
            assert intentar().status_code == 401
        comprobar_bloqueo(intentar(), 300)

        # El login exitoso y los intentos fuera de la ventana reinician el conteo.
        reloj.return_value = 1940
        assert intentar('Clave123').status_code == 200
        for _ in range(4):
            assert intentar().status_code == 401
        assert intentar('Clave123').status_code == 200
        assert intentar().status_code == 401
        reloj.return_value = 2241
        for _ in range(4):
            assert intentar().status_code == 401

    print('OK: quinto fallo bloquea 300 s, informa tiempo restante, conserva el bloqueo '
          'al recargar, no lo prolonga y permite ingresar al vencer.')


if __name__ == '__main__':
    verificar()
