# filepath: app/__init__.py
import os
import secrets
import base64
import hashlib
import html
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import Flask, abort, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import inspect, text

db = SQLAlchemy()


DEFAULT_TRUSTED_ORIGINS = (
    'http://127.0.0.1:8009',
    'http://localhost:8009',
)


def create_app():
    load_dotenv()
    app = Flask(__name__)

    environment = os.getenv('APP_ENV', 'development').strip().lower()
    secret_key = os.getenv('SECRET_KEY', '').strip()
    if environment == 'production' and (not secret_key or secret_key.startswith('generar-')):
        raise RuntimeError('SECRET_KEY debe configurarse con un valor seguro y persistente en produccion.')
    app.config['APP_ENV'] = environment
    app.config['SECRET_KEY'] = secret_key or secrets.token_urlsafe(48)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///facturacion.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_AS_ASCII'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
    app.config['TEMPLATES_AUTO_RELOAD'] = os.getenv('TEMPLATES_AUTO_RELOAD', '0') == '1'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    cookie_secure_config = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    app.config['SESSION_COOKIE_SECURE'] = environment == 'production' or cookie_secure_config
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=int(os.getenv('SESSION_MINUTES', '60')))
    app.config['DEFAULT_YEAR'] = configured_year('APP_DEFAULT_YEAR', datetime.now().year)
    app.config['PLP_BASE_YEAR'] = configured_year('PLP_BASE_YEAR', 2026)
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
        csp_nonce = secrets.token_urlsafe(18)
        script_attr_hashes = set()
        style_attr_hashes = set()
        if response.mimetype == 'text/html' and not response.direct_passthrough:
            contenido = response.get_data(as_text=True)
            contenido = re.sub(
                r'<(script|style)(?=[\s>])',
                lambda match: f'<{match.group(1)} nonce="{csp_nonce}"',
                contenido,
                flags=re.IGNORECASE,
            )
            patron_atributo = r'\s(on[a-z]+|style)\s*=\s*(["\'])(.*?)\2'
            for atributo, _, valor in re.findall(patron_atributo, contenido, re.IGNORECASE | re.DOTALL):
                digest = base64.b64encode(
                    hashlib.sha256(html.unescape(valor).encode('utf-8')).digest()
                ).decode('ascii')
                destino = style_attr_hashes if atributo.lower() == 'style' else script_attr_hashes
                destino.add(f"'sha256-{digest}'")
            response.set_data(contenido)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        response.headers.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        script_attrs = ' '.join(sorted(script_attr_hashes)) or "'none'"
        style_attrs = ' '.join(sorted(style_attr_hashes)) or "'none'"
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{csp_nonce}'; "
            f"script-src-elem 'self' 'nonce-{csp_nonce}'; "
            f"script-src-attr 'unsafe-hashes' {script_attrs}; "
            f"style-src 'self' 'nonce-{csp_nonce}'; "
            f"style-src-elem 'self' 'nonce-{csp_nonce}'; "
            f"style-src-attr 'unsafe-hashes' {style_attrs}; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
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
        return {
            'usuario_actual': usuario,
            'csrf_token': get_csrf_token(),
            'anio_actual': app.config['DEFAULT_YEAR'],
            'anios_disponibles': range(2020, max(datetime.now().year, app.config['DEFAULT_YEAR']) + 3),
        }
    
    with app.app_context():
        migrar_tabla_facturacion_legacy()
        db.create_all()
        migrar_tipos_numericos_postgresql()
        ensure_schema()
        from app.models import normalizar_nombres_comerciales_existentes
        normalizar_nombres_comerciales_existentes()
    
    return app


def configured_origins():
    configured = os.getenv('CORS_ORIGINS')
    if not configured:
        return list(DEFAULT_TRUSTED_ORIGINS)
    origins = [origin.strip().rstrip('/') for origin in configured.split(',') if origin.strip()]
    return origins or list(DEFAULT_TRUSTED_ORIGINS)


def configured_year(variable, default):
    raw_value = os.getenv(variable, str(default)).strip()
    try:
        year = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f'{variable} debe ser un anio numerico.') from exc
    if not 2020 <= year <= 2100:
        raise RuntimeError(f'{variable} debe estar entre 2020 y 2100.')
    return year


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


def migrar_tabla_facturacion_legacy():
    """Renombra la tabla 2026 conservando IDs, datos y referencias existentes."""
    inspector = inspect(db.engine)
    existe_legacy = inspector.has_table('facturacion_2026')
    existe_anual = inspector.has_table('facturacion_anio')
    if not existe_legacy:
        return
    if existe_anual:
        raise RuntimeError(
            'Existen simultáneamente facturacion_2026 y facturacion_anio; '
            'se requiere conciliación manual antes de iniciar.'
        )
        response.headers.setdefault(
            'Content-Security-Policy-Report-Only',
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
    db.session.execute(text('ALTER TABLE facturacion_2026 RENAME TO facturacion_anio'))
    db.session.commit()


def migrar_tipos_numericos_postgresql():
    """Aplica precisión y escala al migrar una base PostgreSQL existente."""
    if db.engine.dialect.name != 'postgresql':
        return
    contrato = {
        'facturacion_anio': {
            'horas_objetivo': (12, 2), 'horas_facturadas': (12, 2), 'horas_penalizadas': (12, 2),
            'valor_hora_objetivo': (18, 2), 'valor_hora': (18, 2), 'facturado_horas_manual': (18, 2), 'tarifacion': (18, 2),
            'importe_fijo': (18, 2), 'variable_objetivo': (18, 2), 'variable_productivo': (18, 2),
            'bonos': (18, 2), 'penalizaciones': (18, 2), 'netx_gen': (18, 2), 'otros': (18, 2),
        },
        'justificaciones_ajustes': {'cantidad': (18, 4), 'precio': (18, 2), 'importe': (18, 2)},
        'matriz_proyecciones': {
            'dotacion_requerida': (20, 10), 'carga_horaria': (20, 10), 'horas_requeridas': (20, 10),
            'porcentaje_cumplimiento': (15, 10), 'porcentaje_nocturnidad': (15, 10),
            'horas_requeridas_manual': (20, 10),
        },
        'matriz_proyecciones_jornadas': {
            'dotacion_requerida': (20, 10), 'carga_horaria': (20, 10), 'horas_requeridas': (20, 10),
        },
        'personal_distribucion_horas': {'porcentaje_diurno': (15, 10)},
        'matriz_precios': {
            'precio_base': (24, 10), 'alcance_porcentaje': (15, 10), 'precio_final': (24, 10),
            'importe_fijo_mensual': (18, 2),
        },
        'variables_campanias': {'porcentaje': (15, 10)},
        'tarifaciones_campanias': {'monto': (24, 10)},
        'next_gen_dolar': {'valor': (18, 6)},
        'next_gen_productos': {'cantidad_usd': (24, 10), 'cotizacion_aplicada': (24, 10)},
    }
    inspector = inspect(db.engine)
    for tabla, columnas in contrato.items():
        if not inspector.has_table(tabla):
            continue
        actuales = {columna['name']: columna['type'] for columna in inspector.get_columns(tabla)}
        for columna, (precision, escala) in columnas.items():
            tipo = actuales.get(columna)
            if tipo is None or (getattr(tipo, 'precision', None), getattr(tipo, 'scale', None)) == (precision, escala):
                continue
            db.session.execute(text(
                f'ALTER TABLE {tabla} ALTER COLUMN {columna} '
                f'TYPE NUMERIC({precision},{escala}) USING {columna}::numeric({precision},{escala})'
            ))
    db.session.commit()


def ensure_schema():
    inspector = inspect(db.engine)
    if inspector.has_table('usuarios'):
        usuario_columns = {column['name'] for column in inspector.get_columns('usuarios')}
        if 'debe_cambiar_password' not in usuario_columns:
            db.session.execute(text(
                'ALTER TABLE usuarios ADD COLUMN debe_cambiar_password BOOLEAN DEFAULT 0 NOT NULL'
            ))
            db.session.commit()
        for nombre_columna in ('puesto', 'gerente_asignado', 'jefe_site_asignado'):
            if nombre_columna not in usuario_columns:
                db.session.execute(text(
                    f'ALTER TABLE usuarios ADD COLUMN {nombre_columna} VARCHAR(100)'
                ))
        if 'permisos_personalizados' not in usuario_columns:
            db.session.execute(text('ALTER TABLE usuarios ADD COLUMN permisos_personalizados TEXT'))
        db.session.execute(text("UPDATE usuarios SET rol = 'Admin' WHERE rol = 'administrador'"))
        db.session.execute(text("UPDATE usuarios SET rol = 'Full' WHERE rol = 'superusuario'"))
        db.session.execute(text("UPDATE usuarios SET rol = 'RMO_OPS' WHERE rol = 'usuario'"))
        db.session.execute(text("UPDATE usuarios SET puesto = 'Administrador' WHERE rol = 'Admin' AND (puesto IS NULL OR puesto = '')"))
        db.session.execute(text("UPDATE usuarios SET puesto = 'Controller' WHERE rol = 'Full' AND (puesto IS NULL OR puesto = '')"))
        db.session.commit()
    if inspector.has_table('ratio_eli_ii_mensual'):
        ratio_ii_columns = {column['name'] for column in inspector.get_columns('ratio_eli_ii_mensual')}
        if 'operaciones_importe' not in ratio_ii_columns:
            db.session.execute(text('ALTER TABLE ratio_eli_ii_mensual ADD COLUMN operaciones_importe NUMERIC(18,2) DEFAULT 0 NOT NULL'))
        if 'staff_importe' not in ratio_ii_columns:
            db.session.execute(text('ALTER TABLE ratio_eli_ii_mensual ADD COLUMN staff_importe NUMERIC(18,2) DEFAULT 0 NOT NULL'))
        db.session.commit()
    asegurar_tipos_proforma_personal()
    inspector = inspect(db.engine)
    asegurar_administrador_inicial_db()
    if not inspector.has_table('facturacion_anio'):
        return

    asignacion_columns = {column['name'] for column in inspector.get_columns('asignaciones_comerciales')} if inspector.has_table('asignaciones_comerciales') else set()
    if asignacion_columns and 'jefe_site' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN jefe_site VARCHAR(100)"))
    if asignacion_columns and 'tipo_negocio' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN tipo_negocio VARCHAR(100)"))
    if asignacion_columns and 'grupo_facturacion' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN grupo_facturacion VARCHAR(100)"))
    if asignacion_columns and 'es_next_gen' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN es_next_gen BOOLEAN DEFAULT 0 NOT NULL"))
    if asignacion_columns and 'vigencia_desde' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN vigencia_desde VARCHAR(7)"))
    if asignacion_columns and 'vigencia_hasta' not in asignacion_columns:
        db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN vigencia_hasta VARCHAR(7)"))
    if inspector.has_table('asignaciones_comerciales'):
        asignacion_columns = {column['name'] for column in inspector.get_columns('asignaciones_comerciales')}
        if 'campania_id' not in asignacion_columns:
            db.session.execute(text("ALTER TABLE asignaciones_comerciales ADD COLUMN campania_id INTEGER"))
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asignaciones_comerciales_campania_id "
            "ON asignaciones_comerciales (campania_id)"
        ))
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asignaciones_comerciales_vigencia_desde "
            "ON asignaciones_comerciales (vigencia_desde)"
        ))
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asignaciones_comerciales_vigencia_hasta "
            "ON asignaciones_comerciales (vigencia_hasta)"
        ))
        db.session.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_asignaciones_comerciales_grupo_facturacion "
            "ON asignaciones_comerciales (grupo_facturacion)"
        ))
        db.session.execute(text("""
            UPDATE asignaciones_comerciales
            SET grupo_facturacion = CASE
                WHEN lower(cliente) LIKE 'personal%' OR lower(campania) LIKE 'personal%' THEN 'Personal'
                WHEN lower(campania) IN ('santander getnet', 'santander getnet onboarding') THEN 'Getnet'
                WHEN lower(cliente) LIKE 'santander%' OR lower(campania) LIKE 'santander%' THEN 'Santander'
                ELSE grupo_facturacion
            END
            WHERE grupo_facturacion IS NULL OR trim(grupo_facturacion) = ''
        """))
        db.session.execute(text("""
            INSERT INTO campanias (cliente, nombre, activa, creado_en)
            SELECT DISTINCT a.cliente, a.campania, 1, CURRENT_TIMESTAMP
            FROM asignaciones_comerciales a
            WHERE a.cliente IS NOT NULL
              AND a.cliente != ''
              AND a.campania IS NOT NULL
              AND a.campania != ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM campanias c
                  WHERE c.cliente = a.cliente AND c.nombre = a.campania
              )
        """))
    if inspector.has_table('campanias'):
        campania_columns = {column['name'] for column in inspector.get_columns('campanias')}
        if 'valor_hora_variable' not in campania_columns:
            db.session.execute(text("ALTER TABLE campanias ADD COLUMN valor_hora_variable BOOLEAN"))
        db.session.execute(text("""
            UPDATE asignaciones_comerciales
            SET campania_id = (
                SELECT c.id
                FROM campanias c
                WHERE c.cliente = asignaciones_comerciales.cliente
                  AND c.nombre = asignaciones_comerciales.campania
                LIMIT 1
            )
            WHERE campania_id IS NULL
        """))
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
    if inspector.has_table('excepciones_calculo'):
        excepcion_columns = {column['name'] for column in inspector.get_columns('excepciones_calculo')}
        if 'ajuste_vh_objetivo_pct' not in excepcion_columns:
            db.session.execute(text("ALTER TABLE excepciones_calculo ADD COLUMN ajuste_vh_objetivo_pct NUMERIC(9,4) DEFAULT 0 NOT NULL"))
        if 'ajuste_vh_alcanzado_pct' not in excepcion_columns:
            db.session.execute(text("ALTER TABLE excepciones_calculo ADD COLUMN ajuste_vh_alcanzado_pct NUMERIC(9,4) DEFAULT 0 NOT NULL"))
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

    if inspector.has_table('matriz_proyecciones'):
        proyeccion_columns = {column['name'] for column in inspector.get_columns('matriz_proyecciones')}
        proyeccion_missing_columns = {
            'carga_semanal': "ALTER TABLE matriz_proyecciones ADD COLUMN carga_semanal VARCHAR(20) DEFAULT 'L a V'",
            'carga_horaria': 'ALTER TABLE matriz_proyecciones ADD COLUMN carga_horaria NUMERIC(12,2) DEFAULT 0',
            'dias_objetivo': 'ALTER TABLE matriz_proyecciones ADD COLUMN dias_objetivo INTEGER DEFAULT 0',
            'tiene_nocturnidad': 'ALTER TABLE matriz_proyecciones ADD COLUMN tiene_nocturnidad BOOLEAN DEFAULT 0',
            'porcentaje_nocturnidad': 'ALTER TABLE matriz_proyecciones ADD COLUMN porcentaje_nocturnidad NUMERIC(9,4) DEFAULT 0',
            'tipo_plp': 'ALTER TABLE matriz_proyecciones ADD COLUMN tipo_plp VARCHAR(30)',
            'horas_carga_manual': 'ALTER TABLE matriz_proyecciones ADD COLUMN horas_carga_manual BOOLEAN DEFAULT 0',
            'dias_objetivo_manual': 'ALTER TABLE matriz_proyecciones ADD COLUMN dias_objetivo_manual INTEGER',
            'horas_requeridas_manual': 'ALTER TABLE matriz_proyecciones ADD COLUMN horas_requeridas_manual NUMERIC(12,2)',
        }
        for column, statement in proyeccion_missing_columns.items():
            if column not in proyeccion_columns:
                db.session.execute(text(statement))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET carga_semanal = 'L a V'
            WHERE carga_semanal IS NULL OR carga_semanal = ''
        """))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET carga_horaria = 0
            WHERE carga_horaria IS NULL
        """))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET dias_objetivo = 0
            WHERE dias_objetivo IS NULL
        """))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET tiene_nocturnidad = 0, porcentaje_nocturnidad = 0
            WHERE tiene_nocturnidad IS NULL OR porcentaje_nocturnidad IS NULL
        """))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET horas_carga_manual = 0
            WHERE horas_carga_manual IS NULL
        """))
        db.session.execute(text("""
            UPDATE matriz_proyecciones
            SET cliente = 'Personal'
            WHERE tipo_plp IS NOT NULL
              AND tipo_plp != ''
              AND cliente != 'Personal'
        """))
        db.session.commit()
        asegurar_distribucion_personal_inicial()

    if inspector.has_table('matriz_precios'):
        precio_columns = {column['name'] for column in inspector.get_columns('matriz_precios')}
        if 'site' not in precio_columns:
            db.session.execute(text("ALTER TABLE matriz_precios ADD COLUMN site VARCHAR(100)"))
        if 'importe_fijo_mensual' not in precio_columns:
            db.session.execute(text("ALTER TABLE matriz_precios ADD COLUMN importe_fijo_mensual NUMERIC(18,2) DEFAULT 0"))
        db.session.execute(text("""
            UPDATE matriz_precios
            SET importe_fijo_mensual = 0
            WHERE importe_fijo_mensual IS NULL
        """))
        if inspector.has_table('asignaciones_comerciales'):
            db.session.execute(text("""
                UPDATE matriz_precios
                SET site = (
                    SELECT COALESCE(a.gerente, a.jefe_site, '')
                    FROM asignaciones_comerciales a
                    WHERE a.activa = TRUE
                      AND a.cliente = matriz_precios.cliente
                      AND a.campania = matriz_precios.campania
                    LIMIT 1
                )
                WHERE site IS NULL OR site = ''
            """))

    if inspector.has_table('sites_proyecciones'):
        site_columns = {column['name'] for column in inspector.get_columns('sites_proyecciones')}
        if 'cliente_destino' not in site_columns:
            db.session.execute(text("ALTER TABLE sites_proyecciones ADD COLUMN cliente_destino VARCHAR(100)"))
        if 'campania_destino' not in site_columns:
            db.session.execute(text("ALTER TABLE sites_proyecciones ADD COLUMN campania_destino VARCHAR(160)"))

    if inspector.has_table('next_gen_productos'):
        next_gen_columns = {column['name'] for column in inspector.get_columns('next_gen_productos')}
        if 'cotizacion_aplicada' not in next_gen_columns:
            db.session.execute(text(
                "ALTER TABLE next_gen_productos ADD COLUMN cotizacion_aplicada NUMERIC(24,10)"
            ))
            db.session.commit()

    columns = {column['name'] for column in inspector.get_columns('facturacion_anio')}
    missing_columns = {
        'gerente': 'ALTER TABLE facturacion_anio ADD COLUMN gerente VARCHAR(100)',
        'jefe_site': 'ALTER TABLE facturacion_anio ADD COLUMN jefe_site VARCHAR(100)',
        'campania': 'ALTER TABLE facturacion_anio ADD COLUMN campania VARCHAR(100)',
        'subcampania': 'ALTER TABLE facturacion_anio ADD COLUMN subcampania VARCHAR(100)',
        'tipo_negocio': 'ALTER TABLE facturacion_anio ADD COLUMN tipo_negocio VARCHAR(100)',
        'es_next_gen': 'ALTER TABLE facturacion_anio ADD COLUMN es_next_gen BOOLEAN DEFAULT 0 NOT NULL',
        'objetivo_separar_ajuste_vh': 'ALTER TABLE facturacion_anio ADD COLUMN objetivo_separar_ajuste_vh BOOLEAN DEFAULT 0 NOT NULL',
        'horas_penalizadas': 'ALTER TABLE facturacion_anio ADD COLUMN horas_penalizadas NUMERIC(12,2) DEFAULT 0',
        'valor_hora_objetivo': 'ALTER TABLE facturacion_anio ADD COLUMN valor_hora_objetivo NUMERIC(18,2)',
        'facturado_horas_manual': 'ALTER TABLE facturacion_anio ADD COLUMN facturado_horas_manual NUMERIC(18,2)',
        'total_facturado_manual': 'ALTER TABLE facturacion_anio ADD COLUMN total_facturado_manual NUMERIC(18,2)',
        'control_facturado_horas': 'ALTER TABLE facturacion_anio ADD COLUMN control_facturado_horas NUMERIC(18,2)',
        'control_variable_productivo': 'ALTER TABLE facturacion_anio ADD COLUMN control_variable_productivo NUMERIC(18,2)',
        'control_penalizaciones_bonos': 'ALTER TABLE facturacion_anio ADD COLUMN control_penalizaciones_bonos NUMERIC(18,2)',
        'control_total_facturado': 'ALTER TABLE facturacion_anio ADD COLUMN control_total_facturado NUMERIC(18,2)',
        'control_objetivo_total': 'ALTER TABLE facturacion_anio ADD COLUMN control_objetivo_total NUMERIC(18,2)',
        'importe_fijo': 'ALTER TABLE facturacion_anio ADD COLUMN importe_fijo NUMERIC(18,2)',
        'variable_objetivo': 'ALTER TABLE facturacion_anio ADD COLUMN variable_objetivo NUMERIC(18,2) DEFAULT 0',
        'variable_productivo': 'ALTER TABLE facturacion_anio ADD COLUMN variable_productivo NUMERIC(18,2) DEFAULT 0',
    }
    for column, statement in missing_columns.items():
        if column not in columns:
            db.session.execute(text(statement))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET jefe_site = 'Sin asignar'
        WHERE jefe_site IS NULL OR jefe_site = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET campania = 'Operacion'
        WHERE campania IS NULL OR campania = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET subcampania = cliente
        WHERE subcampania IS NULL OR subcampania = ''
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET valor_hora_objetivo = valor_hora
        WHERE valor_hora_objetivo IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET horas_penalizadas = 0
        WHERE horas_penalizadas IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET variable_productivo = 0
        WHERE variable_productivo IS NULL
    """))
    db.session.execute(text("""
        UPDATE facturacion_anio
        SET variable_objetivo = 0
        WHERE variable_objetivo IS NULL
    """))
    db.session.execute(text("""
        INSERT INTO asignaciones_comerciales (cliente, gerente, jefe_site, campania, subcampania, tipo_negocio, activa, creado_en)
        SELECT DISTINCT cliente, COALESCE(gerente, 'Sin asignar'), COALESCE(jefe_site, 'Sin asignar'), campania, subcampania, tipo_negocio, 1, CURRENT_TIMESTAMP
        FROM facturacion_anio
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
    if Usuario.query.filter(Usuario.rol.in_(('Admin', 'administrador'))).first():
        return

    primer_usuario = Usuario.query.order_by(Usuario.creado_en.asc(), Usuario.id.asc()).first()
    if not primer_usuario:
        return

    rol_anterior = primer_usuario.rol
    primer_usuario.rol = 'Admin'
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


def asegurar_tipos_proforma_personal():
    """Separa los lotes Masivo, Personal Pay y Soporte sin perder cargas previas."""
    inspector = inspect(db.engine)
    if not inspector.has_table('proforma_personal'):
        return
    columnas = {column['name'] for column in inspector.get_columns('proforma_personal')}
    if 'tipo_proforma' not in columnas:
        db.session.execute(text(
            "ALTER TABLE proforma_personal ADD COLUMN tipo_proforma VARCHAR(30) DEFAULT 'Masivo' NOT NULL"
        ))
        db.session.commit()
    if 'estado_proforma' not in columnas:
        db.session.execute(text(
            "ALTER TABLE proforma_personal ADD COLUMN estado_proforma VARCHAR(20) DEFAULT 'Proyectada' NOT NULL"
        ))
        db.session.commit()
    inspector = inspect(db.engine)
    unicos = inspector.get_unique_constraints('proforma_personal')
    columnas_nuevas = {
        'tipo_proforma', 'fdv', 'periodo', 'negocio', 'sitio_proveedor',
        'segmento', 'subsitio', 'tipo_hora',
    }
    tiene_unico_nuevo = any(set(restriccion.get('column_names') or ()) == columnas_nuevas for restriccion in unicos)
    if db.engine.dialect.name == 'sqlite' and not tiene_unico_nuevo:
        for indice in db.session.execute(text('PRAGMA index_list(proforma_personal)')).mappings():
            if not indice.get('unique'):
                continue
            nombre_indice = str(indice.get('name') or '').replace("'", "''")
            columnas_indice = {
                fila['name'] for fila in db.session.execute(
                    text(f"PRAGMA index_info('{nombre_indice}')")
                ).mappings()
            }
            if columnas_indice == columnas_nuevas:
                tiene_unico_nuevo = True
                break
    if tiene_unico_nuevo:
        db.session.execute(text(
            "UPDATE proforma_personal SET tipo_proforma = 'Masivo' "
            "WHERE tipo_proforma IS NULL OR trim(tipo_proforma) = ''"
        ))
        db.session.execute(text(
            "UPDATE proforma_personal SET estado_proforma = 'Proyectada' "
            "WHERE estado_proforma IS NULL OR trim(estado_proforma) = ''"
        ))
        db.session.commit()
        return

    if db.engine.dialect.name == 'sqlite':
        db.session.execute(text("""
            CREATE TABLE proforma_personal_nueva (
                id INTEGER NOT NULL PRIMARY KEY,
                tipo_proforma VARCHAR(30) DEFAULT 'Masivo' NOT NULL,
                estado_proforma VARCHAR(20) DEFAULT 'Proyectada' NOT NULL,
                fdv VARCHAR(150) NOT NULL,
                periodo VARCHAR(6) NOT NULL,
                negocio VARCHAR(100) NOT NULL,
                sitio_proveedor VARCHAR(100) NOT NULL,
                segmento VARCHAR(150) NOT NULL,
                subsitio VARCHAR(150),
                tipo_hora VARCHAR(50) NOT NULL,
                total_horas NUMERIC(20,10) DEFAULT 0 NOT NULL,
                precio NUMERIC(20,10) DEFAULT 0 NOT NULL,
                monto_fijo NUMERIC(20,10) DEFAULT 0 NOT NULL,
                porcentaje_bono_kpi_vs NUMERIC(15,10) DEFAULT 0 NOT NULL,
                monto_variable_kpi_vs NUMERIC(20,10) DEFAULT 0 NOT NULL,
                porcentaje_bono_ac NUMERIC(15,10) DEFAULT 0 NOT NULL,
                monto_variable_ac NUMERIC(20,10) DEFAULT 0 NOT NULL,
                monto_variable NUMERIC(20,10) DEFAULT 0 NOT NULL,
                total_proyeccion NUMERIC(20,10) DEFAULT 0 NOT NULL,
                bono_porcentaje_total NUMERIC(15,10) DEFAULT 0 NOT NULL,
                archivo_origen VARCHAR(255),
                creado_en DATETIME NOT NULL,
                actualizado_en DATETIME NOT NULL,
                CONSTRAINT uq_proforma_personal_fila_tipo UNIQUE (
                    tipo_proforma, fdv, periodo, negocio, sitio_proveedor,
                    segmento, subsitio, tipo_hora
                )
            )
        """))
        db.session.execute(text("""
            INSERT INTO proforma_personal_nueva (
                id, tipo_proforma, estado_proforma, fdv, periodo, negocio, sitio_proveedor, segmento,
                subsitio, tipo_hora, total_horas, precio, monto_fijo,
                porcentaje_bono_kpi_vs, monto_variable_kpi_vs, porcentaje_bono_ac,
                monto_variable_ac, monto_variable, total_proyeccion,
                bono_porcentaje_total, archivo_origen, creado_en, actualizado_en
            )
            SELECT id, COALESCE(NULLIF(trim(tipo_proforma), ''), 'Masivo'),
                COALESCE(NULLIF(trim(estado_proforma), ''), 'Proyectada'), fdv, periodo,
                negocio, sitio_proveedor, segmento, subsitio, tipo_hora, total_horas,
                precio, monto_fijo, porcentaje_bono_kpi_vs, monto_variable_kpi_vs,
                porcentaje_bono_ac, monto_variable_ac, monto_variable, total_proyeccion,
                bono_porcentaje_total, archivo_origen, creado_en, actualizado_en
            FROM proforma_personal
        """))
        db.session.execute(text('DROP TABLE proforma_personal'))
        db.session.execute(text('ALTER TABLE proforma_personal_nueva RENAME TO proforma_personal'))
        db.session.execute(text('CREATE INDEX ix_proforma_personal_periodo ON proforma_personal (periodo)'))
        db.session.execute(text('CREATE INDEX ix_proforma_personal_tipo_proforma ON proforma_personal (tipo_proforma)'))
        db.session.execute(text('CREATE INDEX ix_proforma_personal_estado_proforma ON proforma_personal (estado_proforma)'))
    else:
        for restriccion in unicos:
            columnas_restriccion = set(restriccion.get('column_names') or ())
            nombre = restriccion.get('name')
            if nombre and columnas_restriccion == columnas_nuevas - {'tipo_proforma'}:
                db.session.execute(text(f'ALTER TABLE proforma_personal DROP CONSTRAINT "{nombre}"'))
        db.session.execute(text("""
            ALTER TABLE proforma_personal
            ADD CONSTRAINT uq_proforma_personal_fila_tipo UNIQUE (
                tipo_proforma, fdv, periodo, negocio, sitio_proveedor,
                segmento, subsitio, tipo_hora
            )
        """))
        db.session.execute(text(
            'CREATE INDEX IF NOT EXISTS ix_proforma_personal_tipo_proforma '
            'ON proforma_personal (tipo_proforma)'
        ))
    db.session.commit()


def asegurar_distribucion_personal_inicial():
    from flask import current_app
    from app.models import PersonalDistribucionHoras, ProyeccionMatriz

    # Esta matriz es una linea base historica. El anio es configurable para que
    # el dato no se confunda con el periodo operativo predeterminado de la app.
    base_year = current_app.config['PLP_BASE_YEAR']

    valores = {
        'Personal CX': [98.16796694772124, 96.11765302091567, 90.08499357215123, 93.08592324475397, 91.12527178069466, 93.75060264177098, 91.39669824176157, 93.81087110649403, 91.99630306566439, 88.76005792692392, 89.80150318528723, 88.70580382605068],
        'Personal': [94.08837911163839, 94.2975562866131, 86.06926288070605, 91.86256843714347, 92.18224768429545, 92.44647182529847, 88.23584619838472, 92.93451439600867, 89.83343814025947, 90.84041720493514, 91.81609953736157, 90.85042955924541],
        'Personal Soporte': [79.46650447358854, 80.4847455095552, 71.14105709600506, 71.25708060209251, 82.69712955112763, 69.38766319665987, 65.47509735717676, 65.73781910354595, 68.50213925809712, 76.54533345298616, 78.59332882295669, 67.11558415411434],
        'Personal SMB': [97.19048607720376, 97.22019802994073, 96.61545016353689, 96.45611517854402, 94.69738664033223, 97.81764486445577, 91.16740061359158, 91.80295034769298, 91.92734071504796, 91.92734178359599, 91.92734152924741, 91.92734327010287],
    }
    existentes = {
        (fila.servicio, fila.mes)
        for fila in PersonalDistribucionHoras.query.filter_by(year=base_year).all()
    }
    agregados = False
    for servicio, porcentajes in valores.items():
        for numero_mes, porcentaje in enumerate(porcentajes, start=1):
            mes = f'{base_year}-{numero_mes:02d}'
            if (servicio, mes) in existentes:
                continue
            db.session.add(PersonalDistribucionHoras(
                servicio=servicio,
                year=base_year,
                mes=mes,
                porcentaje_diurno=porcentaje,
            ))
            agregados = True
    configuraciones = {
        (fila.servicio.casefold(), fila.mes): fila
        for fila in PersonalDistribucionHoras.query.all()
    }
    actualizados = False
    nombres = {nombre.casefold(): nombre for nombre in valores}
    for proyeccion in ProyeccionMatriz.query.all():
        servicio = nombres.get((proyeccion.tipo_plp or '').strip().casefold()) or nombres.get((proyeccion.campania or '').strip().casefold()) or nombres.get((proyeccion.cliente or '').strip().casefold())
        if not servicio:
            continue
        distribucion = configuraciones.get((servicio.casefold(), proyeccion.mes))
        porcentaje_nocturno = distribucion.porcentaje_nocturno if distribucion else 0
        if proyeccion.porcentaje_nocturnidad != porcentaje_nocturno or proyeccion.tiene_nocturnidad != (porcentaje_nocturno > 0):
            proyeccion.porcentaje_nocturnidad = porcentaje_nocturno
            proyeccion.tiene_nocturnidad = porcentaje_nocturno > 0
            actualizados = True
    if agregados or actualizados:
        db.session.commit()
