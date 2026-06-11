# filepath: app/routes.py
from flask import Blueprint, Response, current_app, redirect, render_template, request, jsonify, session, url_for
from app import db, get_csrf_token
from app.models import AsignacionComercial, Facturacion2026, FeriadoOperativo, HistorialCambio, JustificacionAjuste, ProyeccionMatriz, ProyeccionMatrizJornada, ProyeccionPrecio, ROLES_USUARIO, Usuario, VariableCampania, redondear_moneda
from datetime import date, datetime, timedelta
import calendar
from sqlalchemy import func
from html import escape
from html.parser import HTMLParser
from functools import wraps
import csv
import io
import json
import os
import time
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

main_bp = Blueprint('main', __name__)
ADMIN_KEY = os.getenv('ADMIN_ACTION_KEY')
CLAVE_PRUEBA_ACCIONES = os.getenv('DEV_ACTION_KEY')
LOGIN_ATTEMPTS = {}
LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', '900'))
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
TIPO_VH_PERSONAL_COBRANZAS = 'Personal Cobranzas'
TIPOS_VH = [
    'Diurna',
    'Nocturna',
    'Feriado',
    'Capacitación',
    'Diurnas Feriado',
    'Nocturnas Feriado',
    'horas líder',
    'radio',
    TIPO_VH_PERSONAL_COBRANZAS,
]

COLUMNAS_IMPORTACION = [
    ('fecha', 'Fecha de carga'),
    ('mes', 'Mes facturacion'),
    ('cliente', 'Cliente'),
    ('gerente', 'Gerente'),
    ('jefe_site', 'Jefe de Site'),
    ('campania', 'Campaña'),
    ('subcampania', 'Sub campaña'),
    ('tipo_negocio', 'Tipo de negocio'),
    ('tipo_jornada', 'Tipo de VH'),
    ('horas_objetivo', 'Horas objetivo'),
    ('horas_facturadas', 'Horas facturadas'),
    ('horas_penalizadas', 'Horas Penalizacion ADH'),
    ('valor_hora_objetivo', 'Valor hora objetivo'),
    ('valor_hora', 'Valor hora facturado'),
    ('tarifacion', 'Tarificacion'),
    ('importe_fijo', 'Importe fijo facturado'),
    ('variable_objetivo', 'Variable Objetivo'),
    ('variable_productivo', 'Variable Productivo'),
    ('bonos', 'Bonos'),
    ('penalizaciones', 'Penalizaciones'),
    ('netx_gen', 'Next Gen'),
    ('otros', 'Otros'),
]

ALIAS_IMPORTACION = {
    'fecha': 'fecha',
    'fecha de carga': 'fecha',
    'mes': 'mes',
    'mes facturacion': 'mes',
    'mes facturación': 'mes',
    'cliente': 'cliente',
    'gerente': 'gerente',
    'jefe de site': 'jefe_site',
    'jefe_site': 'jefe_site',
    'campana': 'campania',
    'campaña': 'campania',
    'campania': 'campania',
    'sub campana': 'subcampania',
    'sub campaña': 'subcampania',
    'subcampania': 'subcampania',
    'tipo negocio': 'tipo_negocio',
    'tipo de negocio': 'tipo_negocio',
    'tipo_negocio': 'tipo_negocio',
    'negocio': 'tipo_negocio',
    'tipo de vh': 'tipo_jornada',
    'tipo vh': 'tipo_jornada',
    'tipo_jornada': 'tipo_jornada',
    'horas objetivo': 'horas_objetivo',
    'horas_objetivo': 'horas_objetivo',
    'horas facturadas': 'horas_facturadas',
    'horas_facturadas': 'horas_facturadas',
    'horas penalizadas': 'horas_penalizadas',
    'horas penalizacion adh': 'horas_penalizadas',
    'horas penalización adh': 'horas_penalizadas',
    'penalizacion adh horas': 'horas_penalizadas',
    'penalización adh horas': 'horas_penalizadas',
    'horas_penalizadas': 'horas_penalizadas',
    'valor hora objetivo': 'valor_hora_objetivo',
    'valor_hora_objetivo': 'valor_hora_objetivo',
    'valor hora facturado': 'valor_hora',
    'valor hora': 'valor_hora',
    'valor_hora': 'valor_hora',
    'tarifacion': 'tarifacion',
    'tarificacion': 'tarifacion',
    'tarifacion adicional': 'tarifacion',
    'tarificacion adicional': 'tarifacion',
    'importe fijo': 'importe_fijo',
    'importe fijo facturado': 'importe_fijo',
    'tarifa plana': 'importe_fijo',
    'facturacion fija': 'importe_fijo',
    'variable objetivo': 'variable_objetivo',
    'variable_objetivo': 'variable_objetivo',
    'bono objetivo': 'variable_objetivo',
    'variable productivo': 'variable_productivo',
    'variable_productivo': 'variable_productivo',
    'tarifación': 'tarifacion',
    'bonos': 'bonos',
    'bono': 'bonos',
    'facturado bono': 'bonos',
    'penalizaciones': 'penalizaciones',
    'penalizacion': 'penalizaciones',
    'penalizaciones bonos': 'penalizaciones',
    'penalizaciones/bonos': 'penalizaciones',
    'penalizaciones por incumplimientos': 'penalizaciones',
    'penalizacion por incumplimientos': 'penalizaciones',
    'netx gen': 'netx_gen',
    'next gen': 'netx_gen',
    'netx_gen': 'netx_gen',
    'otros': 'otros',
}

class TablaHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.current_cell = []
            self.in_cell = True

    def handle_data(self, data):
        if self.in_cell and self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            self.current_row.append(''.join(self.current_cell).strip())
            self.current_cell = None
            self.in_cell = False
        elif tag == 'tr' and self.current_row is not None:
            if any(cell for cell in self.current_row):
                self.rows.append(self.current_row)
            self.current_row = None


def crear_xlsx(headers, rows):
    def columna_excel(indice):
        nombre = ''
        indice += 1
        while indice:
            indice, resto = divmod(indice - 1, 26)
            nombre = chr(65 + resto) + nombre
        return nombre

    def fila_xml(valores, numero):
        celdas = []
        for indice, valor in enumerate(valores):
            referencia = f'{columna_excel(indice)}{numero}'
            texto = xml_escape(str(valor if valor is not None else ''))
            celdas.append(f'<c r="{referencia}" t="inlineStr"><is><t>{texto}</t></is></c>')
        return f'<row r="{numero}">' + ''.join(celdas) + '</row>'

    filas_xml = [fila_xml(headers, 1)]
    filas_xml.extend(fila_xml(row, numero) for numero, row in enumerate(rows, start=2))
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + ''.join(filas_xml) + '</sheetData></worksheet>'
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ))
        archivo.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ))
        archivo.writestr('xl/workbook.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Carga" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ))
        archivo.writestr('xl/_rels/workbook.xml.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ))
        archivo.writestr('xl/worksheets/sheet1.xml', sheet_xml)
    output.seek(0)
    return output.getvalue()


def validar_clave(data):
    clave = str((data or {}).get('clave') or '')
    return requiere_edicion() or (ADMIN_KEY and clave == ADMIN_KEY)


def validar_confirmacion_accion(data):
    data = data or {}
    usuario = usuario_actual()
    password = str(data.get('password_confirmacion') or '')
    clave = str(data.get('clave') or '')
    if usuario and password and usuario.check_password(password):
        return True
    if current_app.debug and CLAVE_PRUEBA_ACCIONES and clave == CLAVE_PRUEBA_ACCIONES:
        return True
    return False


def serializar_json(valor):
    return json.dumps(valor, ensure_ascii=False, default=str)


def snapshot_modelo(modelo):
    if hasattr(modelo, 'to_dict'):
        return modelo.to_dict()
    return {}


def cambios_entre(antes, despues):
    cambios = {}
    for clave in sorted(set(antes) | set(despues)):
        if clave == 'justificaciones':
            continue
        valor_antes = antes.get(clave)
        valor_despues = despues.get(clave)
        if valor_antes != valor_despues:
            cambios[clave] = {'antes': valor_antes, 'despues': valor_despues}
    return cambios


def registrar_historial(accion, entidad, entidad_id, resumen, antes=None, despues=None, detalle=None):
    usuario = usuario_actual()
    item = HistorialCambio(
        usuario_id=usuario.id if usuario else None,
        usuario_nombre=usuario.nombre if usuario else 'Sistema',
        usuario_email=usuario.email if usuario else None,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        resumen=resumen,
        detalle=detalle,
        antes=serializar_json(antes) if antes is not None else None,
        despues=serializar_json(despues) if despues is not None else None,
    )
    db.session.add(item)
    return item


def usuario_actual():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return None
    return Usuario.query.get(usuario_id)


def usuario_actual_dict():
    usuario = usuario_actual()
    return usuario.to_dict() if usuario else None


def requiere_login():
    usuario = usuario_actual()
    return usuario is not None and usuario.activo


def requiere_admin():
    usuario = usuario_actual()
    return usuario is not None and usuario.activo and usuario.es_administrador


def requiere_edicion():
    usuario = usuario_actual()
    return usuario is not None and usuario.activo and usuario.puede_editar


def requiere_eliminacion():
    usuario = usuario_actual()
    return usuario is not None and usuario.activo and usuario.puede_eliminar


def respuesta_no_autorizado():
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'errores': ['No autorizado']}), 403
    if requiere_login():
        return redirect(url_for('main.index'))
    return redirect(url_for('main.login'))


def login_requerido(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not usuarios_registrados():
            return respuesta_no_autorizado()
        if not requiere_login():
            return respuesta_no_autorizado()
        return func(*args, **kwargs)
    return wrapper


def permiso_requerido(verificador):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not usuarios_registrados():
                return respuesta_no_autorizado()
            if not verificador():
                return respuesta_no_autorizado()
            return func(*args, **kwargs)
        return wrapper
    return decorator


admin_requerido = permiso_requerido(requiere_admin)
edicion_requerida = permiso_requerido(requiere_edicion)
eliminacion_requerida = permiso_requerido(requiere_eliminacion)


def usuarios_registrados():
    return Usuario.query.count() > 0


def asegurar_administrador_inicial():
    """Promueve el primer usuario existente a administrador si aun no hay admin."""
    if not usuarios_registrados():
        return None
    if Usuario.query.filter_by(rol='administrador').first():
        return None
    primer_usuario = Usuario.query.order_by(Usuario.creado_en.asc(), Usuario.id.asc()).first()
    if primer_usuario:
        rol_anterior = primer_usuario.rol
        primer_usuario.rol = 'administrador'
        registrar_historial(
            'edicion',
            'usuario',
            primer_usuario.id,
            f'Usuario inicial promovido a administrador: {primer_usuario.email}',
            antes={'rol': rol_anterior},
            despues={'rol': 'administrador'},
        )
        db.session.commit()
    return primer_usuario


def normalizar_email(email):
    return str(email or '').strip().lower()


def login_rate_key(email):
    forwarded = request.headers.get('X-Forwarded-For', '')
    ip = forwarded.split(',')[0].strip() or request.remote_addr or 'unknown'
    return f'{ip}:{normalizar_email(email)}'


def login_bloqueado(email):
    key = login_rate_key(email)
    now = time.time()
    attempts = [item for item in LOGIN_ATTEMPTS.get(key, []) if now - item < LOGIN_WINDOW_SECONDS]
    LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def registrar_login_fallido(email):
    key = login_rate_key(email)
    now = time.time()
    attempts = [item for item in LOGIN_ATTEMPTS.get(key, []) if now - item < LOGIN_WINDOW_SECONDS]
    attempts.append(now)
    LOGIN_ATTEMPTS[key] = attempts


def limpiar_login_fallido(email):
    LOGIN_ATTEMPTS.pop(login_rate_key(email), None)


def validar_usuario_payload(data, require_password=False):
    errores = []
    nombre = str(data.get('nombre', '')).strip()
    email = normalizar_email(data.get('email'))
    password = str(data.get('password', '') or '')
    rol = str(data.get('rol', 'usuario')).strip()

    if not nombre:
        errores.append('El nombre es obligatorio')
    if not email or '@' not in email:
        errores.append('El email es obligatorio y debe ser valido')
    if require_password and len(password) < 12:
        errores.append('La contrasena debe tener al menos 12 caracteres')
    if require_password and password and (
        password.lower() == password
        or password.upper() == password
        or not any(caracter.isdigit() for caracter in password)
    ):
        errores.append('La contrasena debe combinar mayusculas, minusculas y numeros')
    if rol not in ROLES_USUARIO:
        errores.append('El rol no es valido')
    return errores


def filtrar_valores_exactos(query, columna, valores):
    if isinstance(valores, list):
        return query.filter(columna.in_(valores))
    return query.filter(columna == valores)


def aplicar_filtros(
    query,
    mes=None,
    cliente=None,
    gerente=None,
    jefe_site=None,
    campania=None,
    subcampania=None,
    tipo_negocio=None,
    horas_objetivo_min=None,
    horas_objetivo_max=None,
    horas_facturadas_min=None,
    horas_facturadas_max=None,
):
    if mes:
        if isinstance(mes, list):
            query = query.filter(Facturacion2026.mes.in_(mes))
        else:
            query = query.filter(Facturacion2026.mes == mes)
    if cliente:
        query = filtrar_valores_exactos(query, Facturacion2026.cliente, cliente)
    if gerente:
        query = filtrar_valores_exactos(query, Facturacion2026.gerente, gerente)
    if jefe_site:
        query = filtrar_valores_exactos(query, Facturacion2026.jefe_site, jefe_site)
    if campania:
        query = filtrar_valores_exactos(query, Facturacion2026.campania, campania)
    if subcampania:
        query = filtrar_valores_exactos(query, Facturacion2026.subcampania, subcampania)
    if tipo_negocio:
        query = filtrar_valores_exactos(query, Facturacion2026.tipo_negocio, tipo_negocio)
    if horas_objetivo_min is not None:
        query = query.filter(Facturacion2026.horas_objetivo >= horas_objetivo_min)
    if horas_objetivo_max is not None:
        query = query.filter(Facturacion2026.horas_objetivo <= horas_objetivo_max)
    if horas_facturadas_min is not None:
        query = query.filter(Facturacion2026.horas_facturadas >= horas_facturadas_min)
    if horas_facturadas_max is not None:
        query = query.filter(Facturacion2026.horas_facturadas <= horas_facturadas_max)
    return query


def numero_request(nombre):
    valor = request.args.get(nombre)
    if valor in (None, ''):
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def mes_valido(valor):
    if not valor:
        return None
    texto = str(valor).strip()
    if texto.replace('.', '', 1).isdigit():
        return fecha_excel(float(texto)).strftime('%Y-%m')
    try:
        return datetime.strptime(texto, '%Y-%m').strftime('%Y-%m')
    except ValueError:
        pass
    for formato in ('%m/%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(texto, formato).strftime('%Y-%m')
        except ValueError:
            continue
    return None


def normalizar_header(valor):
    texto = str(valor or '').strip().lower().replace('_', ' ')
    texto = ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )
    return ' '.join(texto.split())


def normalizar_tipo_vh(valor):
    texto = str(valor or '').strip()
    if normalizar_header(texto) == 'personal cobranzas':
        return TIPO_VH_PERSONAL_COBRANZAS
    return texto


def es_personal_cobranzas(data):
    return normalizar_tipo_vh(data.get('tipo_jornada')) == TIPO_VH_PERSONAL_COBRANZAS


def resolver_header(valor):
    normalizado = normalizar_header(valor)
    if normalizado in ALIAS_IMPORTACION:
        return ALIAS_IMPORTACION[normalizado]
    if 'camp' in normalizado and 'sub' in normalizado:
        return 'subcampania'
    if 'camp' in normalizado:
        return 'campania'
    if 'jefe' in normalizado and 'site' in normalizado:
        return 'jefe_site'
    return None


def parse_numero(valor):
    if valor in (None, ''):
        return 0
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return 0

    negativo = False
    if texto.startswith('(') and texto.endswith(')'):
        negativo = True
        texto = texto[1:-1]

    texto = texto.replace('\xa0', '').replace(' ', '')
    for simbolo in ('$', '€', '£', 'ARS', 'USD'):
        texto = texto.replace(simbolo, '')
        texto = texto.replace(simbolo.lower(), '')
    texto = texto.replace("'", '')

    if texto.startswith('-'):
        negativo = True
        texto = texto[1:]
    elif texto.endswith('-'):
        negativo = True
        texto = texto[:-1]

    if not texto:
        return 0

    ultimo_punto = texto.rfind('.')
    ultima_coma = texto.rfind(',')
    if ultimo_punto != -1 and ultima_coma != -1:
        separador_decimal = '.' if ultimo_punto > ultima_coma else ','
        separador_miles = ',' if separador_decimal == '.' else '.'
        texto = texto.replace(separador_miles, '')
        texto = texto.replace(separador_decimal, '.')
    elif ultima_coma != -1:
        partes = texto.split(',')
        if len(partes) == 2 and len(partes[-1]) == 3 and len(partes[0]) <= 3:
            texto = ''.join(partes)
        elif len(partes[-1]) in (1, 2, 3):
            texto = ''.join(partes[:-1]).replace('.', '') + '.' + partes[-1]
        else:
            texto = ''.join(partes)
    elif ultimo_punto != -1:
        partes = texto.split('.')
        if len(partes) > 2 and len(partes[-1]) == 3:
            texto = ''.join(partes)
        elif len(partes) > 2:
            texto = ''.join(partes[:-1]) + '.' + partes[-1]
        elif len(partes) == 2 and len(partes[-1]) == 3 and len(partes[0]) <= 3:
            texto = ''.join(partes)

    numero = float(texto)
    if negativo:
        numero *= -1
    return numero


def fecha_excel(valor):
    return (datetime(1899, 12, 30) + timedelta(days=float(valor))).date()


def parse_fecha(valor):
    texto = str(valor or '').strip()
    if texto.replace('.', '', 1).isdigit():
        return fecha_excel(float(texto))
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError('Fecha invalida. Use YYYY-MM-DD o DD/MM/YYYY')


def crear_registro_facturacion(data):
    fecha = parse_fecha(data['fecha'])
    mes = mes_valido(data.get('mes'))
    if not mes:
        raise ValueError('El mes de facturacion no es valido')

    registro = Facturacion2026(
        fecha=fecha,
        mes=mes,
        cliente=data['cliente'].strip(),
        gerente=data.get('gerente', '').strip(),
        jefe_site=data.get('jefe_site', '').strip(),
        campania=data.get('campania', '').strip(),
        subcampania=data.get('subcampania', '').strip(),
        tipo_negocio=str(data.get('tipo_negocio') or '').strip() or None,
        tipo_jornada=normalizar_tipo_vh(data['tipo_jornada']),
        horas_objetivo=parse_numero(data.get('horas_objetivo')),
        horas_facturadas=parse_numero(data.get('horas_facturadas')),
        horas_penalizadas=parse_numero(data.get('horas_penalizadas')),
        valor_hora_objetivo=parse_numero(data.get('valor_hora_objetivo') or data.get('valor_hora')),
        valor_hora=parse_numero(data.get('valor_hora')),
        tarifacion=parse_numero(data.get('tarifacion')) if data.get('tarifacion') not in (None, '') else None,
        importe_fijo=parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None,
        variable_objetivo=parse_numero(data.get('variable_objetivo')),
        variable_productivo=parse_numero(data.get('variable_productivo')),
        bonos=parse_numero(data.get('bonos')),
        penalizaciones=normalizar_importe_ajuste('penalizaciones', data.get('penalizaciones')),
        netx_gen=parse_numero(data.get('netx_gen')),
        otros=parse_numero(data.get('otros')),
    )
    db.session.add(registro)
    guardar_justificaciones(registro, data)
    asegurar_asignacion_desde_registro(registro)
    return registro


def actualizar_registro_facturacion(registro, data):
    fecha = parse_fecha(data['fecha'])
    mes = mes_valido(data.get('mes'))
    if not mes:
        raise ValueError('El mes de facturacion no es valido')

    registro.fecha = fecha
    registro.mes = mes
    registro.cliente = data['cliente'].strip()
    registro.gerente = data.get('gerente', '').strip()
    registro.jefe_site = data.get('jefe_site', '').strip()
    registro.campania = data.get('campania', '').strip()
    registro.subcampania = data.get('subcampania', '').strip()
    registro.tipo_negocio = str(data.get('tipo_negocio') or '').strip() or None
    registro.tipo_jornada = normalizar_tipo_vh(data['tipo_jornada'])
    registro.horas_objetivo = parse_numero(data.get('horas_objetivo'))
    registro.horas_facturadas = parse_numero(data.get('horas_facturadas'))
    registro.horas_penalizadas = parse_numero(data.get('horas_penalizadas'))
    registro.valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo') or data.get('valor_hora'))
    registro.valor_hora = parse_numero(data.get('valor_hora'))
    registro.tarifacion = parse_numero(data.get('tarifacion')) if data.get('tarifacion') not in (None, '') else None
    registro.importe_fijo = parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None
    registro.variable_objetivo = parse_numero(data.get('variable_objetivo'))
    registro.variable_productivo = parse_numero(data.get('variable_productivo'))
    registro.bonos = parse_numero(data.get('bonos'))
    registro.penalizaciones = normalizar_importe_ajuste('penalizaciones', data.get('penalizaciones'))
    registro.netx_gen = parse_numero(data.get('netx_gen'))
    registro.otros = parse_numero(data.get('otros'))
    guardar_justificaciones(registro, data)
    asegurar_asignacion_desde_registro(registro)
    return registro


def query_reemplazo_importacion(data):
    fecha = parse_fecha(data['fecha'])
    return Facturacion2026.query.filter(
        Facturacion2026.fecha == fecha,
        Facturacion2026.cliente == data['cliente'].strip(),
        Facturacion2026.gerente == data.get('gerente', '').strip(),
        Facturacion2026.jefe_site == data.get('jefe_site', '').strip(),
        Facturacion2026.campania == data.get('campania', '').strip(),
        Facturacion2026.subcampania == data.get('subcampania', '').strip(),
    )


def clave_reemplazo_importacion(data):
    fecha = parse_fecha(data['fecha']).isoformat()
    return '|'.join([
        fecha,
        data['cliente'].strip(),
        data.get('gerente', '').strip(),
        data.get('jefe_site', '').strip(),
        data.get('campania', '').strip(),
        data.get('subcampania', '').strip(),
    ])


def detalle_conflicto_importacion(indice, item, existentes):
    return {
        'fila': indice,
        'fecha': parse_fecha(item['fecha']).isoformat(),
        'mes': mes_valido(item.get('mes')),
        'cliente': item['cliente'].strip(),
        'gerente': item.get('gerente', '').strip(),
        'jefe_site': item.get('jefe_site', '').strip(),
        'campania': item.get('campania', '').strip(),
        'subcampania': item.get('subcampania', '').strip(),
        'tipo_negocio': str(item.get('tipo_negocio') or '').strip(),
        'existentes': [registro.id for registro in existentes],
    }


def filas_desde_csv(contenido):
    muestra = contenido[:2048]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=';,|\t,')
    except csv.Error:
        dialecto = csv.excel
        dialecto.delimiter = ';'
    return list(csv.reader(io.StringIO(contenido), dialecto))


def decodificar_texto_importacion(contenido_bytes):
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return contenido_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return contenido_bytes.decode('utf-8-sig', errors='replace')


def filas_desde_html(contenido):
    parser = TablaHTMLParser()
    parser.feed(contenido)
    return parser.rows


def indice_columna(celda_ref):
    letras = ''.join(caracter for caracter in celda_ref if caracter.isalpha())
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra.upper()) - ord('A') + 1)
    return indice - 1


def filas_desde_xlsx(contenido_bytes):
    ns = {
        'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    }
    with zipfile.ZipFile(io.BytesIO(contenido_bytes)) as archivo:
        shared_strings = []
        if 'xl/sharedStrings.xml' in archivo.namelist():
            root = ET.fromstring(archivo.read('xl/sharedStrings.xml'))
            for item in root.findall('main:si', ns):
                textos = [nodo.text or '' for nodo in item.findall('.//main:t', ns)]
                shared_strings.append(''.join(textos))

        sheet_path = 'xl/worksheets/sheet1.xml'
        if 'xl/workbook.xml' in archivo.namelist() and 'xl/_rels/workbook.xml.rels' in archivo.namelist():
            workbook = ET.fromstring(archivo.read('xl/workbook.xml'))
            rels = ET.fromstring(archivo.read('xl/_rels/workbook.xml.rels'))
            first_sheet = workbook.find('main:sheets/main:sheet', ns)
            if first_sheet is not None:
                rel_id = first_sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                for rel in rels.findall('rel:Relationship', ns):
                    if rel.attrib.get('Id') == rel_id:
                        target = rel.attrib.get('Target', 'worksheets/sheet1.xml')
                        sheet_path = 'xl/' + target.lstrip('/')
                        break

        sheet = ET.fromstring(archivo.read(sheet_path))
        filas = []
        for row in sheet.findall('.//main:row', ns):
            valores = []
            for cell in row.findall('main:c', ns):
                ref = cell.attrib.get('r', '')
                indice = indice_columna(ref) if ref else len(valores)
                while len(valores) <= indice:
                    valores.append('')

                tipo = cell.attrib.get('t')
                valor = ''
                if tipo == 'inlineStr':
                    textos = [nodo.text or '' for nodo in cell.findall('.//main:t', ns)]
                    valor = ''.join(textos)
                else:
                    value_node = cell.find('main:v', ns)
                    if value_node is not None:
                        valor = value_node.text or ''
                        if tipo == 's':
                            valor = shared_strings[int(valor)] if valor.isdigit() and int(valor) < len(shared_strings) else ''
                valores[indice] = valor
            if any(str(valor).strip() for valor in valores):
                filas.append(valores)
        return filas


def datos_desde_filas(filas):
    if not filas:
        return []
    headers = [resolver_header(header) for header in filas[0]]
    datos = []
    for fila in filas[1:]:
        if not any(str(celda).strip() for celda in fila):
            continue
        item = {}
        for indice, valor in enumerate(fila):
            if indice < len(headers) and headers[indice]:
                item[headers[indice]] = valor.strip() if isinstance(valor, str) else valor
        datos.append(item)
    return datos


def valores_request(nombre):
    valores = request.args.getlist(nombre)
    if not valores:
        valor = request.args.get(nombre)
        valores = valor.split(',') if valor else []
    valores = [valor.strip() for valor in valores if valor and valor.strip()]
    if not valores:
        return None
    return valores if len(valores) > 1 else valores[0]


def filtros_request():
    return {
        'mes': valores_request('mes'),
        'cliente': valores_request('cliente'),
        'gerente': valores_request('gerente'),
        'jefe_site': valores_request('jefe_site'),
        'campania': valores_request('campania'),
        'subcampania': valores_request('subcampania'),
        'tipo_negocio': valores_request('tipo_negocio'),
    }


def opciones_filtro(filtros, campo):
    filtros_base = dict(filtros)
    filtros_base[campo] = None
    registros = aplicar_filtros(Facturacion2026.query, **filtros_base).all()
    return sorted({
        getattr(registro, campo)
        for registro in registros
        if getattr(registro, campo, None)
    })


def filtros_comparativo_request():
    return {
        **filtros_request(),
        'horas_objetivo_min': numero_request('horas_objetivo_min'),
        'horas_objetivo_max': numero_request('horas_objetivo_max'),
        'horas_facturadas_min': numero_request('horas_facturadas_min'),
        'horas_facturadas_max': numero_request('horas_facturadas_max'),
    }


def registros_filtrados():
    filtros = filtros_request()
    return aplicar_filtros(Facturacion2026.query, **filtros).all()


def filtros_asignacion(asignacion):
    return {
        'cliente': asignacion.cliente,
        'gerente': asignacion.gerente,
        'jefe_site': asignacion.jefe_site,
        'campania': asignacion.campania,
        'subcampania': asignacion.subcampania,
        'tipo_negocio': asignacion.tipo_negocio,
    }


def query_por_asignacion(asignacion):
    return Facturacion2026.query.filter_by(**filtros_asignacion(asignacion))


TIPOS_JUSTIFICACION = {
    'bonos': 'Bonos',
    'penalizaciones': 'Penalizaciones',
    'otros': 'Otros',
}


def normalizar_importe_ajuste(tipo, importe):
    valor = parse_numero(importe)
    if tipo == 'penalizaciones':
        return -abs(valor) if valor else 0
    return valor


def normalizar_justificaciones(data):
    items = data.get('justificaciones') or []
    salida = []
    for item in items:
        tipo = str(item.get('tipo', '')).strip()
        descripcion = str(item.get('descripcion', '')).strip()
        cantidad = parse_numero(item.get('cantidad')) if item.get('cantidad') not in (None, '') else 0
        precio = parse_numero(item.get('precio')) if item.get('precio') not in (None, '') else 0
        importe_base = parse_numero(item.get('importe')) if item.get('importe') not in (None, '') else cantidad * precio
        importe = normalizar_importe_ajuste(tipo, importe_base)
        if not tipo and not descripcion and cantidad == 0 and precio == 0 and importe == 0:
            continue
        salida.append({
            'tipo': tipo,
            'descripcion': descripcion,
            'cantidad': cantidad,
            'precio': precio,
            'importe': importe,
        })
    return salida


def validar_justificaciones(data):
    errores = []
    items = normalizar_justificaciones(data)
    if 'justificaciones' not in data and not items:
        return errores
    totales = {tipo: 0 for tipo in TIPOS_JUSTIFICACION}
    if not items:
        for tipo, label in TIPOS_JUSTIFICACION.items():
            if abs(normalizar_importe_ajuste(tipo, data.get(tipo))) > 0:
                errores.append(f'{label} requiere al menos una justificacion')
        return errores

    for indice, item in enumerate(items, start=1):
        if item['tipo'] not in TIPOS_JUSTIFICACION:
            errores.append(f'Justificacion {indice}: tipo invalido')
            continue
        if item['cantidad'] <= 0:
            errores.append(f'Justificacion {indice}: la cantidad debe ser mayor a 0')
        if item['precio'] <= 0:
            errores.append(f'Justificacion {indice}: el precio debe ser mayor a 0')
        importe_absoluto = abs(item['importe'])
        if importe_absoluto <= 0:
            errores.append(f'Justificacion {indice}: el importe debe ser mayor a 0')
        if abs(importe_absoluto - (item['cantidad'] * item['precio'])) > 0.01:
            errores.append(f'Justificacion {indice}: el importe debe coincidir con cantidad por precio')
        if not item['descripcion']:
            errores.append(f'Justificacion {indice}: la descripcion es obligatoria')
        totales[item['tipo']] += item['importe']

    for tipo, label in TIPOS_JUSTIFICACION.items():
        valor_campo = normalizar_importe_ajuste(tipo, data.get(tipo))
        if abs(valor_campo) > 0 and totales[tipo] == 0:
            errores.append(f'{label} requiere al menos una justificacion')
        if abs(totales[tipo] - valor_campo) > 0.01:
            errores.append(f'La suma de justificaciones de {label} debe coincidir con el importe cargado')

    return errores


def guardar_justificaciones(registro, data):
    registro.justificaciones.clear()
    for item in normalizar_justificaciones(data):
        registro.justificaciones.append(JustificacionAjuste(
            tipo=item['tipo'],
            cantidad=item['cantidad'],
            precio=item['precio'],
            importe=item['importe'],
            descripcion=item['descripcion'],
        ))


def resumen_registros(registros):
    total_real = sum(r.total_real for r in registros)
    total_teorico = sum(r.total_teorico for r in registros)
    facturado_horas = sum(r.facturado_horas for r in registros)
    objetivo_horas = sum(r.objetivo_facturacion_horas for r in registros)
    desvio_facturacion = facturado_horas - objetivo_horas
    desvio = total_real - total_teorico
    porcentaje = (total_real / total_teorico * 100) if total_teorico > 0 else 0
    porcentaje_facturacion = (facturado_horas / objetivo_horas * 100) if objetivo_horas > 0 else 0
    return {
        'horas_objetivo': round(sum(r.horas_objetivo for r in registros), 2),
        'horas_facturadas': round(sum(r.horas_facturadas for r in registros), 2),
        'horas_penalizadas': round(sum(r.horas_penalizadas or 0 for r in registros), 2),
        'bonos': round(sum(r.bonos or 0 for r in registros), 2),
        'variable_objetivo': round(sum(r.variable_objetivo or 0 for r in registros), 2),
        'variable_productivo': round(sum(r.variable_productivo_calculo for r in registros), 2),
        'penalizaciones': round(sum(r.penalizaciones_incumplimientos for r in registros), 2),
        'netx_gen': round(sum(r.netx_gen or 0 for r in registros), 2),
        'otros': round(sum(r.otros or 0 for r in registros), 2),
        'tarifacion': round(sum(r.tarifacion or 0 for r in registros), 2),
        'facturado_horas': round(facturado_horas, 2),
        'objetivo_facturacion_horas': round(objetivo_horas, 2),
        'desvio_facturacion': round(desvio_facturacion, 2),
        'porcentaje_cumplimiento_facturacion': round(porcentaje_facturacion, 2),
        'total_real': round(total_real, 2),
        'total_teorico': round(total_teorico, 2),
        'desvio': round(desvio, 2),
        'porcentaje_cumplimiento': round(porcentaje, 2)
    }


def resumen_dashboard(registros):
    resumen = resumen_registros(registros)
    total_facturado = sum(r.total_dashboard for r in registros)
    total_teorico = sum(r.total_teorico for r in registros)
    desvio = total_facturado - total_teorico
    porcentaje = (total_facturado / total_teorico * 100) if total_teorico > 0 else 0
    horas_objetivo = sum(r.horas_objetivo or 0 for r in registros)
    horas_facturadas = sum(r.horas_facturadas or 0 for r in registros)
    horas_penalizadas = sum(r.horas_penalizadas or 0 for r in registros)
    objetivo_bono = sum(r.objetivo_facturacion_bono for r in registros)
    facturado_bono = sum(r.facturado_bono for r in registros)
    horas_objetivo_tarifadas = sum(r.horas_objetivo or 0 for r in registros if (r.horas_objetivo or 0) > 0)
    horas_netas_tarifadas = sum(
        max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0)
        for r in registros
        if max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0) > 0
    )
    valor_hora_objetivo = (
        sum((r.valor_hora_objetivo_calculo or 0) * (r.horas_objetivo or 0) for r in registros) / horas_objetivo_tarifadas
        if horas_objetivo_tarifadas > 0 else 0
    )
    valor_hora_realizado = (
        sum((r.valor_hora_alcanzado or 0) * max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0) for r in registros) / horas_netas_tarifadas
        if horas_netas_tarifadas > 0 else 0
    )
    return {
        **resumen,
        'total_facturado': round(total_facturado, 2),
        'total_real': round(total_facturado, 2),
        'total_teorico': round(total_teorico, 2),
        'desvio': round(desvio, 2),
        'porcentaje_cumplimiento': round(porcentaje, 2),
        'porcentaje_cumplimiento_horas': round((horas_facturadas / horas_objetivo * 100) if horas_objetivo > 0 else 0, 2),
        'porcentaje_cumplimiento_horas_adh': round(((horas_facturadas - horas_penalizadas) / horas_objetivo * 100) if horas_objetivo > 0 else 0, 2),
        'porcentaje_valor_hora': round((valor_hora_realizado / valor_hora_objetivo * 100) if valor_hora_objetivo > 0 else 0, 2),
        'porcentaje_bono': round((facturado_bono / objetivo_bono * 100) if objetivo_bono > 0 else 0, 2),
        'porcentaje_cumplimiento_facturacion': round(porcentaje, 2),
    }


MESES_MATRIZ = [
    ('01', 'ene'),
    ('02', 'feb'),
    ('03', 'mar'),
    ('04', 'abr'),
    ('05', 'may'),
    ('06', 'jun'),
    ('07', 'jul'),
    ('08', 'ago'),
    ('09', 'sep'),
    ('10', 'oct'),
    ('11', 'nov'),
    ('12', 'dic'),
]


MESES_PROYECCION = [
    ('01', 'ene'),
    ('02', 'feb'),
    ('03', 'mar'),
    ('04', 'abr'),
    ('05', 'may'),
    ('06', 'jun'),
    ('07', 'jul'),
    ('08', 'ago'),
    ('09', 'sep'),
    ('10', 'oct'),
    ('11', 'nov'),
    ('12', 'dic'),
]


def opciones_meses_proyeccion(year):
    return [
        {
            'value': f'{year}-{numero}',
            'label': f'{label}-{str(year)[-2:]}',
        }
        for numero, label in MESES_PROYECCION
    ]


def etiqueta_mes_proyeccion(mes):
    try:
        year, numero = str(mes).split('-', 1)
    except ValueError:
        return str(mes)
    labels = dict(MESES_PROYECCION)
    return f"{labels.get(numero, numero)}-{year[-2:]}"


def meses_proyeccion_desde(mes):
    mes_normalizado = mes_valido(mes)
    if not mes_normalizado:
        return []
    year = int(mes_normalizado[:4])
    mes_inicio = int(mes_normalizado[-2:])
    return [
        f'{year}-{numero}'
        for numero, _ in MESES_PROYECCION
        if int(numero) >= mes_inicio
    ]


CARGAS_SEMANALES_PROYECCION = (
    'L a V',
    'L a V + S',
    'S + D + F',
    'S',
    'D',
    'F',
    'L a V +S+D+F',
)


def normalizar_carga_semanal(value):
    value = ' '.join(str(value or '').strip().split())
    alias = {
        'L a V +S': 'L a V + S',
        'S+D+F': 'S + D + F',
        'L a V + S+D+F': 'L a V +S+D+F',
        'L a V + S + D + F': 'L a V +S+D+F',
    }
    value = alias.get(value, value)
    return value if value in CARGAS_SEMANALES_PROYECCION else 'L a V'


def fechas_feriadas_activas(year):
    return {
        feriado.fecha
        for feriado in FeriadoOperativo.query.filter_by(year=year, activo=True).all()
        if feriado.fecha
    }


def calcular_dias_objetivo(year, mes_numero, carga_semanal, feriados=None):
    carga = normalizar_carga_semanal(carga_semanal)
    feriados = feriados if feriados is not None else fechas_feriadas_activas(year)
    _, ultimo_dia = calendar.monthrange(year, mes_numero)
    dias = 0
    for dia in range(1, ultimo_dia + 1):
        fecha = date(year, mes_numero, dia)
        weekday = fecha.weekday()
        es_feriado = fecha in feriados
        cuenta = False
        if carga == 'L a V':
            cuenta = weekday < 5 and not es_feriado
        elif carga == 'L a V + S':
            cuenta = weekday < 6 and not es_feriado
        elif carga == 'S + D + F':
            cuenta = weekday in (5, 6) or es_feriado
        elif carga == 'S':
            cuenta = weekday == 5 and not es_feriado
        elif carga == 'D':
            cuenta = weekday == 6 and not es_feriado
        elif carga == 'F':
            cuenta = es_feriado
        elif carga == 'L a V +S+D+F':
            cuenta = True
        if cuenta:
            dias += 1
    return dias


def aplicar_calculo_proyeccion(proyeccion, valores, mes, feriados=None):
    year = int(mes[:4])
    mes_numero = int(mes[-2:])
    jornadas = valores.get('jornadas') or [{
        'dotacion_requerida': valores.get('dotacion_requerida') or 0,
        'carga_semanal': valores.get('carga_semanal'),
        'carga_horaria': valores.get('carga_horaria') or 0,
    }]
    jornadas_calculadas = []
    dotacion_total = 0
    horas_total = 0
    dias_objetivo_total = 0
    carga_semanal_resumen = normalizar_carga_semanal(jornadas[0].get('carga_semanal') if jornadas else None)
    carga_horaria_resumen = jornadas[0].get('carga_horaria') if jornadas else 0

    for jornada in jornadas:
        dotacion = jornada.get('dotacion_requerida') or 0
        carga_semanal = normalizar_carga_semanal(jornada.get('carga_semanal'))
        carga_horaria = jornada.get('carga_horaria') or 0
        dias_objetivo = calcular_dias_objetivo(year, mes_numero, carga_semanal, feriados)
        horas_requeridas = dotacion * dias_objetivo * carga_horaria
        dotacion_total += dotacion
        horas_total += horas_requeridas
        dias_objetivo_total = max(dias_objetivo_total, dias_objetivo)
        jornadas_calculadas.append({
            'dotacion_requerida': dotacion,
            'carga_semanal': carga_semanal,
            'carga_horaria': carga_horaria,
            'dias_objetivo': dias_objetivo,
            'horas_requeridas': horas_requeridas,
        })

    proyeccion.cliente = valores['cliente']
    proyeccion.campania = valores['campania']
    proyeccion.year = year
    proyeccion.mes = mes
    proyeccion.dotacion_requerida = dotacion_total
    proyeccion.carga_semanal = carga_semanal_resumen
    proyeccion.carga_horaria = carga_horaria_resumen or 0
    proyeccion.dias_objetivo = dias_objetivo_total
    proyeccion.horas_requeridas = horas_total
    proyeccion.porcentaje_cumplimiento = valores.get('porcentaje_cumplimiento') or 0
    proyeccion.jornadas = [
        ProyeccionMatrizJornada(**jornada)
        for jornada in jornadas_calculadas
    ]
    return proyeccion


def recalcular_proyecciones_mes(year, mes_numero):
    mes = f'{year}-{mes_numero:02d}'
    feriados = fechas_feriadas_activas(year)
    proyecciones = ProyeccionMatriz.query.filter_by(mes=mes).all()
    for proyeccion in proyecciones:
        jornadas = [jornada.to_dict() for jornada in proyeccion.jornadas]
        if not jornadas:
            carga_horaria = proyeccion.carga_horaria or 0
            if carga_horaria <= 0 and (proyeccion.horas_requeridas or 0) > 0 and (proyeccion.dotacion_requerida or 0) > 0:
                dias_base = proyeccion.dias_objetivo or calcular_dias_objetivo(year, mes_numero, proyeccion.carga_semanal or 'L a V', feriados)
                if dias_base > 0:
                    carga_horaria = proyeccion.horas_requeridas / ((proyeccion.dotacion_requerida or 0) * dias_base)
            jornadas = [{
                'dotacion_requerida': proyeccion.dotacion_requerida,
                'carga_semanal': proyeccion.carga_semanal,
                'carga_horaria': carga_horaria,
            }]
        valores = {
            'cliente': proyeccion.cliente,
            'campania': proyeccion.campania,
            'jornadas': jornadas,
            'porcentaje_cumplimiento': proyeccion.porcentaje_cumplimiento,
        }
        aplicar_calculo_proyeccion(proyeccion, valores, mes, feriados)
    return len(proyecciones)


def snapshot_proyeccion(proyeccion):
    if not proyeccion:
        return None
    return proyeccion.to_dict()


def buscar_proyeccion_snapshot(snapshot):
    if not snapshot:
        return None
    proyeccion_id = snapshot.get('id')
    if proyeccion_id:
        encontrada = ProyeccionMatriz.query.get(proyeccion_id)
        if encontrada:
            return encontrada
    return ProyeccionMatriz.query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first()


def restaurar_proyeccion_snapshot(proyeccion, snapshot):
    proyeccion.cliente = snapshot.get('cliente') or ''
    proyeccion.campania = snapshot.get('campania') or ''
    proyeccion.year = int(snapshot.get('year') or str(snapshot.get('mes', '0'))[:4] or 0)
    proyeccion.mes = snapshot.get('mes') or ''
    proyeccion.dotacion_requerida = snapshot.get('dotacion_requerida') or 0
    proyeccion.carga_semanal = normalizar_carga_semanal(snapshot.get('carga_semanal'))
    proyeccion.carga_horaria = snapshot.get('carga_horaria') or 0
    proyeccion.dias_objetivo = snapshot.get('dias_objetivo') or 0
    proyeccion.horas_requeridas = snapshot.get('horas_requeridas') or 0
    proyeccion.porcentaje_cumplimiento = snapshot.get('porcentaje_cumplimiento') or 0
    proyeccion.jornadas = [
        ProyeccionMatrizJornada(
            dotacion_requerida=jornada.get('dotacion_requerida') or 0,
            carga_semanal=normalizar_carga_semanal(jornada.get('carga_semanal')),
            carga_horaria=jornada.get('carga_horaria') or 0,
            dias_objetivo=jornada.get('dias_objetivo') or 0,
            horas_requeridas=jornada.get('horas_requeridas') or 0,
        )
        for jornada in snapshot.get('jornadas', [])
    ]


def buscar_precio_snapshot(snapshot):
    if not snapshot:
        return None
    precio_id = snapshot.get('id')
    if precio_id:
        encontrada = ProyeccionPrecio.query.get(precio_id)
        if encontrada:
            return encontrada
    return ProyeccionPrecio.query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first()


def restaurar_precio_snapshot(precio, snapshot):
    precio.site = snapshot.get('site') or ''
    precio.cliente = snapshot.get('cliente') or ''
    precio.campania = snapshot.get('campania') or ''
    precio.year = int(snapshot.get('year') or str(snapshot.get('mes', '0'))[:4] or 0)
    precio.mes = snapshot.get('mes') or ''
    precio.precio_base = redondear_moneda(snapshot.get('precio_base') or 0)
    precio.alcance_porcentaje = snapshot.get('alcance_porcentaje') or 0
    precio.importe_fijo_mensual = redondear_moneda(snapshot.get('importe_fijo_mensual') or 0)
    precio.recalcular()


def buscar_variable_snapshot(snapshot):
    if not snapshot:
        return None
    variable_id = snapshot.get('id')
    if variable_id:
        encontrada = VariableCampania.query.get(variable_id)
        if encontrada:
            return encontrada
    return VariableCampania.query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first()


def restaurar_variable_snapshot(variable, snapshot):
    variable.site = snapshot.get('site') or ''
    variable.cliente = snapshot.get('cliente') or ''
    variable.campania = snapshot.get('campania') or ''
    variable.year = int(snapshot.get('year') or str(snapshot.get('mes', '0'))[:4] or 0)
    variable.mes = snapshot.get('mes') or ''
    variable.porcentaje = snapshot.get('porcentaje') or 0


def lista_snapshots_historial(value):
    if not value:
        return []
    if isinstance(value, dict) and isinstance(value.get('proyecciones'), list):
        return value['proyecciones']
    if isinstance(value, dict) and isinstance(value.get('precios'), list):
        return value['precios']
    if isinstance(value, dict) and {'cliente', 'campania', 'mes'}.issubset(value.keys()):
        return [value]
    if isinstance(value, list):
        return value
    return []


def historial_movimiento_deshace(historial_id):
    patron = f'Deshacer movimiento #{historial_id}:%'
    return HistorialCambio.query.filter(
        HistorialCambio.accion == 'deshacer',
        HistorialCambio.resumen.like(patron),
    ).first() is not None


def existe_proyeccion_snapshot(snapshot):
    if not snapshot:
        return False
    query = ProyeccionMatriz.query
    proyeccion_id = snapshot.get('id')
    if proyeccion_id and query.filter_by(id=proyeccion_id).first():
        return True
    return query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first() is not None


def existe_precio_snapshot(snapshot):
    if not snapshot:
        return False
    query = ProyeccionPrecio.query
    precio_id = snapshot.get('id')
    if precio_id and query.filter_by(id=precio_id).first():
        return True
    return query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first() is not None


def existe_variable_snapshot(snapshot):
    if not snapshot:
        return False
    query = VariableCampania.query
    variable_id = snapshot.get('id')
    if variable_id and query.filter_by(id=variable_id).first():
        return True
    return query.filter_by(
        cliente=snapshot.get('cliente'),
        campania=snapshot.get('campania'),
        mes=snapshot.get('mes'),
    ).first() is not None


def metricas_matriz(registros):
    resumen = resumen_registros(registros)
    facturado_horas = sum(r.facturado_horas for r in registros)
    variable_real = sum(r.variable_productivo_calculo for r in registros)
    facturado_bono = sum(r.facturado_bono for r in registros)
    penalizaciones = sum(r.penalizaciones_incumplimientos for r in registros)
    tarifacion = sum(r.tarifacion or 0 for r in registros)
    netx_gen = sum(r.netx_gen or 0 for r in registros)
    otros = sum(r.otros or 0 for r in registros)
    objetivo_horas = sum(r.objetivo_facturacion_horas for r in registros)
    objetivo_bono = sum(r.objetivo_facturacion_bono for r in registros)
    horas_netas_facturadas = max(resumen['horas_facturadas'] - resumen['horas_penalizadas'], 0)
    horas_objetivo_tarifadas = sum(r.horas_objetivo for r in registros if (r.horas_objetivo or 0) > 0)
    horas_netas_tarifadas = sum(
        max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0)
        for r in registros
        if max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0) > 0
    )
    valor_hora_objetivo = (
        sum((r.valor_hora_objetivo_calculo or 0) * (r.horas_objetivo or 0) for r in registros) / horas_objetivo_tarifadas
        if horas_objetivo_tarifadas > 0 else 0
    )
    valor_hora_realizado = (
        sum((r.valor_hora_alcanzado or 0) * max((r.horas_facturadas or 0) - (r.horas_penalizadas or 0), 0) for r in registros) / horas_netas_tarifadas
        if horas_netas_tarifadas > 0 else 0
    )
    horas_con_penalidad_adh = horas_netas_facturadas
    desvio_horas = horas_netas_facturadas - resumen['horas_objetivo']
    desvio_horas_monto = facturado_horas - objetivo_horas
    desvio_variable = variable_real - objetivo_bono
    neto_penalizaciones_bonos = facturado_bono + penalizaciones
    neto_otros_ajustes = 0
    total_objetivo = resumen['total_teorico']
    total_real = facturado_horas + variable_real + neto_penalizaciones_bonos + neto_otros_ajustes
    return {
        **resumen,
        'horas_netas_facturadas': round(horas_netas_facturadas, 2),
        'total_real': round(total_real, 2),
        'total_facturado': round(total_real, 2),
        'desvio': round(total_real - total_objetivo, 2),
        'porcentaje_cumplimiento': round(
            (total_real / total_objetivo * 100)
            if total_objetivo > 0 else 0,
            2
        ),
        'valor_hora_objetivo': round(valor_hora_objetivo, 2),
        'valor_hora_realizado': round(valor_hora_realizado, 2),
        'porcentaje_cumplimiento_horas': round(
            (resumen['horas_facturadas'] / resumen['horas_objetivo'] * 100)
            if resumen['horas_objetivo'] > 0 else 0,
            2
        ),
        'porcentaje_cumplimiento_logueo': round(
            (resumen['horas_facturadas'] / resumen['horas_objetivo'] * 100)
            if resumen['horas_objetivo'] > 0 else 0,
            2
        ),
        'porcentaje_cumplimiento_horas_adh': round(
            (horas_con_penalidad_adh / resumen['horas_objetivo'] * 100)
            if resumen['horas_objetivo'] > 0 else 0,
            2
        ),
        'porcentaje_valor_hora': round(
            (valor_hora_realizado / valor_hora_objetivo * 100)
            if valor_hora_objetivo > 0 else 0,
            2
        ),
        'porcentaje_bono': round(
            (facturado_bono / objetivo_bono * 100)
            if objetivo_bono > 0 else 0,
            2
        ),
        'desvio_horas': round(desvio_horas, 2),
        'desvio_horas_monto': round(desvio_horas_monto, 2),
        'horas_obj': round(objetivo_horas, 2),
        'variable_obj': round(objetivo_bono, 2),
        'total_obj': round(total_objetivo, 2),
        'horas_real': round(facturado_horas, 2),
        'variable_real': round(variable_real, 2),
        'bonos_real': round(facturado_bono, 2),
        'penalizaciones_real': round(penalizaciones, 2),
        'tarifacion_real': round(tarifacion, 2),
        'netx_gen_real': round(netx_gen, 2),
        'otros_real': round(otros, 2),
        'penalizaciones_bonos': round(neto_penalizaciones_bonos, 2),
        'otros_ajustes': round(neto_otros_ajustes, 2),
        'desvio_variable': round(desvio_variable, 2),
        'desvio_penalizaciones_bonos': round(neto_penalizaciones_bonos, 2),
        'desvio_otros_ajustes': round(neto_otros_ajustes, 2),
    }


def matriz_grupos(registros, campo, meses):
    grupos = {}
    for registro in registros:
        nombre = getattr(registro, campo) or 'Sin asignar'
        grupos.setdefault(nombre, []).append(registro)

    salida = []
    for nombre, registros_grupo in grupos.items():
        por_mes = {}
        for mes in meses:
            registros_mes = [r for r in registros_grupo if r.mes == mes]
            por_mes[mes] = metricas_matriz(registros_mes) if registros_mes else None
        salida.append({
            'nombre': nombre,
            'total': metricas_matriz(registros_grupo),
            'meses': por_mes,
        })
    salida.sort(key=lambda item: item['nombre'])
    return salida


def validar_payload_facturacion(data):
    errores = []
    tipo_jornada = normalizar_tipo_vh(data.get('tipo_jornada'))
    sin_restriccion_horas = tipo_jornada == TIPO_VH_PERSONAL_COBRANZAS
    for campo, mensaje in [
        ('fecha', 'La fecha es obligatoria'),
        ('mes', 'El mes de facturacion es obligatorio'),
        ('cliente', 'El cliente es obligatorio'),
        ('gerente', 'El gerente es obligatorio'),
        ('jefe_site', 'El jefe de site es obligatorio'),
        ('campania', 'La campaña es obligatoria'),
        ('subcampania', 'La sub campaña es obligatoria'),
        ('tipo_jornada', 'El tipo de VH es obligatorio'),
    ]:
        if not str(data.get(campo, '')).strip():
            errores.append(mensaje)

    try:
        horas_objetivo = parse_numero(data.get('horas_objetivo'))
        horas_facturadas = parse_numero(data.get('horas_facturadas'))
        horas_penalizadas = parse_numero(data.get('horas_penalizadas'))
        valor_hora = parse_numero(data.get('valor_hora'))
        valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo', valor_hora))
        importe_fijo = parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None
        variable_objetivo = parse_numero(data.get('variable_objetivo'))
        variable_productivo = parse_numero(data.get('variable_productivo'))
    except ValueError:
        errores.append('Hay valores numéricos con formato inválido')
        horas_objetivo = horas_facturadas = horas_penalizadas = valor_hora = valor_hora_objetivo = 0
        importe_fijo = None
        variable_objetivo = 0
        variable_productivo = 0
    if horas_objetivo < 0:
        errores.append('Las horas objetivo no pueden ser negativas')
    if horas_facturadas < 0:
        errores.append('Las horas facturadas no pueden ser negativas')
    if horas_penalizadas < 0:
        errores.append('Las horas penalizadas no pueden ser negativas')
    if not sin_restriccion_horas and horas_penalizadas > horas_facturadas:
        errores.append('Las horas penalizadas no pueden superar las horas facturadas')
    if not sin_restriccion_horas and valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if not sin_restriccion_horas and valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
    if importe_fijo is not None and importe_fijo < 0:
        errores.append('El importe fijo facturado no puede ser negativo')
    if variable_objetivo < 0:
        errores.append('Variable Objetivo no puede ser negativo')
    if tipo_jornada and tipo_jornada not in TIPOS_VH:
        errores.append('El tipo de VH no es válido')
    if data.get('mes') and not mes_valido(data.get('mes')):
        errores.append('El mes de facturacion no es valido')
    return errores


def asegurar_asignacion_desde_registro(registro):
    campos = {
        'cliente': registro.cliente,
        'gerente': registro.gerente,
        'jefe_site': registro.jefe_site,
        'campania': registro.campania,
        'subcampania': registro.subcampania,
        'tipo_negocio': registro.tipo_negocio,
    }
    if not all(valor for campo, valor in campos.items() if campo != 'tipo_negocio'):
        return None
    existente = AsignacionComercial.query.filter_by(**campos).first()
    if existente:
        existente.activa = True
        return existente
    asignacion = AsignacionComercial(**campos)
    db.session.add(asignacion)
    return asignacion


@main_bp.route('/')
@login_requerido
def index():
    """Dashboard principal"""
    return render_template('index.html')


@main_bp.route('/favicon.ico')
def favicon():
    return Response(status=204)


@main_bp.route('/cargar')
@edicion_requerida
def cargar():
    """Vista de carga de datos"""
    return render_template('cargar.html')


@main_bp.route('/control')
@login_requerido
def control():
    """Vista de control de datos"""
    return render_template('control.html')


@main_bp.route('/justificaciones')
@login_requerido
def justificaciones():
    """Vista de control de justificaciones de ajustes."""
    return render_template('justificaciones.html')


@main_bp.route('/comparativo')
@login_requerido
def comparativo():
    """Vista comparativa de horas objetivo contra horas facturadas"""
    return render_template('comparativo.html')


@main_bp.route('/matriz')
@login_requerido
def matriz():
    """Vista matricial mensual por gerencia y jefe de site."""
    return render_template('matriz.html')


@main_bp.route('/matriz-proyecciones')
@login_requerido
def matriz_proyecciones():
    """Vista de planificación mensual de dotación y horas proyectadas."""
    return render_template('matriz_proyecciones.html')


@main_bp.route('/matriz-precios')
@login_requerido
def matriz_precios():
    """Vista de planificación mensual de precios por campaña."""
    return render_template('matriz_precios.html')


@main_bp.route('/resumen')
@login_requerido
def resumen():
    """Resumen anual de horas proyectadas por precio mensual."""
    return render_template('resumen.html')


@main_bp.route('/variable')
@login_requerido
def variable():
    """Vista de variables por campaña sobre facturación horas."""
    return render_template('variable.html')


@main_bp.route('/control-proyecciones')
@login_requerido
def control_proyecciones():
    """Vista de control mensual de horas y dotaciones proyectadas."""
    return render_template('control_proyecciones.html')


@main_bp.route('/calendario-operativo')
@login_requerido
def calendario_operativo():
    """Configuración anual de feriados operativos."""
    return render_template('calendario_operativo.html')


@main_bp.route('/catalogos')
@edicion_requerida
def catalogos():
    """Vista de alta de datos maestros"""
    return render_template('catalogos.html')


@main_bp.route('/catalogos/crear', methods=['GET', 'POST'])
@edicion_requerida
def catalogos_crear():
    """Alta simple de datos maestros desde formulario HTML."""
    if request.method == 'GET':
        return redirect(url_for('main.catalogos'))
    respuesta = crear_asignacion_desde_request()
    status = respuesta[1] if isinstance(respuesta, tuple) and len(respuesta) > 1 else getattr(respuesta, 'status_code', 200)
    if status >= 400:
        return redirect(url_for('main.catalogos', estado='error'))
    return redirect(url_for('main.catalogos', estado='creado'))


@main_bp.route('/login')
def login():
    """Vista de acceso y primera configuracion."""
    asegurar_administrador_inicial()
    if requiere_login():
        return redirect(url_for('main.index'))
    return render_template('login.html', requiere_setup=not usuarios_registrados())


@main_bp.route('/logout', methods=['POST'])
@login_requerido
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main_bp.route('/usuarios')
@admin_requerido
def usuarios():
    """Vista de administracion de usuarios."""
    return render_template('usuarios.html', roles=ROLES_USUARIO)


@main_bp.route('/historial')
@admin_requerido
def historial():
    """Vista de historial de modificaciones y eliminaciones."""
    return render_template('historial.html')


# ========== ENDPOINTS API ==========

@main_bp.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    asegurar_administrador_inicial()
    return jsonify({
        'success': True,
        'usuario': usuario_actual_dict(),
        'requiere_setup': not usuarios_registrados(),
        'csrf_token': get_csrf_token(),
    })


@main_bp.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    email = normalizar_email(data.get('email'))
    password = str(data.get('password', '') or '')

    if login_bloqueado(email):
        return jsonify({'success': False, 'errores': ['Demasiados intentos. Espere unos minutos e intente nuevamente']}), 429

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not usuario.activo or not usuario.check_password(password):
        registrar_login_fallido(email)
        return jsonify({'success': False, 'errores': ['Email o contrasena incorrectos']}), 401

    session.clear()
    session.permanent = True
    session['usuario_id'] = usuario.id
    csrf_token = get_csrf_token()
    limpiar_login_fallido(email)
    return jsonify({'success': True, 'usuario': usuario.to_dict(), 'csrf_token': csrf_token})


@main_bp.route('/api/auth/logout', methods=['POST'])
@login_requerido
def api_auth_logout():
    session.clear()
    return jsonify({'success': True})


@main_bp.route('/api/usuarios/setup', methods=['POST'])
def api_usuarios_setup():
    """Crea el primer administrador cuando la base aun no tiene usuarios."""
    if usuarios_registrados():
        return jsonify({'success': False, 'errores': ['La configuracion inicial ya fue realizada']}), 403

    data = request.get_json() or {}
    data['rol'] = 'administrador'
    errores = validar_usuario_payload(data, require_password=True)
    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    usuario = Usuario(
        nombre=data['nombre'].strip(),
        email=normalizar_email(data['email']),
        rol='administrador',
        activo=True,
    )
    usuario.set_password(data['password'])
    db.session.add(usuario)
    db.session.commit()
    session.clear()
    session.permanent = True
    session['usuario_id'] = usuario.id
    csrf_token = get_csrf_token()
    return jsonify({'success': True, 'usuario': usuario.to_dict(), 'csrf_token': csrf_token})


@main_bp.route('/api/usuarios', methods=['GET'])
@admin_requerido
def api_usuarios():
    usuarios = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    return jsonify({'success': True, 'usuarios': [usuario.to_dict() for usuario in usuarios]})


@main_bp.route('/api/usuarios', methods=['POST'])
@admin_requerido
def api_crear_usuario():
    data = request.get_json() or {}
    errores = validar_usuario_payload(data, require_password=True)
    email = normalizar_email(data.get('email'))
    if Usuario.query.filter_by(email=email).first():
        errores.append('Ya existe un usuario con ese email')
    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    usuario = Usuario(
        nombre=data['nombre'].strip(),
        email=email,
        rol=data.get('rol', 'usuario').strip(),
        activo=bool(data.get('activo', True)),
    )
    usuario.set_password(data['password'])
    db.session.add(usuario)
    db.session.flush()
    registrar_historial(
        'creacion',
        'usuario',
        usuario.id,
        f'Usuario creado: {usuario.email}',
        despues=usuario.to_dict(),
    )
    db.session.commit()
    return jsonify({'success': True, 'usuario': usuario.to_dict()})


@main_bp.route('/api/usuarios/<int:usuario_id>', methods=['PATCH'])
@admin_requerido
def api_actualizar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    antes = snapshot_modelo(usuario)
    data = request.get_json() or {}
    errores = []

    if 'nombre' in data:
        nombre = str(data.get('nombre', '')).strip()
        if not nombre:
            errores.append('El nombre es obligatorio')
        else:
            usuario.nombre = nombre
    if 'email' in data:
        email = normalizar_email(data.get('email'))
        existente = Usuario.query.filter(Usuario.email == email, Usuario.id != usuario.id).first()
        if not email or '@' not in email:
            errores.append('El email es obligatorio y debe ser valido')
        elif existente:
            errores.append('Ya existe un usuario con ese email')
        else:
            usuario.email = email
    if 'rol' in data:
        rol = str(data.get('rol', '')).strip()
        if rol not in ROLES_USUARIO:
            errores.append('El rol no es valido')
        else:
            usuario.rol = rol
    if 'activo' in data:
        usuario.activo = bool(data.get('activo'))
    if data.get('password'):
        password = str(data.get('password'))
        if len(password) < 12:
            errores.append('La contrasena debe tener al menos 12 caracteres')
        elif password.lower() == password or password.upper() == password or not any(caracter.isdigit() for caracter in password):
            errores.append('La contrasena debe combinar mayusculas, minusculas y numeros')
        else:
            usuario.set_password(password)

    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    despues = snapshot_modelo(usuario)
    cambios = cambios_entre(antes, despues)
    if cambios:
        registrar_historial(
            'edicion',
            'usuario',
            usuario.id,
            f'Usuario actualizado: {usuario.email}',
            antes=antes,
            despues=despues,
            detalle=serializar_json(cambios),
        )
    db.session.commit()
    return jsonify({'success': True, 'usuario': usuario.to_dict()})


@main_bp.route('/api/historial', methods=['GET'])
@admin_requerido
def api_historial():
    query = HistorialCambio.query
    accion = request.args.get('accion')
    entidad = request.args.get('entidad')
    if accion:
        query = query.filter(HistorialCambio.accion == accion)
    if entidad:
        query = query.filter(HistorialCambio.entidad == entidad)
    limite = min(numero_request('limite') or 100, 300)
    items = query.order_by(HistorialCambio.creado_en.desc()).limit(int(limite)).all()
    return jsonify({'success': True, 'historial': [item.to_dict() for item in items]})


@main_bp.route('/api/historial/<int:historial_id>/deshacer', methods=['POST'])
@admin_requerido
def api_deshacer_historial(historial_id):
    item = HistorialCambio.query.get_or_404(historial_id)
    resultado, status = deshacer_item_historial(item)
    return jsonify(resultado), status


def deshacer_item_historial(item):
    if item.accion == 'deshacer':
        return {'success': False, 'errores': ['Este movimiento ya es un deshacer']}, 400
    if historial_movimiento_deshace(item.id):
        return {'success': False, 'errores': ['Este movimiento ya fue deshecho']}, 400
    entidades_permitidas = ('proyeccion_matriz', 'matriz_precios', 'variables')
    if item.entidad not in entidades_permitidas:
        return {'success': False, 'errores': ['Por ahora solo se pueden deshacer movimientos de proyecciones, precios y variables']}, 400

    antes = item._json(item.antes) or {}
    despues = item._json(item.despues) or {}
    antes_snapshots = lista_snapshots_historial(antes)
    despues_snapshots = lista_snapshots_historial(despues)
    cantidad = max(len(antes_snapshots), len(despues_snapshots))

    for indice in range(cantidad):
        antes_snapshot = antes_snapshots[indice] if indice < len(antes_snapshots) else None
        despues_snapshot = despues_snapshots[indice] if indice < len(despues_snapshots) else None
        if item.entidad == 'matriz_precios':
            actual = buscar_precio_snapshot(despues_snapshot) or buscar_precio_snapshot(antes_snapshot)
        elif item.entidad == 'variables':
            actual = buscar_variable_snapshot(despues_snapshot) or buscar_variable_snapshot(antes_snapshot)
        else:
            actual = buscar_proyeccion_snapshot(despues_snapshot) or buscar_proyeccion_snapshot(antes_snapshot)
        if antes_snapshot:
            if not actual:
                if item.entidad == 'matriz_precios':
                    actual = ProyeccionPrecio()
                elif item.entidad == 'variables':
                    actual = VariableCampania()
                else:
                    actual = ProyeccionMatriz()
                db.session.add(actual)
            if item.entidad == 'matriz_precios':
                restaurar_precio_snapshot(actual, antes_snapshot)
            elif item.entidad == 'variables':
                restaurar_variable_snapshot(actual, antes_snapshot)
            else:
                restaurar_proyeccion_snapshot(actual, antes_snapshot)
        elif actual:
            db.session.delete(actual)

    registrar_historial(
        'deshacer',
        item.entidad,
        item.entidad_id,
        f'Deshacer movimiento #{item.id}: {item.resumen}',
        antes=despues,
        despues=antes,
    )
    db.session.flush()
    errores_validacion = []
    for indice in range(cantidad):
        antes_snapshot = antes_snapshots[indice] if indice < len(antes_snapshots) else None
        despues_snapshot = despues_snapshots[indice] if indice < len(despues_snapshots) else None
        if item.entidad == 'matriz_precios':
            existe_antes = existe_precio_snapshot(antes_snapshot)
            existe_despues = existe_precio_snapshot(despues_snapshot)
        elif item.entidad == 'variables':
            existe_antes = existe_variable_snapshot(antes_snapshot)
            existe_despues = existe_variable_snapshot(despues_snapshot)
        else:
            existe_antes = existe_proyeccion_snapshot(antes_snapshot)
            existe_despues = existe_proyeccion_snapshot(despues_snapshot)
        if antes_snapshot and not existe_antes:
            errores_validacion.append(f'No se pudo restaurar {antes_snapshot.get("cliente")} / {antes_snapshot.get("campania")} / {antes_snapshot.get("mes")}')
        if not antes_snapshot and despues_snapshot and existe_despues:
            errores_validacion.append(f'No se pudo eliminar {despues_snapshot.get("cliente")} / {despues_snapshot.get("campania")} / {despues_snapshot.get("mes")}')
    if errores_validacion:
        db.session.rollback()
        return {'success': False, 'errores': errores_validacion}, 500
    db.session.commit()
    return {'success': True, 'mensaje': f'Movimiento #{item.id} deshecho'}, 200


@main_bp.route('/api/cargar', methods=['POST'])
@edicion_requerida
def api_cargar():
    """Endpoint para cargar datos de facturación"""
    data = request.get_json() or {}
    data['cliente'] = data.get('cliente', '').strip()
    data['gerente'] = data.get('gerente', '').strip()
    data['jefe_site'] = data.get('jefe_site', '').strip()
    data['campania'] = data.get('campania', '').strip()
    data['subcampania'] = data.get('subcampania', '').strip()
    data['mes'] = data.get('mes', '').strip()
    
    # Validaciones
    errores = []
    tipo_jornada = normalizar_tipo_vh(data.get('tipo_jornada'))
    sin_restriccion_horas = tipo_jornada == TIPO_VH_PERSONAL_COBRANZAS
    
    if not data.get('fecha'):
        errores.append('La fecha es obligatoria')
    if not data.get('mes'):
        errores.append('El mes de facturacion es obligatorio')
    elif not mes_valido(data.get('mes')):
        errores.append('El mes de facturacion no es valido')
    if not data.get('cliente'):
        errores.append('El cliente es obligatorio')
    if not data.get('tipo_jornada'):
        errores.append('El tipo de VH es obligatorio')
    # Validar gerente
    if not data.get('gerente'):
        errores.append('El gerente es obligatorio')
    if not data.get('jefe_site'):
        errores.append('El jefe de site es obligatorio')
    if not data.get('campania'):
        errores.append('La campaña es obligatoria')
    if not data.get('subcampania'):
        errores.append('La sub campaña es obligatoria')
    
    try:
        horas_objetivo = parse_numero(data.get('horas_objetivo'))
        horas_facturadas = parse_numero(data.get('horas_facturadas'))
        horas_penalizadas = parse_numero(data.get('horas_penalizadas'))
        valor_hora = parse_numero(data.get('valor_hora'))
        valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo', valor_hora))
        importe_fijo = parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None
        variable_objetivo = parse_numero(data.get('variable_objetivo'))
        variable_productivo = parse_numero(data.get('variable_productivo'))
    except ValueError:
        errores.append('Hay valores numéricos con formato inválido')
        horas_objetivo = horas_facturadas = horas_penalizadas = valor_hora = valor_hora_objetivo = 0
        importe_fijo = None
        variable_objetivo = 0
        variable_productivo = 0
    
    if horas_objetivo < 0:
        errores.append('Las horas objetivo no pueden ser negativas')
    if horas_facturadas < 0:
        errores.append('Las horas facturadas no pueden ser negativas')
    if horas_penalizadas < 0:
        errores.append('Las horas penalizadas no pueden ser negativas')
    if not sin_restriccion_horas and horas_penalizadas > horas_facturadas:
        errores.append('Las horas penalizadas no pueden superar las horas facturadas')
    if not sin_restriccion_horas and valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if not sin_restriccion_horas and valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
    if importe_fijo is not None and importe_fijo < 0:
        errores.append('El importe fijo facturado no puede ser negativo')
    if variable_objetivo < 0:
        errores.append('Variable Objetivo no puede ser negativo')
    if tipo_jornada and tipo_jornada not in TIPOS_VH:
        errores.append('El tipo de VH no es válido')
    
    errores.extend(validar_justificaciones(data))

    if errores:
        return jsonify({'success': False, 'errores': errores}), 400
    
    try:
        nuevo_registro = crear_registro_facturacion(data)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': 'Datos cargados correctamente',
            'id': nuevo_registro.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(e)]}), 500


@main_bp.route('/api/datos', methods=['GET'])
@login_requerido
def api_datos():
    """Endpoint para obtener datos filtrados por mes, cliente y gerente"""
    query = aplicar_filtros(Facturacion2026.query, **filtros_request())
    registros = query.order_by(Facturacion2026.fecha.desc()).all()

    return jsonify({
        'success': True,
        'data': [r.to_dict() for r in registros]
    })


@main_bp.route('/api/justificaciones', methods=['GET'])
@login_requerido
def api_justificaciones():
    """Listado de justificaciones de bonos, penalizaciones y otros."""
    registros = aplicar_filtros(
        Facturacion2026.query,
        **filtros_request()
    ).order_by(Facturacion2026.fecha.desc()).all()

    items = []
    for registro in registros:
        for justificacion in registro.justificaciones:
            item = justificacion.to_dict()
            item.update({
                'fecha': registro.fecha.isoformat() if registro.fecha else None,
                'mes': registro.mes,
                'cliente': registro.cliente,
                'gerente': registro.gerente,
                'jefe_site': registro.jefe_site,
                'campania': registro.campania,
                'subcampania': registro.subcampania,
                'tipo_jornada': registro.tipo_jornada,
            })
            items.append(item)

    return jsonify({'success': True, 'data': items})


@main_bp.route('/api/datos/<int:registro_id>', methods=['PUT'])
@edicion_requerida
def api_actualizar_dato(registro_id):
    data = request.get_json() or {}
    if not validar_confirmacion_accion(data):
        return jsonify({'success': False, 'errores': ['La confirmacion no es valida']}), 403

    registro = Facturacion2026.query.get_or_404(registro_id)
    antes = snapshot_modelo(registro)
    errores = validar_payload_facturacion(data)
    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    try:
        fecha = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
        registro.fecha = fecha
        registro.mes = mes_valido(data.get('mes'))
        registro.cliente = data['cliente'].strip()
        registro.gerente = data['gerente'].strip()
        registro.jefe_site = data['jefe_site'].strip()
        registro.campania = data['campania'].strip()
        registro.subcampania = data['subcampania'].strip()
        registro.tipo_negocio = str(data.get('tipo_negocio') or '').strip() or None
        registro.tipo_jornada = normalizar_tipo_vh(data['tipo_jornada'])
        registro.horas_objetivo = parse_numero(data.get('horas_objetivo'))
        registro.horas_facturadas = parse_numero(data.get('horas_facturadas'))
        registro.horas_penalizadas = parse_numero(data.get('horas_penalizadas'))
        registro.valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo') or data.get('valor_hora'))
        registro.valor_hora = parse_numero(data.get('valor_hora'))
        registro.tarifacion = parse_numero(data.get('tarifacion')) if data.get('tarifacion') not in (None, '') else None
        registro.importe_fijo = parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None
        registro.variable_objetivo = parse_numero(data.get('variable_objetivo'))
        registro.variable_productivo = parse_numero(data.get('variable_productivo'))
        registro.bonos = float(data.get('bonos', 0) or 0)
        registro.penalizaciones = normalizar_importe_ajuste('penalizaciones', data.get('penalizaciones'))
        registro.netx_gen = float(data.get('netx_gen', 0) or 0)
        registro.otros = float(data.get('otros', 0) or 0)
        asegurar_asignacion_desde_registro(registro)
        despues = snapshot_modelo(registro)
        cambios = cambios_entre(antes, despues)
        if cambios:
            registrar_historial(
                'edicion',
                'facturacion',
                registro.id,
                f'Facturacion editada: {registro.cliente} / {registro.mes}',
                antes=antes,
                despues=despues,
                detalle=serializar_json(cambios),
            )
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Registro actualizado', 'data': registro.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(e)]}), 500


@main_bp.route('/api/datos/<int:registro_id>', methods=['DELETE'])
@eliminacion_requerida
def api_eliminar_dato(registro_id):
    data = request.get_json() or {}
    if not validar_confirmacion_accion(data):
        return jsonify({'success': False, 'errores': ['La confirmacion no es valida']}), 403

    registro = Facturacion2026.query.get_or_404(registro_id)
    antes = snapshot_modelo(registro)
    registrar_historial(
        'eliminacion',
        'facturacion',
        registro.id,
        f'Facturacion eliminada: {registro.cliente} / {registro.mes}',
        antes=antes,
        detalle=f"Se elimino el registro de {registro.cliente} correspondiente a {registro.mes}.",
    )
    db.session.delete(registro)
    db.session.commit()
    return jsonify({'success': True, 'mensaje': 'Registro eliminado'})


@main_bp.route('/api/resumen', methods=['GET'])
@login_requerido
def api_resumen():
    """Endpoint para resumen mensual"""
    filtros = filtros_request()
    
    query = db.session.query(
        Facturacion2026.mes,
        func.sum(Facturacion2026.horas_objetivo).label('horas_objetivo'),
        func.sum(Facturacion2026.horas_facturadas).label('horas_facturadas'),
        func.sum(Facturacion2026.bonos).label('bonos'),
        func.sum(Facturacion2026.netx_gen).label('netx_gen'),
        func.sum(Facturacion2026.otros).label('otros')
    )
    
    query = aplicar_filtros(query, **filtros)
    
    resultados = query.group_by(Facturacion2026.mes).order_by(Facturacion2026.mes).all()
    
    resumen = []
    for r in resultados:
        # Calcular totales usando la lógica del modelo
        registros_mes = aplicar_filtros(
            Facturacion2026.query,
            mes=r.mes,
            cliente=filtros['cliente'],
            gerente=filtros['gerente'],
            jefe_site=filtros['jefe_site'],
            campania=filtros['campania'],
            subcampania=filtros['subcampania'],
            tipo_negocio=filtros['tipo_negocio']
        ).all()
        
        resumen_mes = resumen_dashboard(registros_mes)
        
        resumen.append({
            'mes': r.mes,
            **resumen_mes
        })
    
    return jsonify({
        'success': True,
        'resumen': resumen
    })


@main_bp.route('/api/kpis', methods=['GET'])
@login_requerido
def api_kpis():
    """Endpoint para obtener KPIs generales"""
    registros = registros_filtrados()
    
    if not registros:
        return jsonify({
            'success': True,
            'kpis': {
                'total_facturado': 0,
                'total_real': 0,
                'total_teorico': 0,
                'desvio': 0,
                'porcentaje_cumplimiento': 0,
                'porcentaje_cumplimiento_horas': 0,
                'porcentaje_cumplimiento_horas_adh': 0,
                'porcentaje_valor_hora': 0,
                'porcentaje_bono': 0,
                'porcentaje_cumplimiento_facturacion': 0,
                'horas_objetivo': 0,
                'horas_facturadas': 0,
                'bonos': 0,
                'variable_productivo': 0,
                'penalizaciones': 0,
                'tarifacion': 0
            }
        })

    kpis = resumen_dashboard(registros)
    
    return jsonify({
        'success': True,
        'kpis': kpis
    })


@main_bp.route('/api/grafico', methods=['GET'])
@login_requerido
def api_grafico():
    """Endpoint para datos del gráfico de evolución mensual"""
    filtros = filtros_request()

    query = db.session.query(
        Facturacion2026.mes,
        func.sum(Facturacion2026.horas_objetivo).label('horas_objetivo'),
        func.sum(Facturacion2026.horas_facturadas).label('horas_facturadas')
    )
    query = aplicar_filtros(query, **filtros)
    resultados = query.group_by(Facturacion2026.mes).order_by(Facturacion2026.mes).all()
    
    # Calcular totales reales y teóricos por mes
    datos = []
    for r in resultados:
        registros_mes = aplicar_filtros(
            Facturacion2026.query,
            mes=r.mes,
            cliente=filtros['cliente'],
            gerente=filtros['gerente'],
            jefe_site=filtros['jefe_site'],
            campania=filtros['campania'],
            subcampania=filtros['subcampania'],
            tipo_negocio=filtros['tipo_negocio']
        ).all()
        total_real = sum(reg.total_dashboard for reg in registros_mes)
        total_teorico = sum(reg.total_teorico for reg in registros_mes)
        
        datos.append({
            'mes': r.mes,
            'total_real': round(total_real, 2),
            'total_teorico': round(total_teorico, 2)
        })
    
    return jsonify({
        'success': True,
        'datos': datos
    })


@main_bp.route('/api/filtros', methods=['GET'])
@login_requerido
def api_filtros():
    """Opciones dinamicas disponibles para los filtros del dashboard."""
    filtros = filtros_request()
    return jsonify({
        'success': True,
        'filtros': {
            'meses': opciones_filtro(filtros, 'mes'),
            'clientes': opciones_filtro(filtros, 'cliente'),
            'gerentes': opciones_filtro(filtros, 'gerente'),
            'jefes_site': opciones_filtro(filtros, 'jefe_site'),
            'campanias': opciones_filtro(filtros, 'campania'),
            'subcampanias': opciones_filtro(filtros, 'subcampania'),
            'tipos_negocio': opciones_filtro(filtros, 'tipo_negocio'),
        }
    })


@main_bp.route('/api/por-cliente', methods=['GET'])
@login_requerido
def api_por_cliente():
    """Agrupacion ejecutiva por cliente."""
    registros = registros_filtrados()
    grupos = {}
    for registro in registros:
        grupos.setdefault(registro.cliente, []).append(registro)

    datos = []
    for cliente, registros_cliente in grupos.items():
        resumen = resumen_dashboard(registros_cliente)
        datos.append({
            'cliente': cliente,
            'gerente': registros_cliente[0].gerente,
            'jefe_site': registros_cliente[0].jefe_site,
            'registros': len(registros_cliente),
            **resumen
        })

    datos.sort(key=lambda item: item['total_real'], reverse=True)
    return jsonify({'success': True, 'clientes': datos})


@main_bp.route('/api/comparativo', methods=['GET'])
@login_requerido
def api_comparativo():
    """Comparativo de horas objetivo contra horas facturadas."""
    filtros = filtros_comparativo_request()
    registros = aplicar_filtros(Facturacion2026.query, **filtros).order_by(
        Facturacion2026.mes,
        Facturacion2026.cliente
    ).all()

    resumen = resumen_registros(registros)
    resumen['diferencia_horas'] = round(resumen['horas_facturadas'] - resumen['horas_objetivo'], 2)
    resumen['cumplimiento_horas'] = round(
        (resumen['horas_facturadas'] / resumen['horas_objetivo'] * 100)
        if resumen['horas_objetivo'] > 0 else 0,
        2
    )

    grupos_mes = {}
    grupos_cliente = {}
    for registro in registros:
        grupos_mes.setdefault(registro.mes, []).append(registro)
        clave_cliente = (
            registro.cliente,
            registro.gerente,
            registro.jefe_site,
            registro.campania,
            registro.subcampania,
        )
        grupos_cliente.setdefault(clave_cliente, []).append(registro)

    por_mes = []
    for mes, registros_mes in grupos_mes.items():
        horas_objetivo = sum(r.horas_objetivo for r in registros_mes)
        horas_facturadas = sum(r.horas_facturadas for r in registros_mes)
        por_mes.append({
            'mes': mes,
            'horas_objetivo': round(horas_objetivo, 2),
            'horas_facturadas': round(horas_facturadas, 2),
            'diferencia_horas': round(horas_facturadas - horas_objetivo, 2),
            'cumplimiento_horas': round((horas_facturadas / horas_objetivo * 100) if horas_objetivo > 0 else 0, 2),
        })

    por_cliente = []
    for (cliente, gerente, jefe_site, campania, subcampania), registros_cliente in grupos_cliente.items():
        horas_objetivo = sum(r.horas_objetivo for r in registros_cliente)
        horas_facturadas = sum(r.horas_facturadas for r in registros_cliente)
        por_cliente.append({
            'cliente': cliente,
            'gerente': gerente,
            'jefe_site': jefe_site,
            'campania': campania,
            'subcampania': subcampania,
            'registros': len(registros_cliente),
            'horas_objetivo': round(horas_objetivo, 2),
            'horas_facturadas': round(horas_facturadas, 2),
            'diferencia_horas': round(horas_facturadas - horas_objetivo, 2),
            'cumplimiento_horas': round((horas_facturadas / horas_objetivo * 100) if horas_objetivo > 0 else 0, 2),
        })

    por_mes.sort(key=lambda item: item['mes'])
    por_cliente.sort(key=lambda item: abs(item['diferencia_horas']), reverse=True)

    return jsonify({
        'success': True,
        'kpis': resumen,
        'por_mes': por_mes,
        'por_cliente': por_cliente,
        'detalle': [r.to_dict() for r in registros],
    })


@main_bp.route('/api/matriz', methods=['GET'])
@login_requerido
def api_matriz():
    """Matriz mensual de cumplimiento por gerencia y apertura por jefe de site."""
    year = request.args.get('year') or '2026'
    filtros = filtros_request()
    meses = [f'{year}-{numero}' for numero, _ in MESES_MATRIZ]
    columnas = [{'key': mes, 'label': f'{label}-{year[-2:]}'} for mes, (_, label) in zip(meses, MESES_MATRIZ)]

    base_year = Facturacion2026.query.filter(Facturacion2026.mes.in_(meses))
    registros_year = aplicar_filtros(base_year, **filtros).all()
    registros_sin_filtros = Facturacion2026.query.filter(Facturacion2026.mes.in_(meses)).all()
    jefe_site = filtros.get('jefe_site')
    jefe_site_unico = jefe_site if isinstance(jefe_site, str) else ''

    return jsonify({
        'success': True,
        'year': year,
        'columnas': [{'key': 'total', 'label': year}, *columnas],
        'filtros': {
            'clientes': opciones_filtro({**filtros, 'mes': meses}, 'cliente'),
            'gerentes': opciones_filtro({**filtros, 'mes': meses}, 'gerente'),
            'jefes_site': opciones_filtro({**filtros, 'mes': meses}, 'jefe_site'),
            'campanias': opciones_filtro({**filtros, 'mes': meses}, 'campania'),
            'subcampanias': opciones_filtro({**filtros, 'mes': meses}, 'subcampania'),
            'tipos_negocio': opciones_filtro({**filtros, 'mes': meses}, 'tipo_negocio'),
        },
        'jefes_site': sorted({r.jefe_site for r in registros_sin_filtros if r.jefe_site}),
        'tipos_negocio': sorted({r.tipo_negocio for r in registros_sin_filtros if r.tipo_negocio}),
        'seleccion': filtros,
        'tipo_negocio': filtros.get('tipo_negocio') or '',
        'total_gerencia': matriz_grupos(registros_year, 'gerente', meses),
        'apertura_jefe_site': matriz_grupos(registros_year, 'jefe_site' if not jefe_site_unico else 'campania', meses),
        'jefe_site': jefe_site_unico,
    })


def payload_proyeccion(data):
    cliente = str(data.get('cliente') or '').strip()
    campania = str(data.get('campania') or '').strip()
    mes = str(data.get('mes') or '').strip()
    errores = []

    try:
        year = int(data.get('year') or (mes.split('-')[0] if '-' in mes else datetime.utcnow().year))
    except (TypeError, ValueError):
        year = datetime.utcnow().year
        errores.append('El año no es valido')

    if not cliente:
        errores.append('El cliente es obligatorio')
    if not campania:
        errores.append('La campaña es obligatoria')
    if not mes_valido(mes):
        errores.append('El mes no es valido')
    else:
        mes = mes_valido(mes)
        year = int(mes[:4])

    try:
        porcentaje_cumplimiento = parse_numero(data.get('porcentaje_cumplimiento') if data.get('porcentaje_cumplimiento') not in (None, '') else 100)
    except ValueError:
        porcentaje_cumplimiento = 0
        errores.append('Hay valores numericos con formato invalido')

    jornadas = []
    raw_jornadas = data.get('jornadas') if isinstance(data.get('jornadas'), list) else []
    if not raw_jornadas:
        raw_jornadas = [{
            'dotacion_requerida': data.get('dotacion_requerida'),
            'carga_semanal': data.get('carga_semanal'),
            'carga_horaria': data.get('carga_horaria'),
        }]

    for index, item in enumerate(raw_jornadas, start=1):
        try:
            dotacion = parse_numero(item.get('dotacion_requerida'))
            carga_horaria = parse_numero(item.get('carga_horaria'))
        except (AttributeError, ValueError):
            errores.append(f'La jornada {index} tiene valores numericos invalidos')
            continue
        carga_semanal = normalizar_carga_semanal(item.get('carga_semanal'))
        if dotacion < 0:
            errores.append(f'La dotacion de la jornada {index} no puede ser negativa')
        if carga_horaria < 0:
            errores.append(f'La carga horaria de la jornada {index} no puede ser negativa')
        if dotacion > 0 or carga_horaria > 0:
            jornadas.append({
                'dotacion_requerida': dotacion,
                'carga_semanal': carga_semanal,
                'carga_horaria': carga_horaria,
            })

    if not jornadas:
        errores.append('Debe cargar al menos una jornada con dotacion y carga horaria')
    if porcentaje_cumplimiento < 0:
        errores.append('El porcentaje de cumplimiento no puede ser negativo')

    return {
        'errores': errores,
        'valores': {
            'cliente': cliente,
            'campania': campania,
            'year': year,
            'mes': mes,
            'jornadas': jornadas,
            'porcentaje_cumplimiento': porcentaje_cumplimiento,
        }
    }


def payload_precio(data):
    cliente = str(data.get('cliente') or '').strip()
    campania = str(data.get('campania') or '').strip()
    mes = str(data.get('mes') or '').strip()
    errores = []

    try:
        year = int(data.get('year') or (mes.split('-')[0] if '-' in mes else datetime.utcnow().year))
    except (TypeError, ValueError):
        year = datetime.utcnow().year
        errores.append('El año no es valido')

    if not cliente:
        errores.append('El cliente es obligatorio')
    if not campania:
        errores.append('La campaña es obligatoria')
    if not mes_valido(mes):
        errores.append('El mes no es valido')
    else:
        mes = mes_valido(mes)
        year = int(mes[:4])

    try:
        precio_base = parse_numero(data.get('precio_base'))
        alcance_porcentaje = parse_numero(data.get('alcance_porcentaje') if data.get('alcance_porcentaje') not in (None, '') else 100)
        importe_fijo_mensual = parse_numero(data.get('importe_fijo_mensual') if data.get('importe_fijo_mensual') not in (None, '') else 0)
    except ValueError:
        precio_base = 0
        alcance_porcentaje = 0
        importe_fijo_mensual = 0
        errores.append('Hay valores numericos con formato invalido')

    if precio_base < 0:
        errores.append('El precio no puede ser negativo')
    if alcance_porcentaje < 0:
        errores.append('El alcance no puede ser negativo')
    if importe_fijo_mensual < 0:
        errores.append('El pago mensual fijo no puede ser negativo')

    return {
        'errores': errores,
        'valores': {
            'site': str(data.get('site') or '').strip(),
            'cliente': cliente,
            'campania': campania,
            'year': year,
            'mes': mes,
            'precio_base': precio_base,
            'alcance_porcentaje': alcance_porcentaje,
            'importe_fijo_mensual': importe_fijo_mensual,
        }
    }


def headers_template_precios(year):
    meses = [
        f'{label}-{str(year)[-2:]}'
        for _, label in MESES_PROYECCION
    ]
    fijos = [
        f'Fijo {label}-{str(year)[-2:]}'
        for _, label in MESES_PROYECCION
    ]
    return ['Site', 'Cliente'] + meses + fijos


def header_mes_precio(header):
    texto = normalizar_header(header)
    if texto.startswith('fijo '):
        return None
    partes = texto.split('-')
    if len(partes) != 2:
        return None
    labels = {label: numero for numero, label in MESES_PROYECCION}
    mes_numero = labels.get(partes[0])
    if not mes_numero:
        return None
    try:
        year = int(partes[1])
    except ValueError:
        return None
    year += 2000 if year < 100 else 0
    return f'{year}-{mes_numero}'


def header_mes_fijo_precio(header):
    texto = normalizar_header(header)
    if not texto.startswith('fijo '):
        return None
    return header_mes_precio(texto.replace('fijo ', '', 1))


def resolver_cliente_campania_precio(site, nombre):
    site_normalizado = normalizar_header(site)
    nombre_normalizado = normalizar_header(nombre)
    asignacion = AsignacionComercial.query.filter_by(activa=True).filter(
        func.lower(AsignacionComercial.gerente) == str(site or '').strip().lower(),
    ).filter(
        func.lower(AsignacionComercial.campania) == str(nombre or '').strip().lower(),
    ).first()
    if not asignacion:
        asignaciones = AsignacionComercial.query.filter_by(activa=True).all()
        for candidata in asignaciones:
            if site_normalizado and normalizar_header(candidata.gerente) != site_normalizado:
                continue
            if normalizar_header(candidata.campania) == nombre_normalizado or normalizar_header(candidata.cliente) == nombre_normalizado:
                asignacion = candidata
                break
    if asignacion:
        return asignacion.cliente, asignacion.campania
    return nombre, nombre


def sites_por_clave_precio(cliente, campania):
    asignacion = AsignacionComercial.query.filter_by(
        activa=True,
        cliente=cliente,
        campania=campania,
    ).first()
    if asignacion:
        return asignacion.gerente or asignacion.jefe_site or ''
    return ''


TIPOS_FERIADO = ('Inamovible', 'Trasladable', 'Puente', 'Manual')


def payload_feriado(data):
    errores = []
    nombre = str(data.get('nombre') or '').strip()
    tipo = str(data.get('tipo') or 'Manual').strip()
    activo = bool(data.get('activo', True))
    fecha_raw = str(data.get('fecha') or '').strip()

    if not nombre:
        errores.append('El nombre del feriado es obligatorio')
    if tipo not in TIPOS_FERIADO:
        errores.append('El tipo de feriado no es valido')
    try:
        fecha = datetime.strptime(fecha_raw, '%Y-%m-%d').date()
    except ValueError:
        fecha = None
        errores.append('La fecha del feriado no es valida')

    return {
        'errores': errores,
        'valores': {
            'nombre': nombre,
            'tipo': tipo,
            'activo': activo,
            'fecha': fecha,
            'year': fecha.year if fecha else None,
        }
    }


@main_bp.route('/api/calendario-operativo', methods=['GET'])
@login_requerido
def api_calendario_operativo():
    year = int(request.args.get('year') or datetime.utcnow().year)
    feriados = FeriadoOperativo.query.filter_by(year=year).order_by(FeriadoOperativo.fecha).all()
    return jsonify({
        'success': True,
        'year': year,
        'tipos': list(TIPOS_FERIADO),
        'feriados': [feriado.to_dict() for feriado in feriados],
    })


@main_bp.route('/api/calendario-operativo', methods=['POST'])
@login_requerido
def api_guardar_feriado():
    data = request.get_json(silent=True) or {}
    normalizado = payload_feriado(data)
    if normalizado['errores']:
        return jsonify({'success': False, 'errores': normalizado['errores']}), 400
    valores = normalizado['valores']
    feriado_id = data.get('id')

    if feriado_id:
        feriado = FeriadoOperativo.query.get_or_404(feriado_id)
        fecha_anterior = feriado.fecha
        duplicado = FeriadoOperativo.query.filter_by(fecha=valores['fecha']).filter(FeriadoOperativo.id != feriado.id).first()
        if duplicado:
            return jsonify({'success': False, 'errores': ['Ya existe un feriado cargado para esa fecha']}), 400
    else:
        feriado = FeriadoOperativo.query.filter_by(fecha=valores['fecha']).first()
        fecha_anterior = None
        if not feriado:
            feriado = FeriadoOperativo()
            db.session.add(feriado)

    for campo, valor in valores.items():
        setattr(feriado, campo, valor)
    db.session.flush()
    recalculadas = recalcular_proyecciones_mes(feriado.year, feriado.fecha.month)
    if fecha_anterior and fecha_anterior != feriado.fecha:
        recalculadas += recalcular_proyecciones_mes(fecha_anterior.year, fecha_anterior.month)
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'Feriado guardado. {recalculadas} proyeccion(es) recalculada(s).',
        'feriado': feriado.to_dict(),
    })


@main_bp.route('/api/calendario-operativo/<int:feriado_id>', methods=['DELETE'])
@login_requerido
def api_eliminar_feriado(feriado_id):
    feriado = FeriadoOperativo.query.get_or_404(feriado_id)
    year = feriado.year
    mes_numero = feriado.fecha.month
    db.session.delete(feriado)
    db.session.flush()
    recalculadas = recalcular_proyecciones_mes(year, mes_numero)
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'Feriado eliminado. {recalculadas} proyeccion(es) recalculada(s).',
    })


@main_bp.route('/api/matriz-precios', methods=['GET'])
@login_requerido
def api_matriz_precios():
    year = int(request.args.get('year') or datetime.utcnow().year)
    meses = [item['value'] for item in opciones_meses_proyeccion(year)]
    registros = ProyeccionPrecio.query.filter(ProyeccionPrecio.mes.in_(meses)).order_by(
        ProyeccionPrecio.cliente,
        ProyeccionPrecio.campania,
        ProyeccionPrecio.mes,
    ).all()
    asociaciones = AsignacionComercial.query.filter_by(activa=True).order_by(
        AsignacionComercial.cliente,
        AsignacionComercial.campania,
    ).all()
    pares = []
    vistos = set()
    sites_por_clave = {}
    for asignacion in asociaciones:
        clave = (asignacion.cliente, asignacion.campania)
        sites_por_clave.setdefault(clave, asignacion.gerente or asignacion.jefe_site or 'Sin site')
        if clave in vistos:
            continue
        vistos.add(clave)
        pares.append({
            'cliente': asignacion.cliente,
            'campania': asignacion.campania,
            'site': asignacion.gerente or asignacion.jefe_site or 'Sin site',
        })
    return jsonify({
        'success': True,
        'year': year,
        'meses': opciones_meses_proyeccion(year),
        'asociaciones': pares,
        'precios': [
            {
                **registro.to_dict(),
                'site': registro.site or sites_por_clave.get((registro.cliente, registro.campania), ''),
                'mes_label': etiqueta_mes_proyeccion(registro.mes),
            }
            for registro in registros
        ],
    })


@main_bp.route('/api/matriz-precios', methods=['POST'])
@login_requerido
def api_guardar_matriz_precio():
    data = request.get_json(silent=True) or {}
    normalizado = payload_precio(data)
    if normalizado['errores']:
        return jsonify({'success': False, 'errores': normalizado['errores']}), 400
    valores = normalizado['valores']
    precio_id = data.get('id')
    if precio_id:
        precio = ProyeccionPrecio.query.get_or_404(precio_id)
        if (
            precio.cliente != valores['cliente']
            or precio.campania != valores['campania']
            or precio.mes != valores['mes']
        ):
            return jsonify({'success': False, 'errores': ['La edición replica ajustes sobre la misma campaña y mes. Para cambiar cliente, campaña o mes, cree un precio nuevo.']}), 400

    guardados = []
    antes = []
    site_asignado = valores.get('site') or sites_por_clave_precio(valores['cliente'], valores['campania']) or ''
    for mes in meses_proyeccion_desde(valores['mes']):
        precio = ProyeccionPrecio.query.filter_by(
            cliente=valores['cliente'],
            campania=valores['campania'],
            mes=mes,
        ).first()
        antes.append(precio.to_dict() if precio else None)
        if not precio:
            precio = ProyeccionPrecio()
            db.session.add(precio)
        precio.site = site_asignado or precio.site or ''
        precio.cliente = valores['cliente']
        precio.campania = valores['campania']
        precio.year = int(mes[:4])
        precio.mes = mes
        precio.precio_base = valores['precio_base']
        precio.alcance_porcentaje = valores['alcance_porcentaje']
        precio.importe_fijo_mensual = valores['importe_fijo_mensual']
        precio.recalcular()
        guardados.append(precio)

    db.session.flush()
    despues = [precio.to_dict() for precio in guardados]
    registrar_historial(
        'edicion' if any(antes) else 'creacion',
        'matriz_precios',
        valores['mes'],
        f'Precios guardados: {valores["cliente"]} / {valores["campania"]} desde {valores["mes"]}',
        antes={'precios': antes},
        despues={'precios': despues},
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'{len(guardados)} precio(s) guardado(s)',
        'precios': [
            {**precio.to_dict(), 'mes_label': etiqueta_mes_proyeccion(precio.mes)}
            for precio in guardados
        ],
    })


@main_bp.route('/api/matriz-precios/inflacion', methods=['POST'])
@login_requerido
def api_aplicar_inflacion_matriz_precios():
    data = request.get_json(silent=True) or {}
    mes = mes_valido(str(data.get('mes') or '').strip())
    errores = []
    if not mes:
        errores.append('El mes no es valido')

    try:
        indice_inflacion = parse_numero(data.get('indice_inflacion') if data.get('indice_inflacion') not in (None, '') else 0)
    except ValueError:
        indice_inflacion = 0
        errores.append('El indice de inflacion tiene un formato invalido')

    if indice_inflacion < -100:
        errores.append('El indice de inflacion no puede ser menor a -100%')

    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    meses_afectados = meses_proyeccion_desde(mes)
    precios = ProyeccionPrecio.query.filter(ProyeccionPrecio.mes.in_(meses_afectados)).order_by(
        ProyeccionPrecio.cliente,
        ProyeccionPrecio.campania,
        ProyeccionPrecio.mes,
    ).all()
    antes = [precio.to_dict() for precio in precios]
    factor_inflacion = 1 + (indice_inflacion / 100)

    for precio in precios:
        precio.precio_base = redondear_moneda(redondear_moneda(precio.precio_base) * factor_inflacion)
        precio.recalcular()

    db.session.flush()
    despues = [precio.to_dict() for precio in precios]
    registrar_historial(
        'edicion',
        'matriz_precios',
        mes,
        f'Inflacion aplicada: {indice_inflacion}% desde {mes}',
        antes={'precios': antes, 'indice_inflacion': indice_inflacion},
        despues={'precios': despues, 'indice_inflacion': indice_inflacion},
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'Inflacion aplicada a {len(precios)} precio(s)',
        'precios': [
            {**precio.to_dict(), 'mes_label': etiqueta_mes_proyeccion(precio.mes)}
            for precio in precios
        ],
    })


@main_bp.route('/api/matriz-precios/<int:precio_id>', methods=['DELETE'])
@login_requerido
def api_eliminar_matriz_precio(precio_id):
    precio = ProyeccionPrecio.query.get_or_404(precio_id)
    antes = precio.to_dict()
    db.session.delete(precio)
    registrar_historial(
        'eliminacion',
        'matriz_precios',
        precio_id,
        f'Precio eliminado: {antes.get("cliente")} / {antes.get("campania")} / {antes.get("mes")}',
        antes={'precios': [antes]},
        despues={'precios': []},
    )
    db.session.commit()
    return jsonify({'success': True, 'mensaje': 'Precio eliminado'})


@main_bp.route('/api/matriz-precios/template', methods=['GET'])
@login_requerido
def api_template_matriz_precios():
    year = int(request.args.get('year') or datetime.utcnow().year)
    meses = [item['value'] for item in opciones_meses_proyeccion(year)]
    registros = ProyeccionPrecio.query.filter(ProyeccionPrecio.mes.in_(meses)).all()
    asociaciones = AsignacionComercial.query.filter_by(activa=True).order_by(
        AsignacionComercial.gerente,
        AsignacionComercial.campania,
    ).all()

    mapa_precios = {
        (registro.cliente, registro.campania, registro.mes): registro.precio_base or 0
        for registro in registros
    }
    mapa_fijos = {
        (registro.cliente, registro.campania, registro.mes): registro.importe_fijo_mensual or ''
        for registro in registros
        if registro.importe_fijo_mensual
    }
    sites_precios = {
        (registro.cliente, registro.campania): registro.site or ''
        for registro in registros
        if registro.site
    }
    filas = []
    vistos = set()
    for asignacion in asociaciones:
        clave = (asignacion.cliente, asignacion.campania)
        if clave in vistos:
            continue
        vistos.add(clave)
        filas.append([
            sites_precios.get(clave) or asignacion.gerente or asignacion.jefe_site or '',
            asignacion.campania,
            *[
                mapa_precios.get((asignacion.cliente, asignacion.campania, mes), '')
                for mes in meses
            ],
            *[
                mapa_fijos.get((asignacion.cliente, asignacion.campania, mes), '')
                for mes in meses
            ],
        ])

    for registro in registros:
        clave = (registro.cliente, registro.campania)
        if clave in vistos:
            continue
        vistos.add(clave)
        filas.append([
            sites_precios.get(clave, ''),
            registro.campania or registro.cliente,
            *[
                mapa_precios.get((registro.cliente, registro.campania, mes), '')
                for mes in meses
            ],
            *[
                mapa_fijos.get((registro.cliente, registro.campania, mes), '')
                for mes in meses
            ],
        ])

    if not filas:
        filas.append(['Ej: Gerencia Multicampaña', 'Ej: Assurant', 13662.53, 13662.53, 13662.53, '', '', '', '', '', '', '', '', '', 250000, 250000, 250000, '', '', '', '', '', '', '', '', ''])

    contenido = crear_xlsx(headers_template_precios(year), filas)
    return Response(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="plantilla_precios_{year}.xlsx"'}
    )


@main_bp.route('/api/matriz-precios/importar', methods=['POST'])
@login_requerido
def api_importar_matriz_precios():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'success': False, 'errores': ['Seleccione un archivo para importar']}), 400

    nombre = archivo.filename.lower()
    contenido_bytes = archivo.read()
    try:
        if nombre.endswith('.xlsx'):
            filas = filas_desde_xlsx(contenido_bytes)
        elif nombre.endswith('.csv'):
            filas = filas_desde_csv(decodificar_texto_importacion(contenido_bytes))
        else:
            return jsonify({'success': False, 'errores': ['Use un archivo .xlsx o .csv con el template de precios']}), 400
    except Exception:
        return jsonify({'success': False, 'errores': ['No pude leer el archivo. Descargue nuevamente el template y vuelva a completarlo.']}), 400

    if len(filas) < 2:
        return jsonify({'success': False, 'errores': ['No se encontraron filas para importar']}), 400

    headers = [normalizar_header(celda) for celda in filas[0]]
    mapa = {header: index for index, header in enumerate(headers)}
    site_index = mapa.get('site')
    cliente_index = mapa.get('cliente')
    if site_index is None or cliente_index is None:
        return jsonify({'success': False, 'errores': ['El template debe tener las columnas Site y Cliente']}), 400

    columnas_mes = []
    columnas_fijo = []
    for index, header_original in enumerate(filas[0]):
        mes = header_mes_precio(header_original)
        if mes:
            columnas_mes.append((index, mes))
        mes_fijo = header_mes_fijo_precio(header_original)
        if mes_fijo:
            columnas_fijo.append((index, mes_fijo))
    if not columnas_mes:
        return jsonify({'success': False, 'errores': ['No encontre columnas de meses con formato ene-26, feb-26, etc.']}), 400

    errores = []
    guardados = []
    antes = []
    for numero_fila, fila in enumerate(filas[1:], start=2):
        if not any(str(celda or '').strip() for celda in fila):
            continue
        site = str(fila[site_index] if site_index < len(fila) else '').strip()
        nombre_cliente = str(fila[cliente_index] if cliente_index < len(fila) else '').strip()
        if normalizar_header(site).startswith('ej:') or normalizar_header(nombre_cliente).startswith('ej:'):
            continue
        if not nombre_cliente:
            errores.append(f'Fila {numero_fila}: Cliente es obligatorio')
            continue
        cliente, campania = resolver_cliente_campania_precio(site, nombre_cliente)
        meses_a_importar = sorted({mes for _, mes in columnas_mes} | {mes for _, mes in columnas_fijo})
        for mes in meses_a_importar:
            precio_columna = next((index for index, mes_columna in columnas_mes if mes_columna == mes), None)
            fijo_columna = next((index for index, mes_columna in columnas_fijo if mes_columna == mes), None)
            fijo_presente = fijo_columna is not None
            valor = fila[precio_columna] if precio_columna is not None and precio_columna < len(fila) else ''
            valor_fijo = fila[fijo_columna] if fijo_columna is not None and fijo_columna < len(fila) else ''
            precio_con_valor = valor not in (None, '') and str(valor).strip() != ''
            fijo_con_valor = fijo_presente and valor_fijo not in (None, '') and str(valor_fijo).strip() != ''
            if (
                not precio_con_valor
                and not fijo_con_valor
            ):
                continue
            try:
                precio_base = parse_numero(valor) if precio_con_valor else 0
                importe_fijo_mensual = parse_numero(valor_fijo) if fijo_con_valor else 0
            except ValueError:
                errores.append(f'Fila {numero_fila}, {mes}: precio o fijo invalido')
                continue
            registro = ProyeccionPrecio.query.filter_by(
                cliente=cliente,
                campania=campania,
                mes=mes,
            ).first()
            antes.append(registro.to_dict() if registro else None)
            if not registro:
                registro = ProyeccionPrecio()
                db.session.add(registro)
            registro.site = site
            registro.cliente = cliente
            registro.campania = campania
            registro.year = int(mes[:4])
            registro.mes = mes
            if precio_con_valor:
                registro.precio_base = precio_base
            elif not registro.id:
                registro.precio_base = 0
            if precio_con_valor or not registro.id:
                registro.alcance_porcentaje = 100
            if fijo_con_valor:
                registro.importe_fijo_mensual = importe_fijo_mensual
            elif not registro.id:
                registro.importe_fijo_mensual = 0
            registro.recalcular()
            guardados.append(registro)

    if errores:
        return jsonify({'success': False, 'errores': errores[:30]}), 400
    if not guardados:
        return jsonify({'success': False, 'errores': ['No hay precios validos para importar']}), 400

    db.session.flush()
    despues = [registro.to_dict() for registro in guardados]
    registrar_historial(
        'edicion' if any(antes) else 'creacion',
        'matriz_precios',
        ','.join(sorted({str(registro.year) for registro in guardados})),
        f'Importacion de precios: {len(guardados)} registro(s)',
        antes={'precios': antes},
        despues={'precios': despues},
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'{len(guardados)} precio(s) importado(s)',
        'years': sorted({registro.year for registro in guardados}),
    })


def construir_resumen_proyeccion_data(year):
    meses_info = opciones_meses_proyeccion(year)
    meses = [item['value'] for item in meses_info]

    asociaciones = AsignacionComercial.query.filter_by(activa=True).all()
    sites_por_clave = {}
    sites_por_nombre = {}
    for asignacion in asociaciones:
        site_asignado = asignacion.gerente or asignacion.jefe_site or 'Sin site'
        sites_por_clave.setdefault((asignacion.cliente, asignacion.campania), site_asignado)
        sites_por_nombre.setdefault(normalizar_header(asignacion.campania), site_asignado)
        sites_por_nombre.setdefault(normalizar_header(asignacion.cliente), site_asignado)

    proyecciones = ProyeccionMatriz.query.filter(ProyeccionMatriz.mes.in_(meses)).all()
    precios = ProyeccionPrecio.query.filter(ProyeccionPrecio.mes.in_(meses)).all()
    precios_por_clave = {}
    precios_por_nombre = {}
    for precio in precios:
        site_precio = (
            (precio.site or '').strip()
            or sites_por_clave.get((precio.cliente, precio.campania))
            or sites_por_nombre.get(normalizar_header(precio.campania))
            or sites_por_nombre.get(normalizar_header(precio.cliente))
        )
        precios_por_clave[(precio.cliente, precio.campania, precio.mes)] = precio
        precios_por_nombre.setdefault((normalizar_header(precio.campania), precio.mes), precio)
        precios_por_nombre.setdefault((normalizar_header(precio.cliente), precio.mes), precio)

    filas = []
    total_general = {mes: 0 for mes in meses}
    totales_por_site = {}

    for proyeccion in proyecciones:
        clave = (proyeccion.cliente, proyeccion.campania)
        precio = (
            precios_por_clave.get((proyeccion.cliente, proyeccion.campania, proyeccion.mes))
            or precios_por_nombre.get((normalizar_header(proyeccion.campania), proyeccion.mes))
            or precios_por_nombre.get((normalizar_header(proyeccion.cliente), proyeccion.mes))
        )
        if not precio:
            continue
        site = (
            (precio.site or '').strip()
            or sites_por_clave.get(clave)
            or sites_por_nombre.get(normalizar_header(proyeccion.campania))
            or sites_por_nombre.get(normalizar_header(proyeccion.cliente))
            or 'Next Gen'
        )
        valor = (proyeccion.horas_proyectadas or 0) * (precio.precio_final or 0)
        fila_clave = (site, proyeccion.cliente, proyeccion.campania, 'Horas')
        fila = next((item for item in filas if item['clave'] == fila_clave), None)
        if not fila:
            fila = {
                'clave': fila_clave,
                'site': site,
                'cliente': proyeccion.cliente,
                'campania': proyeccion.campania,
                'concepto': 'Horas',
                'meses': {mes: 0 for mes in meses},
                'total': 0,
            }
            filas.append(fila)
        fila['meses'][proyeccion.mes] += valor
        fila['total'] += valor
        total_general[proyeccion.mes] += valor
        totales_por_site.setdefault(site, {mes: 0 for mes in meses})
        totales_por_site[site][proyeccion.mes] += valor

    for precio in precios:
        valor = precio.importe_fijo_mensual or 0
        if valor <= 0:
            continue
        clave = (precio.cliente, precio.campania)
        site = (
            (precio.site or '').strip()
            or sites_por_clave.get(clave)
            or sites_por_nombre.get(normalizar_header(precio.campania))
            or sites_por_nombre.get(normalizar_header(precio.cliente))
            or 'Sin site'
        )
        fila_clave = (site, precio.cliente, precio.campania, 'Fijo mensual')
        fila = next((item for item in filas if item['clave'] == fila_clave), None)
        if not fila:
            fila = {
                'clave': fila_clave,
                'site': site,
                'cliente': precio.cliente,
                'campania': precio.campania,
                'concepto': 'Fijo mensual',
                'meses': {mes: 0 for mes in meses},
                'total': 0,
            }
            filas.append(fila)
        fila['meses'][precio.mes] += valor
        fila['total'] += valor
        total_general[precio.mes] += valor
        totales_por_site.setdefault(site, {mes: 0 for mes in meses})
        totales_por_site[site][precio.mes] += valor

    filas_ordenadas = []
    for site in sorted({fila['site'] for fila in filas}):
        grupo = sorted(
            [fila for fila in filas if fila['site'] == site],
            key=lambda item: (item['campania'], item['concepto']),
        )
        filas_ordenadas.extend(grupo)
        total_site = totales_por_site.get(site, {mes: 0 for mes in meses})
        filas_ordenadas.append({
            'site': site,
            'cliente': '',
            'campania': site,
            'concepto': 'Total',
            'tipo': 'total_site',
            'meses': total_site,
            'total': sum(total_site.values()),
        })

    return {
        'success': True,
        'year': year,
        'meses': meses_info,
        'filas': [
            {
                'site': fila['site'],
                'cliente': fila.get('cliente') or '',
                'campania': fila['campania'],
                'concepto': fila['concepto'],
                'tipo': fila.get('tipo', 'detalle'),
                'meses': {mes: round(fila['meses'].get(mes, 0), 2) for mes in meses},
                'total': round(fila.get('total', 0), 2),
            }
            for fila in filas_ordenadas
        ],
        'total_general': {
            'meses': {mes: round(total_general.get(mes, 0), 2) for mes in meses},
            'total': round(sum(total_general.values()), 2),
        },
    }


@main_bp.route('/api/resumen-proyeccion', methods=['GET'])
@login_requerido
def api_resumen_proyeccion():
    year = int(request.args.get('year') or datetime.utcnow().year)
    return jsonify(construir_resumen_proyeccion_data(year))


def numero_seguro(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0


def site_por_proyeccion(cliente, campania, sites_por_clave, sites_por_nombre):
    return (
        sites_por_clave.get((cliente, campania))
        or sites_por_nombre.get(normalizar_header(campania))
        or sites_por_nombre.get(normalizar_header(cliente))
        or 'Sin site'
    )


def construir_control_proyecciones_data(year):
    meses_info = opciones_meses_proyeccion(year)
    meses = [item['value'] for item in meses_info]
    asociaciones = AsignacionComercial.query.filter_by(activa=True).all()
    sites_por_clave = {}
    sites_por_nombre = {}
    for asignacion in asociaciones:
        site = asignacion.gerente or asignacion.jefe_site or 'Sin site'
        sites_por_clave.setdefault((asignacion.cliente, asignacion.campania), site)
        sites_por_nombre.setdefault(normalizar_header(asignacion.campania), site)
        sites_por_nombre.setdefault(normalizar_header(asignacion.cliente), site)

    proyecciones = ProyeccionMatriz.query.filter(ProyeccionMatriz.mes.in_(meses)).order_by(
        ProyeccionMatriz.cliente,
        ProyeccionMatriz.campania,
        ProyeccionMatriz.mes,
    ).all()
    filas_por_clave = {}
    for proyeccion in proyecciones:
        site = site_por_proyeccion(proyeccion.cliente, proyeccion.campania, sites_por_clave, sites_por_nombre)
        clave = (site, proyeccion.cliente, proyeccion.campania)
        fila = filas_por_clave.setdefault(clave, {
            'site': site,
            'cliente': proyeccion.cliente,
            'campania': proyeccion.campania,
            'horas': {mes: 0 for mes in meses},
            'dotaciones': {mes: 0 for mes in meses},
            'total_horas': 0,
            'total_dotaciones': 0,
        })
        fila['horas'][proyeccion.mes] += proyeccion.horas_proyectadas or 0
        fila['dotaciones'][proyeccion.mes] += proyeccion.dotacion_requerida or 0

    filas = []
    total_horas = {mes: 0 for mes in meses}
    total_dotaciones = {mes: 0 for mes in meses}
    for clave in sorted(filas_por_clave):
        fila = filas_por_clave[clave]
        fila['horas'] = {mes: round(fila['horas'][mes], 2) for mes in meses}
        fila['dotaciones'] = {mes: round(fila['dotaciones'][mes], 2) for mes in meses}
        fila['total_horas'] = round(sum(fila['horas'].values()), 2)
        fila['total_dotaciones'] = round(sum(fila['dotaciones'].values()), 2)
        for mes in meses:
            total_horas[mes] += fila['horas'][mes]
            total_dotaciones[mes] += fila['dotaciones'][mes]
        filas.append(fila)

    return {
        'filas': filas,
        'total_horas': {
            'meses': {mes: round(total_horas[mes], 2) for mes in meses},
            'total': round(sum(total_horas.values()), 2),
        },
        'total_dotaciones': {
            'meses': {mes: round(total_dotaciones[mes], 2) for mes in meses},
            'total': round(sum(total_dotaciones.values()), 2),
        },
    }


def construir_variable_data(year):
    resumen_data = construir_resumen_proyeccion_data(year)
    meses_info = resumen_data['meses']
    meses = [item['value'] for item in meses_info]
    base_por_clave = {}

    for fila in resumen_data['filas']:
        if fila.get('tipo') == 'total_site':
            continue
        clave = (fila.get('site') or '', fila.get('cliente') or '', fila.get('campania') or '')
        base = base_por_clave.setdefault(clave, {
            'site': fila.get('site') or '',
            'cliente': fila.get('cliente') or '',
            'campania': fila.get('campania') or '',
            'meses': {mes: 0 for mes in meses},
            'total_base': 0,
        })
        for mes in meses:
            base['meses'][mes] += numero_seguro(fila.get('meses', {}).get(mes))
        base['total_base'] += numero_seguro(fila.get('total'))

    variables = VariableCampania.query.filter(VariableCampania.mes.in_(meses)).all()
    variables_por_clave = {
        (variable.site or '', variable.cliente, variable.campania, variable.mes): variable
        for variable in variables
    }

    filas = []
    total_general = {mes: 0 for mes in meses}
    for clave in sorted(base_por_clave):
        base = base_por_clave[clave]
        porcentajes = {}
        importes = {}
        total = 0
        for mes in meses:
            variable = variables_por_clave.get((base['site'], base['cliente'], base['campania'], mes))
            porcentaje = variable.porcentaje if variable else 0
            importe = redondear_moneda(base['meses'][mes] * (porcentaje / 100))
            porcentajes[mes] = round(porcentaje or 0, 2)
            importes[mes] = importe
            total += importe
            total_general[mes] += importe
        filas.append({
            'site': base['site'],
            'cliente': base['cliente'],
            'campania': base['campania'],
            'base_meses': {mes: round(base['meses'][mes], 2) for mes in meses},
            'porcentajes': porcentajes,
            'meses': importes,
            'total_base': round(base['total_base'], 2),
            'total': round(total, 2),
        })

    return {
        'success': True,
        'year': year,
        'meses': meses_info,
        'campanias': [
            {
                'site': fila['site'],
                'cliente': fila['cliente'],
                'campania': fila['campania'],
                'label': f"{fila['site']} / {fila['cliente']} / {fila['campania']}",
            }
            for fila in filas
        ],
        'filas': filas,
        'total_general': {
            'meses': {mes: round(total_general.get(mes, 0), 2) for mes in meses},
            'total': round(sum(total_general.values()), 2),
        },
    }


@main_bp.route('/api/variables', methods=['GET'])
@login_requerido
def api_variables():
    year = int(request.args.get('year') or datetime.utcnow().year)
    return jsonify(construir_variable_data(year))


@main_bp.route('/api/control-proyecciones', methods=['GET'])
@login_requerido
def api_control_proyecciones():
    year = int(request.args.get('year') or datetime.utcnow().year)
    meses_info = opciones_meses_proyeccion(year)
    data = construir_control_proyecciones_data(year)
    data.update({
        'success': True,
        'year': year,
        'meses': meses_info,
    })
    return jsonify(data)


@main_bp.route('/api/variables', methods=['POST'])
@login_requerido
def api_guardar_variable():
    data = request.get_json(silent=True) or {}
    mes = mes_valido(str(data.get('mes') or '').strip())
    errores = []
    if not mes:
        errores.append('El mes no es valido')

    site = str(data.get('site') or '').strip()
    cliente = str(data.get('cliente') or '').strip()
    campania = str(data.get('campania') or '').strip()
    if not cliente:
        errores.append('El cliente es obligatorio')
    if not campania:
        errores.append('La campaña es obligatoria')

    try:
        porcentaje = parse_numero(data.get('porcentaje') if data.get('porcentaje') not in (None, '') else 0)
    except ValueError:
        porcentaje = 0
        errores.append('El porcentaje tiene un formato invalido')

    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    year = int(mes[:4])
    base_data = construir_variable_data(year)
    campania_valida = next((
        item for item in base_data['campanias']
        if item['site'] == site and item['cliente'] == cliente and item['campania'] == campania
    ), None)
    if not campania_valida:
        return jsonify({'success': False, 'errores': ['La campaña no existe en Facturación horas para el año seleccionado']}), 400

    variable = VariableCampania.query.filter_by(cliente=cliente, campania=campania, mes=mes).first()
    antes = variable.to_dict() if variable else None
    if not variable:
        variable = VariableCampania()
        db.session.add(variable)
    variable.site = site
    variable.cliente = cliente
    variable.campania = campania
    variable.year = year
    variable.mes = mes
    variable.porcentaje = porcentaje
    db.session.flush()
    despues = variable.to_dict()
    registrar_historial(
        'edicion' if antes else 'creacion',
        'variables',
        mes,
        f'Variable guardada: {cliente} / {campania} / {mes}',
        antes=antes,
        despues=despues,
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': 'Variable guardada',
        'variable': variable.to_dict(),
    })


@main_bp.route('/api/matriz-proyecciones', methods=['GET'])
@login_requerido
def api_matriz_proyecciones():
    year = int(request.args.get('year') or datetime.utcnow().year)
    meses = [item['value'] for item in opciones_meses_proyeccion(year)]
    registros = ProyeccionMatriz.query.filter(ProyeccionMatriz.mes.in_(meses)).order_by(
        ProyeccionMatriz.cliente,
        ProyeccionMatriz.campania,
        ProyeccionMatriz.mes,
    ).all()
    asociaciones = AsignacionComercial.query.filter_by(activa=True).order_by(
        AsignacionComercial.cliente,
        AsignacionComercial.campania,
    ).all()
    pares = []
    vistos = set()
    for asignacion in asociaciones:
        clave = (asignacion.cliente, asignacion.campania)
        if clave in vistos:
            continue
        vistos.add(clave)
        pares.append({'cliente': asignacion.cliente, 'campania': asignacion.campania})
    return jsonify({
        'success': True,
        'year': year,
        'meses': opciones_meses_proyeccion(year),
        'asociaciones': pares,
        'feriados': [feriado.to_dict() for feriado in FeriadoOperativo.query.filter_by(year=year, activo=True).all()],
        'cargas_semanales': list(CARGAS_SEMANALES_PROYECCION),
        'proyecciones': [
            {**registro.to_dict(), 'mes_label': etiqueta_mes_proyeccion(registro.mes)}
            for registro in registros
        ],
    })


@main_bp.route('/api/matriz-proyecciones', methods=['POST'])
@login_requerido
def api_guardar_matriz_proyeccion():
    data = request.get_json(silent=True) or {}
    normalizado = payload_proyeccion(data)
    if normalizado['errores']:
        return jsonify({'success': False, 'errores': normalizado['errores']}), 400
    valores = normalizado['valores']
    proyeccion_id = data.get('id')
    if proyeccion_id:
        proyeccion = ProyeccionMatriz.query.get_or_404(proyeccion_id)
        if (
            proyeccion.cliente != valores['cliente']
            or proyeccion.campania != valores['campania']
            or proyeccion.mes != valores['mes']
        ):
            return jsonify({'success': False, 'errores': ['La edición replica ajustes sobre la misma campaña y mes. Para cambiar cliente, campaña o mes, cree una proyección nueva.']}), 400

    proyecciones_guardadas = []
    feriados = fechas_feriadas_activas(valores['year'])
    antes_snapshots = []

    for mes in meses_proyeccion_desde(valores['mes']):
        proyeccion = ProyeccionMatriz.query.filter_by(
            cliente=valores['cliente'],
            campania=valores['campania'],
            mes=mes,
        ).first()
        antes_snapshots.append(snapshot_proyeccion(proyeccion))
        if not proyeccion:
            proyeccion = ProyeccionMatriz()
            db.session.add(proyeccion)

        aplicar_calculo_proyeccion(proyeccion, valores, mes, feriados)
        proyecciones_guardadas.append(proyeccion)

    db.session.flush()
    despues_snapshots = [snapshot_proyeccion(proyeccion) for proyeccion in proyecciones_guardadas]
    registrar_historial(
        'edicion' if any(antes_snapshots) else 'creacion',
        'proyeccion_matriz',
        valores['mes'],
        f'Proyecciones guardadas: {valores["cliente"]} / {valores["campania"]} desde {valores["mes"]}',
        antes={'proyecciones': antes_snapshots},
        despues={'proyecciones': despues_snapshots},
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'{len(proyecciones_guardadas)} proyeccion(es) guardada(s)',
        'proyecciones': [
            {**proyeccion.to_dict(), 'mes_label': etiqueta_mes_proyeccion(proyeccion.mes)}
            for proyeccion in proyecciones_guardadas
        ],
    })


@main_bp.route('/api/matriz-proyecciones/<int:proyeccion_id>', methods=['DELETE'])
@login_requerido
def api_eliminar_matriz_proyeccion(proyeccion_id):
    proyeccion = ProyeccionMatriz.query.get_or_404(proyeccion_id)
    antes = snapshot_proyeccion(proyeccion)
    db.session.delete(proyeccion)
    registrar_historial(
        'eliminacion',
        'proyeccion_matriz',
        proyeccion_id,
        f'Proyeccion eliminada: {antes.get("cliente")} / {antes.get("campania")} / {antes.get("mes")}',
        antes={'proyecciones': [antes]},
        despues={'proyecciones': []},
    )
    db.session.commit()
    return jsonify({'success': True, 'mensaje': 'Proyección eliminada'})


@main_bp.route('/api/matriz-proyecciones/eliminar-todo', methods=['POST'])
@login_requerido
def api_eliminar_todas_matriz_proyecciones():
    data = request.get_json(silent=True) or {}
    try:
        year = int(data.get('year') or datetime.utcnow().year)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'errores': ['El año no es valido']}), 400

    meses = [item['value'] for item in opciones_meses_proyeccion(year)]
    proyecciones = ProyeccionMatriz.query.filter(ProyeccionMatriz.mes.in_(meses)).order_by(
        ProyeccionMatriz.cliente,
        ProyeccionMatriz.campania,
        ProyeccionMatriz.mes,
    ).all()
    if not proyecciones:
        return jsonify({'success': False, 'errores': [f'No hay proyecciones cargadas para {year}']}), 404

    antes = [snapshot_proyeccion(proyeccion) for proyeccion in proyecciones]
    for proyeccion in proyecciones:
        db.session.delete(proyeccion)
    registrar_historial(
        'eliminacion',
        'proyeccion_matriz',
        year,
        f'Eliminacion total de proyecciones {year}: {len(proyecciones)} registro(s)',
        antes={'proyecciones': antes},
        despues={'proyecciones': []},
    )
    db.session.flush()
    pendientes = [snapshot for snapshot in antes if existe_proyeccion_snapshot(snapshot)]
    if pendientes:
        db.session.rollback()
        return jsonify({'success': False, 'errores': ['No se pudieron eliminar todas las proyecciones']}), 500
    db.session.commit()
    return jsonify({'success': True, 'mensaje': f'{len(proyecciones)} proyeccion(es) eliminada(s)'})


@main_bp.route('/api/matriz-proyecciones/deshacer-ultimo', methods=['POST'])
@login_requerido
def api_deshacer_ultima_proyeccion():
    usuario = usuario_actual()
    query = HistorialCambio.query.filter(
        HistorialCambio.entidad == 'proyeccion_matriz',
        HistorialCambio.accion != 'deshacer',
    )
    if usuario and not usuario.es_administrador:
        query = query.filter(HistorialCambio.usuario_id == usuario.id)
    item = None
    for candidato in query.order_by(HistorialCambio.creado_en.desc(), HistorialCambio.id.desc()).limit(50).all():
        if not historial_movimiento_deshace(candidato.id):
            item = candidato
            break
    if not item:
        return jsonify({'success': False, 'errores': ['No hay movimientos de proyecciones para deshacer']}), 404
    resultado, status = deshacer_item_historial(item)
    return jsonify(resultado), status


@main_bp.route('/api/matriz-proyecciones/template', methods=['GET'])
@login_requerido
def api_template_matriz_proyecciones():
    year = int(request.args.get('year') or datetime.utcnow().year)
    meses = [item['value'] for item in opciones_meses_proyeccion(year)]
    registros = ProyeccionMatriz.query.filter(ProyeccionMatriz.mes.in_(meses)).order_by(
        ProyeccionMatriz.cliente,
        ProyeccionMatriz.campania,
        ProyeccionMatriz.mes,
    ).all()

    headers = [
        'Cliente', 'Campaña', 'Año', 'Mes',
        'Personas', 'Carga semanal', 'Hs diarias', 'Q dias objetivo',
        'Hs requeridas jornada', 'Dotacion total', 'Hs requeridas total',
        '% cumplimiento', 'Horas proyectadas total',
    ]
    rows = [[
        'Ej: BNA',
        'Ej: BNA Mora',
        year,
        f'{year}-01',
        'Ej: 9',
        'Ej: L a V',
        'Ej: 6',
        'Calculado por sistema',
        'Calculado por sistema',
        'Calculado por sistema',
        'Calculado por sistema',
        'Ej: 100',
        'Calculado por sistema',
    ]]
    for registro in registros:
        jornadas = registro.jornadas or [ProyeccionMatrizJornada(
            dotacion_requerida=registro.dotacion_requerida,
            carga_semanal=registro.carga_semanal,
            carga_horaria=registro.carga_horaria,
            dias_objetivo=registro.dias_objetivo,
            horas_requeridas=registro.horas_requeridas,
        )]
        for jornada in jornadas:
            rows.append([
                registro.cliente,
                registro.campania,
                registro.year,
                registro.mes,
                jornada.dotacion_requerida or 0,
                jornada.carga_semanal or 'L a V',
                jornada.carga_horaria or 0,
                jornada.dias_objetivo or 0,
                round(jornada.horas_requeridas or 0, 2),
                registro.dotacion_requerida or 0,
                round(registro.horas_requeridas or 0, 2),
                registro.porcentaje_cumplimiento or 0,
                round(registro.horas_proyectadas or 0, 2),
            ])

    contenido = crear_xlsx(headers, rows)
    return Response(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="plantilla_proyecciones_{year}.xlsx"'}
    )


@main_bp.route('/api/matriz-proyecciones/importar', methods=['POST'])
@login_requerido
def api_importar_matriz_proyecciones():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        return jsonify({'success': False, 'errores': ['Seleccione un archivo para importar']}), 400

    nombre = archivo.filename.lower()
    contenido_bytes = archivo.read()
    try:
        if nombre.endswith('.xlsx'):
            filas = filas_desde_xlsx(contenido_bytes)
        elif nombre.endswith('.csv'):
            filas = filas_desde_csv(decodificar_texto_importacion(contenido_bytes))
        else:
            return jsonify({'success': False, 'errores': ['Use un archivo .xlsx o .csv generado desde el template']}), 400
    except Exception:
        return jsonify({'success': False, 'errores': ['No pude leer el archivo. Descargue nuevamente el template y vuelva a completarlo.']}), 400

    if len(filas) < 2:
        return jsonify({'success': False, 'errores': ['No se encontraron filas para importar']}), 400

    headers = [normalizar_header(celda) for celda in filas[0]]
    mapa = {header: index for index, header in enumerate(headers)}
    requeridas = {
        'cliente': 'cliente',
        'campana': 'campania',
        'campaña': 'campania',
        'ano': 'year',
        'año': 'year',
        'mes': 'mes',
        'personas': 'dotacion_requerida',
        'carga semanal': 'carga_semanal',
        'hs diarias': 'carga_horaria',
        '% cumplimiento': 'porcentaje_cumplimiento',
        'hs requeridas total': 'horas_requeridas_total',
        'horas requeridas total': 'horas_requeridas_total',
        'horas proyectadas total': 'horas_proyectadas_total',
        'horas proyectadas': 'horas_proyectadas_total',
    }
    columnas = {}
    for header, destino in requeridas.items():
        if header in mapa:
            columnas[destino] = mapa[header]
    faltantes = [campo for campo in ('cliente', 'campania', 'year', 'mes', 'dotacion_requerida', 'carga_semanal', 'carga_horaria') if campo not in columnas]
    if faltantes:
        return jsonify({'success': False, 'errores': [f'Faltan columnas requeridas: {", ".join(faltantes)}']}), 400

    grupos = {}
    errores = []
    for indice, fila in enumerate(filas[1:], start=2):
        if not any(str(celda or '').strip() for celda in fila):
            continue

        def celda(campo):
            posicion = columnas.get(campo)
            return fila[posicion] if posicion is not None and posicion < len(fila) else ''

        cliente = str(celda('cliente') or '').strip()
        if normalizar_header(cliente).startswith('ej:'):
            continue
        campania = str(celda('campania') or '').strip()
        mes = mes_valido(celda('mes'))
        try:
            year = int(float(str(celda('year')).strip()))
            dotacion = parse_numero(celda('dotacion_requerida'))
            carga_horaria = parse_numero(celda('carga_horaria'))
            porcentaje = parse_numero(celda('porcentaje_cumplimiento')) if 'porcentaje_cumplimiento' in columnas and str(celda('porcentaje_cumplimiento')).strip() else 100
            horas_requeridas_total = parse_numero(celda('horas_requeridas_total')) if 'horas_requeridas_total' in columnas and str(celda('horas_requeridas_total')).strip() else None
            horas_proyectadas_total = parse_numero(celda('horas_proyectadas_total')) if 'horas_proyectadas_total' in columnas and str(celda('horas_proyectadas_total')).strip() else None
        except ValueError:
            errores.append(f'Fila {indice}: hay valores numericos invalidos')
            continue
        if not cliente or not campania or not mes:
            errores.append(f'Fila {indice}: cliente, campaña y mes son obligatorios')
            continue
        carga_semanal = normalizar_carga_semanal(celda('carga_semanal'))
        clave = (cliente, campania, mes)
        grupos.setdefault(clave, {
            'cliente': cliente,
            'campania': campania,
            'year': year,
            'mes': mes,
            'porcentaje_cumplimiento': porcentaje,
            'horas_requeridas_total': horas_requeridas_total,
            'horas_proyectadas_total': horas_proyectadas_total,
            'jornadas': [],
        })
        if horas_requeridas_total is not None:
            grupos[clave]['horas_requeridas_total'] = horas_requeridas_total
        if horas_proyectadas_total is not None:
            grupos[clave]['horas_proyectadas_total'] = horas_proyectadas_total
        grupos[clave]['jornadas'].append({
            'dotacion_requerida': dotacion,
            'carga_semanal': carga_semanal,
            'carga_horaria': carga_horaria,
        })

    if errores:
        return jsonify({'success': False, 'errores': errores[:20]}), 400
    if not grupos:
        return jsonify({'success': False, 'errores': ['No hay filas validas para importar']}), 400

    guardadas = []
    antes_snapshots = []
    years = set()
    for valores in grupos.values():
        normalizado = payload_proyeccion(valores)
        if normalizado['errores']:
            errores.extend(normalizado['errores'])
            continue
        datos = normalizado['valores']
        feriados = fechas_feriadas_activas(datos['year'])
        proyeccion = ProyeccionMatriz.query.filter_by(
            cliente=datos['cliente'],
            campania=datos['campania'],
            mes=datos['mes'],
        ).first()
        antes_snapshots.append(snapshot_proyeccion(proyeccion))
        if not proyeccion:
            proyeccion = ProyeccionMatriz()
            db.session.add(proyeccion)
        aplicar_calculo_proyeccion(proyeccion, datos, datos['mes'], feriados)
        horas_requeridas_total = valores.get('horas_requeridas_total')
        horas_proyectadas_total = valores.get('horas_proyectadas_total')
        if horas_requeridas_total is not None and horas_requeridas_total >= 0:
            proyeccion.horas_requeridas = horas_requeridas_total
            if horas_proyectadas_total is not None and horas_requeridas_total > 0:
                proyeccion.porcentaje_cumplimiento = (horas_proyectadas_total / horas_requeridas_total) * 100
        elif horas_proyectadas_total is not None and horas_proyectadas_total >= 0:
            proyeccion.horas_requeridas = horas_proyectadas_total
            proyeccion.porcentaje_cumplimiento = 100
        guardadas.append(proyeccion)
        years.add(datos['year'])

    if errores:
        return jsonify({'success': False, 'errores': errores[:20]}), 400
    db.session.flush()
    despues_snapshots = [snapshot_proyeccion(proyeccion) for proyeccion in guardadas]
    registrar_historial(
        'edicion' if any(antes_snapshots) else 'creacion',
        'proyeccion_matriz',
        ','.join(str(year) for year in sorted(years)),
        f'Importacion de proyecciones: {len(guardadas)} registro(s)',
        antes={'proyecciones': antes_snapshots},
        despues={'proyecciones': despues_snapshots},
    )
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': f'{len(guardadas)} proyeccion(es) importada(s)',
        'years': sorted(years),
    })


@main_bp.route('/api/alertas', methods=['GET'])
@login_requerido
def api_alertas():
    """Alertas automaticas segun los datos filtrados."""
    registros = registros_filtrados()
    alertas = []

    if not registros:
        alertas.append({
            'tipo': 'info',
            'titulo': 'Sin datos para el filtro',
            'detalle': 'No hay registros que coincidan con la seleccion actual.'
        })
        return jsonify({'success': True, 'alertas': alertas})

    resumen = resumen_registros(registros)
    if resumen['porcentaje_cumplimiento'] < 95:
        alertas.append({
            'tipo': 'danger',
            'titulo': 'Cumplimiento bajo',
            'detalle': f"El cumplimiento general es {resumen['porcentaje_cumplimiento']}%."
        })
    elif resumen['porcentaje_cumplimiento'] < 100:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Cumplimiento debajo del objetivo',
            'detalle': f"El cumplimiento general esta en {resumen['porcentaje_cumplimiento']}%."
        })

    if resumen['desvio'] < 0:
        alertas.append({
            'tipo': 'danger',
            'titulo': 'Desvio negativo',
            'detalle': f"El desvio acumulado es {round(resumen['desvio'], 2)}."
        })

    exceso_horas = [r for r in registros if r.horas_facturadas > r.horas_objetivo]
    if exceso_horas:
        alertas.append({
            'tipo': 'warning',
            'titulo': 'Horas facturadas sobre objetivo',
            'detalle': f"{len(exceso_horas)} registro(s) superan las horas objetivo."
        })

    grupos = {}
    for registro in registros:
        grupos.setdefault(registro.cliente, []).append(registro)
    clientes_en_riesgo = []
    for cliente, registros_cliente in grupos.items():
        resumen_cliente = resumen_registros(registros_cliente)
        if resumen_cliente['porcentaje_cumplimiento'] < 95:
            clientes_en_riesgo.append({'cliente': cliente, **resumen_cliente})
    if clientes_en_riesgo:
        nombres = ', '.join(item['cliente'] for item in clientes_en_riesgo[:3])
        alertas.append({
            'tipo': 'danger',
            'titulo': 'Clientes en riesgo',
            'detalle': f"{nombres} por debajo de 95% de cumplimiento."
        })

    if not alertas:
        alertas.append({
            'tipo': 'success',
            'titulo': 'Operacion dentro de objetivo',
            'detalle': 'No se detectaron desvios criticos en la seleccion actual.'
        })

    return jsonify({'success': True, 'alertas': alertas})


@main_bp.route('/api/exportar_excel', methods=['GET'])
@login_requerido
def api_exportar_excel():
    """Exporta los registros filtrados en un archivo compatible con Excel."""
    registros = aplicar_filtros(Facturacion2026.query, **filtros_request()).order_by(
        Facturacion2026.fecha.desc()
    ).all()

    headers = [
        'Fecha', 'Mes', 'Cliente', 'Gerente', 'Jefe de Site', 'Campaña', 'Sub campaña', 'Tipo de negocio', 'Tipo de VH', 'Horas objetivo',
        'Horas facturadas', 'Horas Penalizacion ADH', 'Valor hora objetivo', 'Valor hora alcanzado', 'Tarificacion', 'Importe fijo facturado', 'Variable Objetivo', 'Variable Productivo',
        '% cumplimiento horas',
        'Objetivo facturacion horas', 'Objetivo facturacion bono', 'Facturacion objetivo',
        'Facturado horas', 'Facturado bono', 'Variable Productivo', 'Penalizaciones por incumplimientos',
        'Next Gen', 'Otros', 'Total facturado', 'Desvio', '% cumplimiento'
    ]
    rows = []
    for r in registros:
        rows.append([
            r.fecha.isoformat(), r.mes, r.cliente, r.gerente or '', r.jefe_site or '',
            r.campania or '', r.subcampania or '', r.tipo_negocio or '', r.tipo_jornada,
            r.horas_objetivo, r.horas_facturadas, r.horas_penalizadas or 0,
            r.valor_hora_objetivo if r.valor_hora_objetivo else r.valor_hora,
            r.valor_hora_alcanzado,
            r.tarifacion or 0,
            r.importe_fijo if r.importe_fijo is not None else '',
            r.variable_objetivo or 0,
            r.variable_productivo or 0,
            round(r.porcentaje_cumplimiento_horas, 2),
            round(r.objetivo_facturacion_horas, 2), round(r.objetivo_facturacion_bono, 2),
            round(r.facturacion_objetivo, 2), round(r.facturado_horas, 2),
            round(r.facturado_bono, 2), round(r.variable_productivo_calculo, 2), round(r.penalizaciones_incumplimientos, 2),
            r.netx_gen or 0, r.otros or 0,
            round(r.total_dashboard, 2),
            round(r.total_dashboard - r.total_teorico, 2),
            round((r.total_dashboard / r.total_teorico * 100) if r.total_teorico > 0 else 0, 2)
        ])

    table_rows = ['<tr>' + ''.join(f'<th>{escape(h)}</th>' for h in headers) + '</tr>']
    for row in rows:
        table_rows.append('<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in row) + '</tr>')

    html = (
        '<html><head><meta charset="utf-8"></head><body>'
        '<table border="1">'
        + ''.join(table_rows) +
        '</table></body></html>'
    )
    filename = f"facturacion_{datetime.now().strftime('%Y%m%d_%H%M')}.xls"
    return Response(
        html,
        content_type='application/vnd.ms-excel; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@main_bp.route('/api/template_carga', methods=['GET'])
@edicion_requerida
def api_template_carga():
    """Descarga una plantilla xlsx para carga masiva."""
    headers = [label for _, label in COLUMNAS_IMPORTACION]
    ayuda_por_campo = {
        'fecha': 'YYYY-MM-DD o DD/MM/YYYY',
        'mes': 'YYYY-MM',
        'cliente': 'Texto',
        'gerente': 'Texto',
        'jefe_site': 'Texto',
        'campania': 'Texto',
        'subcampania': 'Texto',
        'tipo_negocio': 'Opcional',
        'tipo_jornada': 'Diurna, Nocturna, Feriado, Capacitación, Diurnas Feriado, Nocturnas Feriado, horas líder o radio',
        'horas_objetivo': 'Número',
        'horas_facturadas': 'Número',
        'horas_penalizadas': 'Opcional',
        'valor_hora_objetivo': 'Número',
        'valor_hora': 'Número',
    }
    ayuda = [ayuda_por_campo.get(campo, 'Opcional') for campo, _ in COLUMNAS_IMPORTACION]
    contenido = crear_xlsx(headers, [ayuda])
    return Response(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="plantilla_carga_facturacion_tipo_negocio.xlsx"',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
        }
    )


@main_bp.route('/api/importar_datos', methods=['POST'])
@edicion_requerida
def api_importar_datos():
    """Importa registros desde la plantilla Excel/CSV."""
    archivo = request.files.get('archivo')
    if not archivo:
        return jsonify({'success': False, 'errores': ['Debe adjuntar un archivo']}), 400

    try:
        contenido_bytes = archivo.read()
        nombre = (archivo.filename or '').lower()
        if nombre.endswith('.xlsx'):
            filas = filas_desde_xlsx(contenido_bytes)
        else:
            try:
                contenido = contenido_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                contenido = contenido_bytes.decode('cp1252')
            if nombre.endswith('.xls') and '<table' not in contenido.lower():
                return jsonify({
                    'success': False,
                    'errores': ['Ese archivo .xls no es la plantilla esperada. Descargue nuevamente el template .xlsx, complete las filas y vuelva a subirlo.']
                }), 400
            filas = filas_desde_html(contenido) if nombre.endswith('.xls') or '<table' in contenido.lower() else filas_desde_csv(contenido)

        datos = datos_desde_filas(filas)
        if not datos:
            return jsonify({'success': False, 'errores': ['No se encontraron filas para importar. Revise que el archivo tenga encabezados y datos.']}), 400

        confirmar_reemplazo = request.form.get('confirmar_reemplazo') == '1'
        creados = 0
        reemplazados = 0
        errores = []
        items_validos = []
        conflictos_por_clave = {}
        for indice, item in enumerate(datos, start=2):
            if indice == 2 and str(item.get('fecha', '')).startswith('YYYY'):
                continue

            item.setdefault('bonos', 0)
            item.setdefault('horas_penalizadas', 0)
            item['penalizaciones'] = normalizar_importe_ajuste('penalizaciones', item.get('penalizaciones'))
            item.setdefault('netx_gen', 0)
            item.setdefault('otros', 0)
            item.setdefault('tarifacion', None)
            item.setdefault('importe_fijo', None)
            item.setdefault('variable_objetivo', 0)
            item.setdefault('variable_productivo', 0)
            item.setdefault('valor_hora_objetivo', item.get('valor_hora'))

            errores_fila = validar_payload_facturacion(item)
            if errores_fila:
                errores.append(f'Fila {indice}: ' + '; '.join(errores_fila))
                continue
            try:
                existentes = query_reemplazo_importacion(item).all()
                if existentes:
                    clave = clave_reemplazo_importacion(item)
                    conflictos_por_clave.setdefault(
                        clave,
                        detalle_conflicto_importacion(indice, item, existentes)
                    )
                items_validos.append((indice, item, existentes))
            except Exception as exc:
                errores.append(f'Fila {indice}: {exc}')

        if errores:
            db.session.rollback()
            return jsonify({'success': False, 'creados': 0, 'errores': errores[:50]}), 400

        if conflictos_por_clave and not confirmar_reemplazo:
            return jsonify({
                'success': False,
                'requiere_confirmacion': True,
                'mensaje': 'La importacion reemplazaria datos existentes. Confirme para continuar.',
                'conflictos': list(conflictos_por_clave.values()),
                'errores': ['Hay datos existentes que coinciden por fecha, cliente, gerente, jefe de site, campania y sub campania.']
            }), 409

        for indice, item, existentes in items_validos:
            if existentes and confirmar_reemplazo:
                principal = existentes[0]
                antes = snapshot_modelo(principal)
                try:
                    actualizar_registro_facturacion(principal, item)
                    for duplicado in existentes[1:]:
                        db.session.delete(duplicado)
                    despues = snapshot_modelo(principal)
                    registrar_historial(
                        'edicion',
                        'facturacion',
                        principal.id,
                        f'Facturacion reemplazada por importacion: {principal.cliente} / {principal.mes}',
                        antes=antes,
                        despues=despues,
                        detalle=f'Fila {indice}. Coincidencia exacta por fecha y nombres comerciales.',
                    )
                    reemplazados += 1
                except Exception as exc:
                    errores.append(f'Fila {indice}: {exc}')
                continue

            try:
                crear_registro_facturacion(item)
                creados += 1
            except Exception as exc:
                errores.append(f'Fila {indice}: {exc}')

        if errores:
            db.session.rollback()
            return jsonify({'success': False, 'creados': 0, 'errores': errores[:50]}), 400

        if creados == 0 and reemplazados == 0:
            db.session.rollback()
            return jsonify({
                'success': False,
                'creados': 0,
                'errores': [
                    'No se importó ningún registro. La plantilla descargada viene vacía: complete los datos desde la primera fila debajo del encabezado y vuelva a subirla.'
                ]
            }), 400

        db.session.commit()
        partes_mensaje = []
        if creados:
            partes_mensaje.append(f'{creados} creado(s)')
        if reemplazados:
            partes_mensaje.append(f'{reemplazados} reemplazado(s)')
        return jsonify({
            'success': True,
            'creados': creados,
            'reemplazados': reemplazados,
            'mensaje': 'Importacion completada: ' + ', '.join(partes_mensaje)
        })
    except zipfile.BadZipFile:
        db.session.rollback()
        return jsonify({'success': False, 'errores': ['No pude leer el Excel. Descargue nuevamente el template .xlsx y vuelva a completarlo.']}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(exc)]}), 500


@main_bp.route('/api/asignaciones', methods=['GET'])
@edicion_requerida
def api_asignaciones():
    """Lista de asociaciones predefinidas para carga y filtros."""
    solo_activas = request.args.get('activas', '1') != '0'
    query = AsignacionComercial.query
    if solo_activas:
        query = query.filter_by(activa=True)
    asignaciones = query.order_by(
        AsignacionComercial.cliente,
        AsignacionComercial.campania,
        AsignacionComercial.subcampania
    ).all()
    return jsonify({
        'success': True,
        'asignaciones': [asignacion.to_dict() for asignacion in asignaciones]
    })


@main_bp.route('/api/asignaciones/<int:asignacion_id>', methods=['GET'])
@edicion_requerida
def api_obtener_asignacion(asignacion_id):
    """Obtiene una asociacion puntual desde la base."""
    asignacion = AsignacionComercial.query.get_or_404(asignacion_id)
    return jsonify({'success': True, 'asignacion': asignacion.to_dict()})


@main_bp.route('/api/asignaciones', methods=['POST'])
@edicion_requerida
def api_crear_asignacion():
    """Alta de una asociacion cliente/gerente/campaña/sub campaña."""
    return crear_asignacion_desde_request()


@main_bp.route('/api/catalogos/asignaciones', methods=['POST'])
@edicion_requerida
def api_crear_asignacion_catalogos():
    """Alta de datos maestros desde la pantalla de catalogos."""
    return crear_asignacion_desde_request()


def crear_asignacion_desde_request():
    try:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        campos = {
            'cliente': str(data.get('cliente') or '').strip(),
            'gerente': str(data.get('gerente') or '').strip(),
            'jefe_site': str(data.get('jefe_site') or '').strip(),
            'campania': str(data.get('campania') or '').strip(),
            'subcampania': str(data.get('subcampania') or '').strip(),
            'tipo_negocio': str(data.get('tipo_negocio') or '').strip() or None,
        }
        errores = [f'{campo} es obligatorio' for campo, valor in campos.items() if campo != 'tipo_negocio' and not valor]
        if errores:
            return jsonify({'success': False, 'errores': errores}), 400

        existente = AsignacionComercial.query.filter_by(**campos).first()
        if existente:
            existente.activa = True
            db.session.commit()
            return jsonify({'success': True, 'mensaje': 'La asociacion ya existia y quedo activa', 'asignacion': existente.to_dict()})

        asignacion = AsignacionComercial(**campos)
        db.session.add(asignacion)
        db.session.flush()
        try:
            registrar_historial(
                'creacion',
                'asignacion',
                asignacion.id,
                f'Asociacion creada: {asignacion.label}',
                despues=asignacion.to_dict(),
            )
        except Exception as historial_error:
            current_app.logger.exception('No se pudo registrar historial de asignacion: %s', historial_error)
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Asociacion creada correctamente', 'asignacion': asignacion.to_dict()})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Error creando asignacion')
        return jsonify({'success': False, 'errores': [f'No se pudo crear la asociacion: {exc}']}), 500


@main_bp.route('/api/asignaciones/<int:asignacion_id>', methods=['PATCH', 'PUT'])
@edicion_requerida
def api_actualizar_asignacion(asignacion_id):
    data = request.get_json() or {}
    if not validar_confirmacion_accion(data):
        return jsonify({'success': False, 'errores': ['La confirmacion no es valida']}), 403

    asignacion = AsignacionComercial.query.get_or_404(asignacion_id)
    antes = snapshot_modelo(asignacion)
    valores_anteriores = filtros_asignacion(asignacion)
    nuevos_valores = {}
    campos_asociacion = ['cliente', 'gerente', 'jefe_site', 'campania', 'subcampania', 'tipo_negocio']

    for campo in campos_asociacion:
        if campo in data:
            valor = str(data.get(campo) or '').strip()
            if campo == 'tipo_negocio':
                nuevos_valores[campo] = valor or None
                continue
            if not valor:
                return jsonify({'success': False, 'errores': [f'{campo} es obligatorio']}), 400
            nuevos_valores[campo] = valor

    if nuevos_valores:
        valores_finales = {**valores_anteriores, **nuevos_valores}
        duplicada = AsignacionComercial.query.filter_by(**valores_finales).filter(
            AsignacionComercial.id != asignacion.id
        ).first()
        if duplicada:
            return jsonify({'success': False, 'errores': ['Ya existe otra asociación con esos datos']}), 400

        registros_asociados = Facturacion2026.query.filter_by(**valores_anteriores).all()
        for registro in registros_asociados:
            for campo, valor in valores_finales.items():
                setattr(registro, campo, valor)
        for campo, valor in valores_finales.items():
            setattr(asignacion, campo, valor)
    else:
        registros_asociados = []

    if 'activa' in data:
        asignacion.activa = bool(data['activa'])
    db.session.flush()
    despues = snapshot_modelo(asignacion)
    cambios = cambios_entre(antes, despues)
    if cambios:
        registrar_historial(
            'edicion',
            'asignacion',
            asignacion.id,
            f'Asociacion actualizada: {asignacion.label}',
            antes=antes,
            despues=despues,
            detalle=serializar_json(cambios),
        )
    db.session.commit()
    db.session.refresh(asignacion)
    return jsonify({
        'success': True,
        'mensaje': 'Asociacion actualizada correctamente',
        'asignacion': asignacion.to_dict(),
        'registros_actualizados': len(registros_asociados),
        'cambios': cambios,
    })


@main_bp.route('/api/asignaciones/<int:asignacion_id>', methods=['DELETE'])
@eliminacion_requerida
def api_eliminar_asignacion(asignacion_id):
    data = request.get_json() or {}
    if not validar_confirmacion_accion(data):
        return jsonify({'success': False, 'errores': ['La confirmacion no es valida']}), 403

    asignacion = AsignacionComercial.query.get_or_404(asignacion_id)
    antes = snapshot_modelo(asignacion)
    registros_asociados = query_por_asignacion(asignacion).all()
    registrar_historial(
        'eliminacion',
        'asignacion',
        asignacion.id,
        f'Asociacion eliminada: {asignacion.label}',
        antes=antes,
        detalle=f'Se elimino la asociacion y {len(registros_asociados)} carga(s) vinculadas.',
    )
    for registro in registros_asociados:
        db.session.delete(registro)
    db.session.delete(asignacion)
    db.session.commit()
    return jsonify({
        'success': True,
        'mensaje': 'Asociación eliminada',
        'registros_eliminados': len(registros_asociados)
    })


@main_bp.route('/api/seed', methods=['POST'])
@admin_requerido
def api_seed():
    """Endpoint para cargar datos de ejemplo"""
    from app.models import Facturacion2026
    
    # Verificar si ya hay datos
    if Facturacion2026.query.first():
        return jsonify({'success': False, 'mensaje': 'Ya existen datos en la base de datos'}), 400
    
    datos_seed = [
        # Enero 2026
        {'fecha': '2026-01-05', 'cliente': 'Acme Corp', 'tipo_jornada': 'Diurna', 
         'horas_objetivo': 160, 'horas_facturadas': 165, 'valor_hora': 45, 'tarifacion': None, 
         'bonos': 200, 'penalizaciones': 0, 'netx_gen': 50, 'otros': 0},
        {'fecha': '2026-01-12', 'cliente': 'Tech Solutions', 'tipo_jornada': 'Nocturna', 
         'horas_objetivo': 80, 'horas_facturadas': 75, 'valor_hora': 50, 'tarifacion': None, 
         'bonos': 0, 'penalizaciones': 100, 'netx_gen': 0, 'otros': 25},
        {'fecha': '2026-01-20', 'cliente': 'Global Services', 'tipo_jornada': 'Feriado', 
         'horas_objetivo': 160, 'horas_facturadas': 160, 'valor_hora': 42, 'tarifacion': 48, 
         'bonos': 150, 'penalizaciones': 0, 'netx_gen': 0, 'otros': 0},
        
        # Febrero 2026
        {'fecha': '2026-02-03', 'cliente': 'Acme Corp', 'tipo_jornada': 'Capacitación', 
         'horas_objetivo': 160, 'horas_facturadas': 170, 'valor_hora': 45, 'tarifacion': None, 
         'bonos': 350, 'penalizaciones': 0, 'netx_gen': 100, 'otros': 0},
        {'fecha': '2026-02-10', 'cliente': 'Tech Solutions', 'tipo_jornada': 'Diurnas Feriado', 
         'horas_objetivo': 80, 'horas_facturadas': 82, 'valor_hora': 50, 'tarifacion': None, 
         'bonos': 50, 'penalizaciones': 0, 'netx_gen': 0, 'otros': 0},
        {'fecha': '2026-02-18', 'cliente': 'Innovate Ltd', 'tipo_jornada': 'Nocturnas Feriado', 
         'horas_objetivo': 160, 'horas_facturadas': 155, 'valor_hora': 55, 'tarifacion': None, 
         'bonos': 0, 'penalizaciones': 150, 'netx_gen': 0, 'otros': 50},
        
        # Marzo 2026
        {'fecha': '2026-03-02', 'cliente': 'Global Services', 'tipo_jornada': 'horas líder', 
         'horas_objetivo': 160, 'horas_facturadas': 168, 'valor_hora': 42, 'tarifacion': 48, 
         'bonos': 280, 'penalizaciones': 0, 'netx_gen': 75, 'otros': 0},
        {'fecha': '2026-03-09', 'cliente': 'Acme Corp', 'tipo_jornada': 'radio', 
         'horas_objetivo': 160, 'horas_facturadas': 160, 'valor_hora': 45, 'tarifacion': None, 
         'bonos': 100, 'penalizaciones': 0, 'netx_gen': 0, 'otros': 0},
        {'fecha': '2026-03-16', 'cliente': 'Tech Solutions', 'tipo_jornada': 'Diurna', 
         'horas_objetivo': 80, 'horas_facturadas': 78, 'valor_hora': 50, 'tarifacion': None, 
         'bonos': 0, 'penalizaciones': 50, 'netx_gen': 0, 'otros': 0},
        {'fecha': '2026-03-23', 'cliente': 'Digital Dynamics', 'tipo_jornada': 'Nocturna', 
         'horas_objetivo': 160, 'horas_facturadas': 172, 'valor_hora': 52, 'tarifacion': None, 
         'bonos': 400, 'penalizaciones': 0, 'netx_gen': 150, 'otros': 0},
        
        # Abril 2026
        {'fecha': '2026-04-06', 'cliente': 'Innovate Ltd', 'tipo_jornada': 'Feriado', 
         'horas_objetivo': 160, 'horas_facturadas': 158, 'valor_hora': 55, 'tarifacion': None, 
         'bonos': 0, 'penalizaciones': 55, 'netx_gen': 0, 'otros': 0},
        {'fecha': '2026-04-13', 'cliente': 'Acme Corp', 'tipo_jornada': 'Capacitación', 
         'horas_objetivo': 160, 'horas_facturadas': 175, 'valor_hora': 45, 'tarifacion': None, 
         'bonos': 500, 'penalizaciones': 0, 'netx_gen': 200, 'otros': 0},
        {'fecha': '2026-04-20', 'cliente': 'Global Services', 'tipo_jornada': 'Diurnas Feriado', 
         'horas_objetivo': 160, 'horas_facturadas': 160, 'valor_hora': 42, 'tarifacion': 48, 
         'bonos': 150, 'penalizaciones': 0, 'netx_gen': 0, 'otros': 0},
    ]
    gerentes_por_cliente = {
        'Acme Corp': 'Laura Gomez',
        'Tech Solutions': 'Martin Perez',
        'Global Services': 'Sofia Alvarez',
        'Innovate Ltd': 'Diego Torres',
        'Digital Dynamics': 'Valeria Ruiz',
    }
    jefes_site_por_cliente = {
        'Acme Corp': 'Mariana Silva',
        'Tech Solutions': 'Roberto Diaz',
        'Global Services': 'Carolina Mendez',
        'Innovate Ltd': 'Pablo Rios',
        'Digital Dynamics': 'Natalia Castro',
    }
    campanias_por_cliente = {
        'Acme Corp': ('Retencion', 'Empresas premium'),
        'Tech Solutions': ('Soporte', 'Mesa tecnica'),
        'Global Services': ('Operacion 2026', 'Backoffice regional'),
        'Innovate Ltd': ('Crecimiento', 'Nuevas cuentas'),
        'Digital Dynamics': ('Transformacion', 'Automatizacion'),
    }
    
    try:
        for d in datos_seed:
            fecha = datetime.strptime(d['fecha'], '%Y-%m-%d').date()
            mes = fecha.strftime('%Y-%m')
            
            registro = Facturacion2026(
                fecha=fecha,
                mes=mes,
                cliente=d['cliente'],
                gerente=d.get('gerente') or gerentes_por_cliente.get(d['cliente'], 'Sin asignar'),
                jefe_site=d.get('jefe_site') or jefes_site_por_cliente.get(d['cliente'], 'Sin asignar'),
                campania=d.get('campania') or campanias_por_cliente.get(d['cliente'], ('Operacion 2026', 'General'))[0],
                subcampania=d.get('subcampania') or campanias_por_cliente.get(d['cliente'], ('Operacion 2026', 'General'))[1],
                tipo_jornada=d['tipo_jornada'],
                horas_objetivo=d['horas_objetivo'],
                horas_facturadas=d['horas_facturadas'],
                valor_hora_objetivo=d.get('valor_hora_objetivo', d['valor_hora']),
                valor_hora=d['valor_hora'],
                tarifacion=d['tarifacion'],
                importe_fijo=d.get('importe_fijo'),
                variable_productivo=d.get('variable_productivo', 0),
                bonos=d['bonos'],
                penalizaciones=d['penalizaciones'],
                netx_gen=d['netx_gen'],
                otros=d['otros']
            )
            db.session.add(registro)

            campania, subcampania = campanias_por_cliente.get(d['cliente'], ('Operacion 2026', 'General'))
            existe_asignacion = AsignacionComercial.query.filter_by(
                cliente=d['cliente'],
                gerente=gerentes_por_cliente.get(d['cliente'], 'Sin asignar'),
                jefe_site=jefes_site_por_cliente.get(d['cliente'], 'Sin asignar'),
                campania=campania,
                subcampania=subcampania
            ).first()
            if not existe_asignacion:
                db.session.add(AsignacionComercial(
                    cliente=d['cliente'],
                    gerente=gerentes_por_cliente.get(d['cliente'], 'Sin asignar'),
                    jefe_site=jefes_site_por_cliente.get(d['cliente'], 'Sin asignar'),
                    campania=campania,
                    subcampania=subcampania
                ))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': f'Se cargaron {len(datos_seed)} registros de ejemplo'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(e)]}), 500


@main_bp.route('/api/clientes', methods=['GET'])
@login_requerido
def api_clientes():
    """Endpoint para obtener lista de clientes únicos"""
    clientes = db.session.query(Facturacion2026.cliente).distinct().order_by(Facturacion2026.cliente).all()
    return jsonify({
        'success': True,
        'clientes': [c[0] for c in clientes]
    })


# Endpoint para obtener lista de gerentes únicos
@main_bp.route('/api/gerentes', methods=['GET'])
@login_requerido
def api_gerentes():
    gerentes = db.session.query(Facturacion2026.gerente).distinct().order_by(Facturacion2026.gerente).all()
    return jsonify({
        'success': True,
        'gerentes': [g[0] for g in gerentes if g[0]]
    })


@main_bp.route('/api/meses', methods=['GET'])
@login_requerido
def api_meses():
    """Endpoint para obtener lista de meses disponibles"""
    meses = db.session.query(Facturacion2026.mes).distinct().order_by(Facturacion2026.mes).all()
    return jsonify({
        'success': True,
        'meses': [m[0] for m in meses]
    })
