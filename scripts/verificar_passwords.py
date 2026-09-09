"""Verifica el mínimo de contraseña en todas las rutas con SQLite en memoria."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_COOKIE_SECURE'] = '0'

from app import create_app


def verificar():
    app = create_app()
    app.config['TESTING'] = True
    admin = app.test_client()

    def enviar(client, method, url, payload, status):
        token = client.get('/api/auth/me').get_json()['csrf_token']
        response = client.open(url, method=method, json=payload,
                               headers={'X-CSRF-Token': token})
        data = response.get_json()
        assert response.status_code == status, (url, response.status_code, data)
        if status == 400:
            assert any('8 caracteres' in error for error in data['errores']), data
        return data

    perfil = {'nombre': 'Prueba', 'email': 'admin@example.test', 'password': 'Clave12'}
    enviar(admin, 'POST', '/api/usuarios/setup', perfil, 400)
    perfil['password'] = 'Clave123'
    enviar(admin, 'POST', '/api/usuarios/setup', perfil, 200)

    perfil.update(email='usuario@example.test', rol='Full', puesto='Controller', password='Clave12')
    enviar(admin, 'POST', '/api/usuarios', perfil, 400)
    perfil['password'] = 'Clave123'
    usuario = enviar(admin, 'POST', '/api/usuarios', perfil, 200)['usuario']
    ruta_usuario = f"/api/usuarios/{usuario['id']}"
    enviar(admin, 'PATCH', ruta_usuario, {'password': 'Nueva12'}, 400)
    enviar(admin, 'PATCH', ruta_usuario, {'password': 'Nueva123'}, 200)

    client = app.test_client()
    login = enviar(client, 'POST', '/api/auth/login',
                   {'email': perfil['email'], 'password': 'Nueva123'}, 200)
    assert login['requiere_cambio_password'] is True
    html = client.get('/cambiar-contrasena').get_data(as_text=True)
    assert html.count('minlength="8"') == 2
    assert 'Mínimo 8 caracteres' in html
    cambio = {'password_actual': 'Nueva123', 'password_nueva': 'Final12',
              'password_confirmacion': 'Final12'}
    enviar(client, 'POST', '/api/auth/cambiar-contrasena', cambio, 400)
    cambio.update(password_nueva='Final123', password_confirmacion='Final123')
    enviar(client, 'POST', '/api/auth/cambiar-contrasena', cambio, 200)
    assert client.get('/api/auth/me').get_json()['usuario']['debe_cambiar_password'] is False
    nuevo_login = enviar(app.test_client(), 'POST', '/api/auth/login',
                         {'email': perfil['email'], 'password': 'Final123'}, 200)
    assert nuevo_login['requiere_cambio_password'] is False

    # Las contraseñas de más de ocho caracteres continúan siendo válidas.
    enviar(admin, 'PATCH', ruta_usuario, {'password': 'ClaveLarga123'}, 200)
    for password in ('abcdefgh', 'ABCDEFGH', 'Abcdefgh', '12345678'):
        token = admin.get('/api/auth/me').get_json()['csrf_token']
        response = admin.patch(ruta_usuario, json={'password': password},
                               headers={'X-CSRF-Token': token})
        assert response.status_code == 400
        assert 'mayusculas' in ' '.join(response.get_json()['errores'])
    print('OK: setup, alta, edición, cambio obligatorio y login aceptan 8 caracteres; '
          'se rechazan 7 y se mantienen las reglas de mayúsculas, minúsculas y números.')


if __name__ == '__main__':
    verificar()
