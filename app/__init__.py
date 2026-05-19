# filepath: app/__init__.py
import os
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from flask import Flask, abort, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import inspect, text

db = SQLAlchemy()


DEFAULT_TRUSTED_ORIGINS = (
    'http://127.0.0.1:3000',
    'http://localhost:3000',
    'http://127.0.0.1:8009',
    'http://localhost:8009',
)


def create_app():
    load_dotenv()
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or secrets.token_urlsafe(48)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///facturacion.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_AS_ASCII'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
    app.config['TEMPLATES_AUTO_RELOAD'] = os.getenv('TEMPLATES_AUTO_RELOAD', '0') == '1'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=int(os.getenv('SESSION_MINUTES', '60')))
    app.json.ensure_ascii = False

    origins = configured_origins()
    app.config['TRUSTED_ORIGINS'] = set(origins)
    CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)
    
    db.init_app(app)
    
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    @app.before_request
    def enforce_browser_request_boundaries():
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return None
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        candidate = origin or referer
        if candidate and not origin_is_allowed(candidate):
            abort(403)
        if not csrf_token_is_valid():
            abort(403)
        return None

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com; "
            "connect-src 'self' http://127.0.0.1:8009 http://localhost:8009; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers.setdefault('Cache-Control', 'no-store')
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.context_processor
    def inject_usuario_actual():
        from app.models import Usuario
        usuario_id = session.get('usuario_id')
        usuario = Usuario.query.get(usuario_id) if usuario_id else None
        return {'usuario_actual': usuario, 'csrf_token': get_csrf_token()}
    
    with app.app_context():
        db.create_all()
        ensure_schema()
    
    return app


def configured_origins():
    configured = os.getenv('CORS_ORIGINS')
    if not configured:
        return list(DEFAULT_TRUSTED_ORIGINS)
    origins = [origin.strip().rstrip('/') for origin in configured.split(',') if origin.strip()]
    return origins or list(DEFAULT_TRUSTED_ORIGINS)


def origin_is_allowed(value):
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return False
    origin = f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')
    if origin in current_trusted_origins():
        return True
    request_origin = f'{request.scheme}://{request.host}'.rstrip('/')
    return origin == request_origin


def current_trusted_origins():
    from flask import current_app
    return current_app.config.get('TRUSTED_ORIGINS', set())


def get_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def csrf_token_is_valid():
    expected = session.get('csrf_token')
    supplied = (
        request.headers.get('X-CSRF-Token')
        or request.form.get('csrf_token')
        or (request.get_json(silent=True) or {}).get('csrf_token')
    )
    return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))


def ensure_schema():
    inspector = inspect(db.engine)
    asegurar_administrador_inicial_db()
    if not inspector.has_table('facturacion_2026'):
        return

    asignacion_columns = {column['name'] for column in inspector.get_columns('asignaciones_comerciales')} if inspector.has_table('asignaciones_comerciales') else set()
    if asignacion_columns and 'jefe_site' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN jefe_site VARCHAR(100)"))
    if asignacion_columns and 'tipo_negocio' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN tipo_negocio VARCHAR(100)"))
    if inspector.has_table('asignaciones_comerciales'):
        db.session.execute(text("""
            UPDATE asignaciones_comerciales
            SET jefe_site = 'Sin asignar'
            WHERE jefe_site IS NULL OR jefe_site = ''
        """))
    if inspector.has_table('justificaciones_ajustes'):
        justificacion_columns = {column['name'] for column in inspector.get_columns('justificaciones_ajustes')}
        if 'cantidad' not in justificacion_columns:
            db.session.execute(text("ALTER TABLE justificaciones_ajustes ADD COLUMN cantidad FLOAT DEFAULT 1"))
        if 'precio' not in justificacion_columns:
            db.session.execute(text("ALTER TABLE justificaciones_ajustes ADD COLUMN precio FLOAT DEFAULT 0"))
        db.session.execute(text("""
            UPDATE justificaciones_ajustes
            SET cantidad = 1
            WHERE cantidad IS NULL OR cantidad = 0
        """))
        db.session.execute(text("""
            UPDATE justificaciones_ajustes
            SET precio = importe
            WHERE precio IS NULL OR precio = 0
        """))

    columns = {column['name'] for column in inspector.get_columns('facturacion_2026')}
    missing_columns = {
        'gerente': 'ALTER TABLE facturacion_2026 ADD COLUMN gerente VARCHAR(100)',
        'jefe_site': 'ALTER TABLE facturacion_2026 ADD COLUMN jefe_site VARCHAR(100)',
        'campania': 'ALTER TABLE facturacion_2026 ADD COLUMN campania VARCHAR(100)',
        'subcampania': 'ALTER TABLE facturacion_2026 ADD COLUMN subcampania VARCHAR(100)',
        'tipo_negocio': 'ALTER TABLE facturacion_2026 ADD COLUMN tipo_negocio VARCHAR(100)',
        'horas_penalizadas': 'ALTER TABLE facturacion_2026 ADD COLUMN horas_penalizadas FLOAT DEFAULT 0',
        'valor_hora_objetivo': 'ALTER TABLE facturacion_2026 ADD COLUMN valor_hora_objetivo FLOAT',
        'importe_fijo': 'ALTER TABLE facturacion_2026 ADD COLUMN importe_fijo FLOAT',
        'variable_objetivo': 'ALTER TABLE facturacion_2026 ADD COLUMN variable_objetivo FLOAT DEFAULT 0',
        'variable_productivo': 'ALTER TABLE facturacion_2026 ADD COLUMN variable_productivo FLOAT DEFAULT 0',
    }
    for column, statement in missing_columns.items():
        if column not in columns:
            db.session.execute(text(statement))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET jefe_site = 'Sin asignar'
        WHERE jefe_site IS NULL OR jefe_site = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET campania = 'Operacion 2026'
        WHERE campania IS NULL OR campania = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET subcampania = cliente
        WHERE subcampania IS NULL OR subcampania = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET valor_hora_objetivo = valor_hora
        WHERE valor_hora_objetivo IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET horas_penalizadas = 0
        WHERE horas_penalizadas IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET variable_productivo = 0
        WHERE variable_productivo IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_2026
        SET variable_objetivo = 0
        WHERE variable_objetivo IS NULL
    """))
    db.session.execute(text("""
        INSERT INTO asignaciones_comerciales (cliente, gerente, jefe_site, campania, subcampania, tipo_negocio, activa, creado_en)
        SELECT DISTINCT cliente, COALESCE(gerente, 'Sin asignar'), COALESCE(jefe_site, 'Sin asignar'), campania, subcampania, tipo_negocio, 1, CURRENT_TIMESTAMP
        FROM facturacion_2026
        WHERE cliente IS NOT NULL
          AND campania IS NOT NULL
          AND subcampania IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM asignaciones_comerciales)
    """))
    db.session.commit()


def asegurar_administrador_inicial_db():
    from app.models import HistorialCambio, Usuario

    inspector = inspect(db.engine)
    if not inspector.has_table('usuarios'):
        return
    if Usuario.query.count() == 0:
        return
    if Usuario.query.filter_by(rol='administrador').first():
        return

    primer_usuario = Usuario.query.order_by(Usuario.creado_en.asc(), Usuario.id.asc()).first()
    if not primer_usuario:
        return

    rol_anterior = primer_usuario.rol
    primer_usuario.rol = 'administrador'
    if inspector.has_table('historial_cambios'):
        db.session.add(HistorialCambio(
            usuario_id=primer_usuario.id,
            usuario_nombre=primer_usuario.nombre,
            usuario_email=primer_usuario.email,
            accion='edicion',
            entidad='usuario',
            entidad_id=str(primer_usuario.id),
            resumen=f'Usuario inicial promovido a administrador: {primer_usuario.email}',
            antes=f'{{"rol": "{rol_anterior}"}}',
            despues='{"rol": "administrador"}',
        ))
    db.session.commit()
