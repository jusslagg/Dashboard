# filepath: app/routes.py
from flask import Blueprint, Response, current_app, redirect, render_template, request, jsonify, session, url_for
from app import db
from app.models import AsignacionComercial, BajaOperativa, Facturacion2026, HistorialCambio, JustificacionAjuste, ROLES_USUARIO, Usuario
from datetime import datetime, timedelta
from sqlalchemy import func
from html import escape
from html.parser import HTMLParser
from functools import wraps
import csv
import io
import json
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

main_bp = Blueprint('main', __name__)
ADMIN_KEY = 'CAT2026'
CLAVE_PRUEBA_ACCIONES = 'PRUEBA2026'
TIPOS_VH = [
    'Diurna',
    'Nocturna',
    'Feriado',
    'Capacitación',
    'Diurnas Feriado',
    'Nocturnas Feriado',
    'horas líder',
    'radio',
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
    ('netx_gen', 'NetX Gen'),
    ('otros', 'Otros'),
]

COLUMNAS_BAJAS_IMPORTACION = [
    ('year', 'Año'),
    ('mes_baja', 'Mes baja'),
    ('campania', 'Campaña'),
    ('motivo_baja', 'Motivo baja'),
    ('cantidad', 'Cantidad'),
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
    'netx_gen': 'netx_gen',
    'otros': 'otros',
}

ALIAS_BAJAS_IMPORTACION = {
    'ano': 'year',
    'año': 'year',
    'year': 'year',
    'mes baja': 'mes_baja',
    'mes de baja': 'mes_baja',
    'mes_baja': 'mes_baja',
    'campana': 'campania',
    'campaña': 'campania',
    'campania': 'campania',
    'motivo baja': 'motivo_baja',
    'motivo de baja': 'motivo_baja',
    'motivo_baja': 'motivo_baja',
    'cantidad': 'cantidad',
    'total': 'cantidad',
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
    return requiere_edicion() or (data or {}).get('clave') == ADMIN_KEY


def validar_confirmacion_accion(data):
    data = data or {}
    usuario = usuario_actual()
    password = str(data.get('password_confirmacion') or '')
    clave = str(data.get('clave') or '')
    if usuario and password and usuario.check_password(password):
        return True
    if current_app.debug and clave == CLAVE_PRUEBA_ACCIONES:
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
    if require_password and len(password) < 8:
        errores.append('La contrasena debe tener al menos 8 caracteres')
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


def mes_baja_valido(valor):
    if valor in (None, ''):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if texto.replace('.', '', 1).isdigit():
        numero = int(float(texto))
        if 1 <= numero <= 12:
            return str(numero)
        try:
            return str(fecha_excel(float(texto)).month)
        except (OverflowError, ValueError):
            return None
    meses_nombre = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'setiembre': 9, 'sep': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12,
    }
    normalizado = normalizar_header(texto)
    if normalizado in meses_nombre:
        return str(meses_nombre[normalizado])
    for formato in ('%Y-%m', '%m/%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return str(datetime.strptime(texto, formato).month)
        except ValueError:
            continue
    return texto


def normalizar_header(valor):
    texto = str(valor or '').strip().lower().replace('_', ' ')
    texto = ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )
    return ' '.join(texto.split())


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


def resolver_header_bajas(valor):
    return ALIAS_BAJAS_IMPORTACION.get(normalizar_header(valor))


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
        tipo_jornada=data['tipo_jornada'],
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
        penalizaciones=parse_numero(data.get('penalizaciones')),
        netx_gen=parse_numero(data.get('netx_gen')),
        otros=parse_numero(data.get('otros')),
    )
    db.session.add(registro)
    guardar_justificaciones(registro, data)
    asegurar_asignacion_desde_registro(registro)
    return registro


def crear_baja_operativa(data):
    year = str(data.get('year') or '2026').strip()
    mes_baja = mes_baja_valido(data.get('mes_baja'))
    campania = str(data.get('campania') or '').strip()
    motivo_baja = str(data.get('motivo_baja') or '').strip()
    cantidad = int(parse_numero(data.get('cantidad') or 1))
    errores = []
    if not year:
        errores.append('El año es obligatorio')
    if not mes_baja:
        errores.append('El mes de baja es obligatorio')
    if not campania:
        errores.append('La campaña es obligatoria')
    if not motivo_baja:
        errores.append('El motivo de baja es obligatorio')
    if cantidad <= 0:
        errores.append('La cantidad debe ser mayor a 0')
    if errores:
        raise ValueError('; '.join(errores))

    baja = BajaOperativa(
        year=year,
        mes_baja=mes_baja,
        campania=campania,
        motivo_baja=motivo_baja,
        cantidad=cantidad,
    )
    db.session.add(baja)
    return baja


def filas_desde_csv(contenido):
    muestra = contenido[:2048]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=';,|\t,')
    except csv.Error:
        dialecto = csv.excel
        dialecto.delimiter = ';'
    return list(csv.reader(io.StringIO(contenido), dialecto))


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


def datos_bajas_desde_filas(filas):
    if not filas:
        return []
    headers = [resolver_header_bajas(header) for header in filas[0]]
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


def normalizar_justificaciones(data):
    items = data.get('justificaciones') or []
    salida = []
    for item in items:
        tipo = str(item.get('tipo', '')).strip()
        descripcion = str(item.get('descripcion', '')).strip()
        cantidad = parse_numero(item.get('cantidad')) if item.get('cantidad') not in (None, '') else 0
        precio = parse_numero(item.get('precio')) if item.get('precio') not in (None, '') else 0
        importe = parse_numero(item.get('importe')) if item.get('importe') not in (None, '') else cantidad * precio
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
            if parse_numero(data.get(tipo)) > 0:
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
        if item['importe'] <= 0:
            errores.append(f'Justificacion {indice}: el importe debe ser mayor a 0')
        if abs(item['importe'] - (item['cantidad'] * item['precio'])) > 0.01:
            errores.append(f'Justificacion {indice}: el importe debe coincidir con cantidad por precio')
        if not item['descripcion']:
            errores.append(f'Justificacion {indice}: la descripcion es obligatoria')
        totales[item['tipo']] += item['importe']

    for tipo, label in TIPOS_JUSTIFICACION.items():
        valor_campo = parse_numero(data.get(tipo))
        if valor_campo > 0 and totales[tipo] == 0:
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
        'penalizaciones': round(sum(r.penalizaciones or 0 for r in registros), 2),
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


def metricas_matriz(registros):
    resumen = resumen_registros(registros)
    facturado_horas = sum(r.facturado_horas for r in registros)
    facturado_bono = sum(r.facturado_bono for r in registros)
    penalizaciones = sum(r.penalizaciones_incumplimientos for r in registros)
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
    desvio_horas = resumen['horas_facturadas'] - resumen['horas_objetivo']
    desvio_horas_monto = facturado_horas - objetivo_horas
    desvio_bono = facturado_bono - objetivo_bono
    desvio_penalizaciones = penalizaciones
    total_objetivo = resumen['total_teorico']
    total_real = facturado_horas + facturado_bono + penalizaciones
    return {
        **resumen,
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
        'bonos_real': round(facturado_bono, 2),
        'penalizaciones_real': round(penalizaciones, 2),
        'desvio_bono': round(desvio_bono, 2),
        'desvio_penalizaciones_bonos': round(desvio_penalizaciones, 2),
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


def resumen_bajas(registros_baja):
    meses = sorted(
        {str(registro.mes_baja) for registro in registros_baja if registro.mes_baja},
        key=lambda valor: int(valor) if str(valor).isdigit() else 99
    )
    motivos = sorted({registro.motivo_baja for registro in registros_baja if registro.motivo_baja})
    campanias = sorted({registro.campania or 'Sin campania' for registro in registros_baja})

    por_mes = []
    por_motivo = []
    total_meses = {mes: 0 for mes in meses}
    total_motivos = {motivo: 0 for motivo in motivos}

    for campania in campanias:
        registros_campania = [r for r in registros_baja if (r.campania or 'Sin campania') == campania]
        fila_mes = {'campania': campania, 'meses': {}, 'total': sum(r.cantidad or 0 for r in registros_campania)}
        for mes in meses:
            cantidad = sum(r.cantidad or 0 for r in registros_campania if str(r.mes_baja or '') == mes)
            fila_mes['meses'][mes] = cantidad
            total_meses[mes] += cantidad
        por_mes.append(fila_mes)

        fila_motivo = {'campania': campania, 'motivos': {}, 'total': sum(r.cantidad or 0 for r in registros_campania)}
        for motivo in motivos:
            cantidad = sum(r.cantidad or 0 for r in registros_campania if r.motivo_baja == motivo)
            fila_motivo['motivos'][motivo] = cantidad
            total_motivos[motivo] += cantidad
        por_motivo.append(fila_motivo)

    return {
        'meses': meses,
        'motivos': motivos,
        'por_mes': por_mes,
        'por_motivo': por_motivo,
        'totales_mes': total_meses,
        'totales_motivo': total_motivos,
        'total': sum(registro.cantidad or 0 for registro in registros_baja),
    }


def validar_payload_facturacion(data):
    errores = []
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
    if horas_penalizadas > horas_facturadas:
        errores.append('Las horas penalizadas no pueden superar las horas facturadas')
    if valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
    if importe_fijo is not None and importe_fijo < 0:
        errores.append('El importe fijo facturado no puede ser negativo')
    if variable_objetivo < 0:
        errores.append('Variable Objetivo no puede ser negativo')
    if data.get('tipo_jornada') and data.get('tipo_jornada') not in TIPOS_VH:
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


@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@main_bp.route('/usuarios')
@edicion_requerida
def usuarios():
    """Vista de administracion de usuarios."""
    return render_template('usuarios.html', roles=ROLES_USUARIO)


@main_bp.route('/historial')
@login_requerido
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
    })


@main_bp.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    email = normalizar_email(data.get('email'))
    password = str(data.get('password', '') or '')

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not usuario.activo or not usuario.check_password(password):
        return jsonify({'success': False, 'errores': ['Email o contrasena incorrectos']}), 401

    session.clear()
    session['usuario_id'] = usuario.id
    return jsonify({'success': True, 'usuario': usuario.to_dict()})


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
    session['usuario_id'] = usuario.id
    return jsonify({'success': True, 'usuario': usuario.to_dict()})


@main_bp.route('/api/usuarios', methods=['GET'])
@edicion_requerida
def api_usuarios():
    usuarios = Usuario.query.order_by(Usuario.creado_en.desc()).all()
    return jsonify({'success': True, 'usuarios': [usuario.to_dict() for usuario in usuarios]})


@main_bp.route('/api/usuarios', methods=['POST'])
@edicion_requerida
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
@edicion_requerida
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
        if len(password) < 8:
            errores.append('La contrasena debe tener al menos 8 caracteres')
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
@login_requerido
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
    if horas_penalizadas > horas_facturadas:
        errores.append('Las horas penalizadas no pueden superar las horas facturadas')
    if valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
    if importe_fijo is not None and importe_fijo < 0:
        errores.append('El importe fijo facturado no puede ser negativo')
    if variable_objetivo < 0:
        errores.append('Variable Objetivo no puede ser negativo')
    if data.get('tipo_jornada') and data.get('tipo_jornada') not in TIPOS_VH:
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
        registro.tipo_jornada = data['tipo_jornada']
        registro.horas_objetivo = float(data.get('horas_objetivo', 0))
        registro.horas_facturadas = float(data.get('horas_facturadas', 0))
        registro.horas_penalizadas = float(data.get('horas_penalizadas', 0) or 0)
        registro.valor_hora_objetivo = float(data.get('valor_hora_objetivo') or data.get('valor_hora', 0))
        registro.valor_hora = float(data.get('valor_hora', 0))
        registro.tarifacion = data.get('tarifacion')
        registro.importe_fijo = parse_numero(data.get('importe_fijo')) if data.get('importe_fijo') not in (None, '') else None
        registro.variable_objetivo = parse_numero(data.get('variable_objetivo'))
        registro.variable_productivo = parse_numero(data.get('variable_productivo'))
        registro.bonos = float(data.get('bonos', 0) or 0)
        registro.penalizaciones = float(data.get('penalizaciones', 0) or 0)
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
        func.sum(Facturacion2026.penalizaciones).label('penalizaciones'),
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
    jefe_site = request.args.get('jefe_site') or ''
    tipo_negocio = request.args.get('tipo_negocio') or ''
    mes_baja = request.args.get('mes_baja') or ''
    motivo_baja = request.args.get('motivo_baja') or ''
    meses = [f'{year}-{numero}' for numero, _ in MESES_MATRIZ]
    columnas = [{'key': mes, 'label': f'{label}-{year[-2:]}'} for mes, (_, label) in zip(meses, MESES_MATRIZ)]

    registros_query = Facturacion2026.query.filter(Facturacion2026.mes.in_(meses))
    if tipo_negocio:
        registros_query = registros_query.filter(Facturacion2026.tipo_negocio == tipo_negocio)
    registros_year = registros_query.all()
    bajas_year = BajaOperativa.query.filter_by(year=year).all()
    jefes_site = sorted({r.jefe_site for r in registros_year if r.jefe_site})
    meses_baja = sorted(
        {str(r.mes_baja) for r in bajas_year if r.mes_baja},
        key=lambda valor: int(valor) if str(valor).isdigit() else 99
    )
    motivos_baja = sorted({r.motivo_baja for r in bajas_year if r.motivo_baja})

    registros_apertura = [
        registro for registro in registros_year
        if not jefe_site or registro.jefe_site == jefe_site
    ]
    registros_baja = [
        registro for registro in bajas_year
        if (not mes_baja or str(registro.mes_baja or '') == mes_baja)
        and (not motivo_baja or registro.motivo_baja == motivo_baja)
    ]

    return jsonify({
        'success': True,
        'year': year,
        'columnas': [{'key': 'total', 'label': year}, *columnas],
        'jefes_site': jefes_site,
        'tipos_negocio': sorted({r.tipo_negocio for r in Facturacion2026.query.filter(Facturacion2026.mes.in_(meses)).all() if r.tipo_negocio}),
        'tipo_negocio': tipo_negocio,
        'meses_baja': meses_baja,
        'motivos_baja': motivos_baja,
        'mes_baja': mes_baja,
        'motivo_baja': motivo_baja,
        'bajas': resumen_bajas(registros_baja),
        'total_gerencia': matriz_grupos(registros_year, 'gerente', meses),
        'apertura_jefe_site': matriz_grupos(registros_apertura, 'jefe_site' if not jefe_site else 'campania', meses),
        'jefe_site': jefe_site,
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
        'NetX Gen', 'Otros', 'Total facturado', 'Desvio', '% cumplimiento'
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


@main_bp.route('/api/template_bajas', methods=['GET'])
@edicion_requerida
def api_template_bajas():
    """Descarga una plantilla independiente para bajas."""
    headers = [label for _, label in COLUMNAS_BAJAS_IMPORTACION]
    ayuda = ['2026', '3', 'Campaña ejemplo', 'Renuncia', '1']
    contenido = crear_xlsx(headers, [ayuda])
    return Response(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="plantilla_bajas.xlsx"'}
    )


@main_bp.route('/api/importar_bajas', methods=['POST'])
@edicion_requerida
def api_importar_bajas():
    """Importa bajas desde una plantilla separada de facturacion."""
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
            filas = filas_desde_html(contenido) if nombre.endswith('.xls') or '<table' in contenido.lower() else filas_desde_csv(contenido)

        datos = datos_bajas_desde_filas(filas)
        if not datos:
            return jsonify({'success': False, 'errores': ['No se encontraron filas de bajas para importar.']}), 400

        creados = 0
        errores = []
        for indice, item in enumerate(datos, start=2):
            if indice == 2 and normalizar_header(item.get('campania')) == 'campana ejemplo':
                continue
            try:
                crear_baja_operativa(item)
                creados += 1
            except Exception as exc:
                errores.append(f'Fila {indice}: {exc}')

        if errores:
            db.session.rollback()
            return jsonify({'success': False, 'creados': 0, 'errores': errores[:50]}), 400
        if creados == 0:
            db.session.rollback()
            return jsonify({'success': False, 'creados': 0, 'errores': ['No se importo ninguna baja.']}), 400

        db.session.commit()
        return jsonify({'success': True, 'creados': creados, 'mensaje': f'Se importaron {creados} baja(s)'})
    except zipfile.BadZipFile:
        db.session.rollback()
        return jsonify({'success': False, 'errores': ['No pude leer el Excel de bajas. Descargue nuevamente el template.']}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(exc)]}), 500


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

        creados = 0
        errores = []
        for indice, item in enumerate(datos, start=2):
            if indice == 2 and str(item.get('fecha', '')).startswith('YYYY'):
                continue

            item.setdefault('bonos', 0)
            item.setdefault('horas_penalizadas', 0)
            item.setdefault('penalizaciones', 0)
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
                crear_registro_facturacion(item)
                creados += 1
            except Exception as exc:
                errores.append(f'Fila {indice}: {exc}')

        if errores:
            db.session.rollback()
            return jsonify({'success': False, 'creados': 0, 'errores': errores[:50]}), 400

        if creados == 0:
            db.session.rollback()
            return jsonify({
                'success': False,
                'creados': 0,
                'errores': [
                    'No se importó ningún registro. La plantilla descargada viene vacía: complete los datos desde la primera fila debajo del encabezado y vuelva a subirla.'
                ]
            }), 400

        db.session.commit()
        return jsonify({'success': True, 'creados': creados, 'mensaje': f'Se importaron {creados} registros'})
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
