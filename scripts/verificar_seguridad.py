"""Controles de regresión para la configuración de seguridad HTTP."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


def verificar():
    errores = []
    app = create_app()
    with app.test_client() as client:
        response = client.get('/login')
        csp = response.headers.get('Content-Security-Policy', '')
        if response.status_code != 200:
            errores.append(f'Login devuelve HTTP {response.status_code}')
        for esperado in ("object-src 'none'", "frame-ancestors 'none'", "connect-src 'self'", "nonce-"):
            if esperado not in csp:
                errores.append(f'CSP no contiene {esperado}')
        for prohibido in ("'unsafe-inline'", 'cdn.tailwindcss.com', 'cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'unpkg.com'):
            if prohibido in csp:
                errores.append(f'CSP todavía contiene {prohibido}')
        for header in ('X-Content-Type-Options', 'X-Frame-Options', 'Permissions-Policy',
                       'Cross-Origin-Resource-Policy', 'X-Permitted-Cross-Domain-Policies'):
            if not response.headers.get(header):
                errores.append(f'Falta el encabezado {header}')
        for recurso in ('vendor/app-tailwind.css', 'vendor/chart.umd.min.js',
                        'vendor/lucide.min.js', 'vendor/fontawesome/css/all.min.css'):
            if client.get(f'/static/{recurso}').status_code != 200:
                errores.append(f'No carga el recurso local {recurso}')

    if any(':3000' in origin for origin in app.config['TRUSTED_ORIGINS']):
        errores.append('Los orígenes autorizados todavía incluyen el puerto 3000')

    anterior = os.environ.get('APP_ENV')
    os.environ['APP_ENV'] = 'production'
    try:
        production_app = create_app()
        if not production_app.config['SESSION_COOKIE_SECURE']:
            errores.append('Producción no fuerza SESSION_COOKIE_SECURE')
        if production_app.debug:
            errores.append('Producción tiene debug activo')
    finally:
        if anterior is None:
            os.environ.pop('APP_ENV', None)
        else:
            os.environ['APP_ENV'] = anterior

    if errores:
        raise AssertionError('\n'.join(errores))
    print('Seguridad HTTP OK: CSP estricta, recursos locales, orígenes y cookies de producción verificados.')


if __name__ == '__main__':
    verificar()
