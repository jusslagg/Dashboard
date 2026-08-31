"""Prueba integral de login, menú, rutas y alcance jerárquico de RBAC.

Usa SQLite en memoria: no crea usuarios ni altera la base operativa.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_COOKIE_SECURE'] = '0'
os.environ.setdefault('SECRET_KEY', 'clave-exclusiva-de-pruebas-rbac')

from app import create_app, db  # noqa: E402
from app.models import Facturacion2026, PUESTOS_POR_ROL, Usuario, permisos_perfil  # noqa: E402


PASSWORD = 'PruebaRoles2026!'
RUTAS = {
    'facturacion': '/control',
    'carga': '/cargar',
    'directorio': '/reloj',
    'proyecciones': '/matriz-proyecciones',
    'administracion': '/usuarios',
    'ayuda': '/guia-usuario',
}


def tiene_facturacion(permisos):
    return any(m.startswith(('facturacion_', 'rmo_')) for m in permisos['modulos'])


def csrf_desde_html(html):
    encontrado = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    assert encontrado, 'La vista de login no entregó token CSRF'
    return encontrado.group(1)


def iniciar_sesion(cliente_http, email):
    vista = cliente_http.get('/login')
    assert vista.status_code == 200, f'GET /login devolvió {vista.status_code}'
    csrf = csrf_desde_html(vista.get_data(as_text=True))
    respuesta = cliente_http.post(
        '/api/auth/login',
        json={'email': email, 'password': PASSWORD},
        headers={'X-CSRF-Token': csrf},
    )
    assert respuesta.status_code == 200, (
        f'Login de {email} devolvió {respuesta.status_code}: {respuesta.get_data(as_text=True)}'
    )
    assert respuesta.get_json()['success'] is True


def links_menu(cliente_http, inicio):
    respuesta = cliente_http.get(inicio, follow_redirects=True)
    assert respuesta.status_code == 200, f'No se pudo renderizar el menú desde {inicio}'
    html = respuesta.get_data(as_text=True)
    return set(re.findall(r'<a\s+href="([^"]+)"\s+class="sidebar-link', html))


def verificar_rutas(cliente_http, esperado, etiqueta):
    for modulo, ruta in RUTAS.items():
        respuesta = cliente_http.get(ruta, follow_redirects=False)
        debe_entrar = esperado[modulo]
        if debe_entrar:
            assert respuesta.status_code == 200, (
                f'{etiqueta}: {ruta} debía estar permitida y devolvió {respuesta.status_code}'
            )
        else:
            assert respuesta.status_code in (302, 403), (
                f'{etiqueta}: {ruta} debía estar bloqueada y devolvió {respuesta.status_code}'
            )


def crear_usuario(nombre, email, rol, puesto, **campos):
    usuario = Usuario(
        nombre=nombre,
        email=email,
        rol=rol,
        puesto=puesto,
        activo=True,
        debe_cambiar_password=False,
        **campos,
    )
    usuario.set_password(PASSWORD)
    db.session.add(usuario)
    return usuario


def crear_factura(cliente, gerente, jefe):
    db.session.add(Facturacion2026(
        fecha=date(2026, 8, 1),
        mes='2026-08',
        cliente=cliente,
        gerente=gerente,
        jefe_site=jefe,
        campania=f'Campaña {cliente}',
        subcampania='General',
        tipo_negocio='Horas',
        tipo_jornada='Completa',
        horas_objetivo=100,
        horas_facturadas=98,
        valor_hora=1000,
    ))


app = create_app()
app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

with app.app_context():
    db.create_all()

    casos = []
    contador = 0
    for rol, puestos in PUESTOS_POR_ROL.items():
        for puesto in puestos:
            contador += 1
            email = f'rbac-{contador}@prueba.local'
            crear_usuario(f'Prueba {rol} {puesto}', email, rol, puesto)
            casos.append((rol, puesto, email))

    # Datos mínimos para comprobar la cascada gerente > jefe > sin restricción.
    crear_factura('Cliente A1', 'Gerencia A', 'Jefatura 1')
    crear_factura('Cliente A2', 'Gerencia A', 'Jefatura 2')
    crear_factura('Cliente B1', 'Gerencia B', 'Jefatura 1')
    crear_factura('Cliente B2', 'Gerencia B', 'Jefatura 3')
    crear_usuario('Alcance gerente', 'alcance-gerente@prueba.local', 'RMO_OPS', 'Gte ops',
                  gerente_asignado='Gerencia A')
    crear_usuario('Alcance jefe', 'alcance-jefe@prueba.local', 'RMO_OPS', 'Jefe de site',
                  jefe_site_asignado='Jefatura 1')
    crear_usuario('Alcance libre', 'alcance-libre@prueba.local', 'RMO_OPS', 'Gte ops')
    usuario_editable = crear_usuario(
        'Usuario editable', 'editable@prueba.local', 'RMO_OPS', 'Jefe de site'
    )

    # También valida que los permisos elegidos por checklist sustituyan la plantilla del rol.
    crear_usuario(
        'Permiso personalizado',
        'personalizado@prueba.local',
        'RMO_OPS',
        'Jefe de site',
        permisos_personalizados=json.dumps({
            'visualizar': True,
            'cargar': False,
            'editar': False,
            'eliminar': False,
            'administrar_perfiles': False,
            'modulos': ['directorio'],
        }),
    )
    db.session.commit()

    # Un administrador puede cambiar rol/puesto/permisos de un usuario existente
    # sin tocar su contraseña ni activar un cambio obligatorio de contraseña.
    hash_original = usuario_editable.password_hash
    admin_email = next(email for rol, _, email in casos if rol == 'Admin')
    with app.test_client() as cliente_http:
        iniciar_sesion(cliente_http, admin_email)
        with cliente_http.session_transaction() as sesion:
            csrf = sesion['csrf_token']
        respuesta = cliente_http.patch(
            f'/api/usuarios/{usuario_editable.id}',
            json={
                'rol': 'Finanzas',
                'puesto': 'Analista Planif y ctrl',
                'gerente_asignado': '',
                'jefe_site_asignado': '',
                'permisos': {
                    'visualizar': True, 'cargar': False, 'editar': False,
                    'eliminar': False, 'administrar_perfiles': False,
                    'modulos': ['facturacion_total', 'directorio', 'proyecciones'],
                },
            },
            headers={'X-CSRF-Token': csrf},
        )
        assert respuesta.status_code == 200, respuesta.get_data(as_text=True)
    db.session.refresh(usuario_editable)
    assert usuario_editable.rol == 'Finanzas'
    assert usuario_editable.puesto == 'Analista Planif y ctrl'
    assert usuario_editable.password_hash == hash_original
    assert usuario_editable.debe_cambiar_password is False

    resultados = []
    for rol, puesto, email in casos:
        permisos = permisos_perfil(rol, puesto)
        esperado = {
            'facturacion': tiene_facturacion(permisos),
            'carga': permisos['cargar'] and tiene_facturacion(permisos),
            'directorio': 'directorio' in permisos['modulos'],
            'proyecciones': 'proyecciones' in permisos['modulos'],
            'administracion': permisos['administrar_perfiles'],
            'ayuda': True,
        }
        inicio = '/control' if esperado['facturacion'] else (
            '/reloj' if esperado['directorio'] else (
                '/matriz-proyecciones' if esperado['proyecciones'] else '/guia-usuario'
            )
        )
        with app.test_client() as cliente_http:
            iniciar_sesion(cliente_http, email)
            links = links_menu(cliente_http, inicio)
            esperados_menu = {
                '/control': esperado['facturacion'],
                '/cargar': esperado['carga'],
                '/reloj': esperado['directorio'],
                '/matriz-proyecciones': esperado['proyecciones'],
                '/usuarios': esperado['administracion'],
                '/guia-usuario': True,
            }
            pagina_con_menu = any((
                esperado['facturacion'], esperado['directorio'],
                esperado['proyecciones'], esperado['administracion'],
            ))
            for ruta, visible in esperados_menu.items():
                if ruta == '/guia-usuario' and not pagina_con_menu:
                    continue
                assert (ruta in links) is visible, (
                    f'{rol}/{puesto}: visibilidad incorrecta de {ruta}'
                )
            verificar_rutas(cliente_http, esperado, f'{rol}/{puesto}')
            if not pagina_con_menu:
                aterrizaje = cliente_http.get('/', follow_redirects=False)
                assert aterrizaje.status_code == 302
                assert aterrizaje.headers['Location'].endswith('/guia-usuario')
        resultados.append(f'{rol}/{puesto}')

    with app.test_client() as cliente_http:
        iniciar_sesion(cliente_http, 'personalizado@prueba.local')
        links = links_menu(cliente_http, '/reloj')
        assert '/reloj' in links and '/control' not in links and '/matriz-proyecciones' not in links
        assert cliente_http.get('/reloj').status_code == 200
        assert cliente_http.get('/control').status_code == 403

    alcances = {}
    for nombre, email in (
        ('gerente', 'alcance-gerente@prueba.local'),
        ('jefe', 'alcance-jefe@prueba.local'),
        ('libre', 'alcance-libre@prueba.local'),
    ):
        with app.test_client() as cliente_http:
            iniciar_sesion(cliente_http, email)
            respuesta = cliente_http.get('/api/datos')
            assert respuesta.status_code == 200
            alcances[nombre] = respuesta.get_json()['data']

    assert {fila['gerente'] for fila in alcances['gerente']} == {'Gerencia A'}
    assert {fila['cliente'] for fila in alcances['gerente']} == {'Cliente A1', 'Cliente A2'}
    assert {fila['jefe_site'] for fila in alcances['jefe']} == {'Jefatura 1'}
    assert {fila['cliente'] for fila in alcances['jefe']} == {'Cliente A1', 'Cliente B1'}
    assert len(alcances['libre']) == 4

print(
    f'RBAC integral OK: {len(resultados)} combinaciones rol/puesto, '
    'login, menú, bloqueo directo, permisos personalizados y 3 alcances jerárquicos.'
)
