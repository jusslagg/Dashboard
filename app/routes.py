# filepath: app/routes.py
from flask import Blueprint, Response, render_template, request, jsonify
from app import db
from app.models import AsignacionComercial, Facturacion2026
from datetime import datetime, timedelta
from sqlalchemy import func, or_
from html import escape
from html.parser import HTMLParser
import csv
import io
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

main_bp = Blueprint('main', __name__)
ADMIN_KEY = 'CAT2026'
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
    ('tipo_jornada', 'Tipo de VH'),
    ('horas_objetivo', 'Horas objetivo'),
    ('horas_facturadas', 'Horas facturadas'),
    ('valor_hora_objetivo', 'Valor hora objetivo'),
    ('valor_hora', 'Valor hora facturado'),
    ('tarifacion', 'Tarifacion'),
    ('bonos', 'Bonos'),
    ('penalizaciones', 'Penalizaciones'),
    ('netx_gen', 'NetX Gen'),
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
    'tipo de vh': 'tipo_jornada',
    'tipo vh': 'tipo_jornada',
    'tipo_jornada': 'tipo_jornada',
    'horas objetivo': 'horas_objetivo',
    'horas_objetivo': 'horas_objetivo',
    'horas facturadas': 'horas_facturadas',
    'horas_facturadas': 'horas_facturadas',
    'valor hora objetivo': 'valor_hora_objetivo',
    'valor_hora_objetivo': 'valor_hora_objetivo',
    'valor hora facturado': 'valor_hora',
    'valor hora': 'valor_hora',
    'valor_hora': 'valor_hora',
    'tarifacion': 'tarifacion',
    'tarifación': 'tarifacion',
    'bonos': 'bonos',
    'penalizaciones': 'penalizaciones',
    'netx gen': 'netx_gen',
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
    return (data or {}).get('clave') == ADMIN_KEY


def aplicar_filtros(
    query,
    mes=None,
    cliente=None,
    gerente=None,
    jefe_site=None,
    campania=None,
    subcampania=None,
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
        if isinstance(cliente, list):
            query = query.filter(or_(*[Facturacion2026.cliente.ilike(f'%{valor}%') for valor in cliente]))
        else:
            query = query.filter(Facturacion2026.cliente.ilike(f'%{cliente}%'))
    if gerente:
        if isinstance(gerente, list):
            query = query.filter(or_(*[Facturacion2026.gerente.ilike(f'%{valor}%') for valor in gerente]))
        else:
            query = query.filter(Facturacion2026.gerente.ilike(f'%{gerente}%'))
    if jefe_site:
        if isinstance(jefe_site, list):
            query = query.filter(or_(*[Facturacion2026.jefe_site.ilike(f'%{valor}%') for valor in jefe_site]))
        else:
            query = query.filter(Facturacion2026.jefe_site.ilike(f'%{jefe_site}%'))
    if campania:
        if isinstance(campania, list):
            query = query.filter(or_(*[Facturacion2026.campania.ilike(f'%{valor}%') for valor in campania]))
        else:
            query = query.filter(Facturacion2026.campania.ilike(f'%{campania}%'))
    if subcampania:
        if isinstance(subcampania, list):
            query = query.filter(or_(*[Facturacion2026.subcampania.ilike(f'%{valor}%') for valor in subcampania]))
        else:
            query = query.filter(Facturacion2026.subcampania.ilike(f'%{subcampania}%'))
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
        tipo_jornada=data['tipo_jornada'],
        horas_objetivo=parse_numero(data.get('horas_objetivo')),
        horas_facturadas=parse_numero(data.get('horas_facturadas')),
        valor_hora_objetivo=parse_numero(data.get('valor_hora_objetivo') or data.get('valor_hora')),
        valor_hora=parse_numero(data.get('valor_hora')),
        tarifacion=parse_numero(data.get('tarifacion')) if data.get('tarifacion') not in (None, '') else None,
        bonos=parse_numero(data.get('bonos')),
        penalizaciones=parse_numero(data.get('penalizaciones')),
        netx_gen=parse_numero(data.get('netx_gen')),
        otros=parse_numero(data.get('otros')),
    )
    db.session.add(registro)
    asegurar_asignacion_desde_registro(registro)
    return registro


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
    }


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
    }


def query_por_asignacion(asignacion):
    return Facturacion2026.query.filter_by(**filtros_asignacion(asignacion))


def resumen_registros(registros):
    total_real = sum(r.total_real for r in registros)
    total_teorico = sum(r.total_teorico for r in registros)
    desvio = total_real - total_teorico
    porcentaje = (total_real / total_teorico * 100) if total_teorico > 0 else 0
    return {
        'horas_objetivo': round(sum(r.horas_objetivo for r in registros), 2),
        'horas_facturadas': round(sum(r.horas_facturadas for r in registros), 2),
        'bonos': round(sum(r.bonos or 0 for r in registros), 2),
        'penalizaciones': round(sum(r.penalizaciones or 0 for r in registros), 2),
        'netx_gen': round(sum(r.netx_gen or 0 for r in registros), 2),
        'otros': round(sum(r.otros or 0 for r in registros), 2),
        'total_real': round(total_real, 2),
        'total_teorico': round(total_teorico, 2),
        'desvio': round(desvio, 2),
        'porcentaje_cumplimiento': round(porcentaje, 2)
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
        valor_hora = parse_numero(data.get('valor_hora'))
        valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo', valor_hora))
    except ValueError:
        errores.append('Hay valores numéricos con formato inválido')
        horas_objetivo = horas_facturadas = valor_hora = valor_hora_objetivo = 0
    if horas_objetivo < 0:
        errores.append('Las horas objetivo no pueden ser negativas')
    if horas_facturadas < 0:
        errores.append('Las horas facturadas no pueden ser negativas')
    if valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
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
    }
    if not all(campos.values()):
        return None
    existente = AsignacionComercial.query.filter_by(**campos).first()
    if existente:
        existente.activa = True
        return existente
    asignacion = AsignacionComercial(**campos)
    db.session.add(asignacion)
    return asignacion


@main_bp.route('/')
def index():
    """Dashboard principal"""
    return render_template('index.html')


@main_bp.route('/cargar')
def cargar():
    """Vista de carga de datos"""
    return render_template('cargar.html')


@main_bp.route('/control')
def control():
    """Vista de control de datos"""
    return render_template('control.html')


@main_bp.route('/comparativo')
def comparativo():
    """Vista comparativa de horas objetivo contra horas facturadas"""
    return render_template('comparativo.html')


@main_bp.route('/catalogos')
def catalogos():
    """Vista de alta de datos maestros"""
    return render_template('catalogos.html')


# ========== ENDPOINTS API ==========

@main_bp.route('/api/cargar', methods=['POST'])
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
        valor_hora = parse_numero(data.get('valor_hora'))
        valor_hora_objetivo = parse_numero(data.get('valor_hora_objetivo', valor_hora))
    except ValueError:
        errores.append('Hay valores numéricos con formato inválido')
        horas_objetivo = horas_facturadas = valor_hora = valor_hora_objetivo = 0
    
    if horas_objetivo < 0:
        errores.append('Las horas objetivo no pueden ser negativas')
    if horas_facturadas < 0:
        errores.append('Las horas facturadas no pueden ser negativas')
    if valor_hora <= 0:
        errores.append('El valor hora debe ser mayor a 0')
    if valor_hora_objetivo <= 0:
        errores.append('El valor hora objetivo debe ser mayor a 0')
    if data.get('tipo_jornada') and data.get('tipo_jornada') not in TIPOS_VH:
        errores.append('El tipo de VH no es válido')
    
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
def api_datos():
    """Endpoint para obtener datos filtrados por mes, cliente y gerente"""
    query = aplicar_filtros(Facturacion2026.query, **filtros_request())
    registros = query.order_by(Facturacion2026.fecha.desc()).all()

    return jsonify({
        'success': True,
        'data': [r.to_dict() for r in registros]
    })


@main_bp.route('/api/datos/<int:registro_id>', methods=['PUT'])
def api_actualizar_dato(registro_id):
    data = request.get_json() or {}
    if not validar_clave(data):
        return jsonify({'success': False, 'errores': ['Clave inválida']}), 403

    registro = Facturacion2026.query.get_or_404(registro_id)
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
        registro.tipo_jornada = data['tipo_jornada']
        registro.horas_objetivo = float(data.get('horas_objetivo', 0))
        registro.horas_facturadas = float(data.get('horas_facturadas', 0))
        registro.valor_hora_objetivo = float(data.get('valor_hora_objetivo') or data.get('valor_hora', 0))
        registro.valor_hora = float(data.get('valor_hora', 0))
        registro.tarifacion = data.get('tarifacion')
        registro.bonos = float(data.get('bonos', 0) or 0)
        registro.penalizaciones = float(data.get('penalizaciones', 0) or 0)
        registro.netx_gen = float(data.get('netx_gen', 0) or 0)
        registro.otros = float(data.get('otros', 0) or 0)
        asegurar_asignacion_desde_registro(registro)
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'Registro actualizado', 'data': registro.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'errores': [str(e)]}), 500


@main_bp.route('/api/datos/<int:registro_id>', methods=['DELETE'])
def api_eliminar_dato(registro_id):
    data = request.get_json() or {}
    if not validar_clave(data):
        return jsonify({'success': False, 'errores': ['Clave inválida']}), 403

    registro = Facturacion2026.query.get_or_404(registro_id)
    db.session.delete(registro)
    db.session.commit()
    return jsonify({'success': True, 'mensaje': 'Registro eliminado'})


@main_bp.route('/api/resumen', methods=['GET'])
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
            subcampania=filtros['subcampania']
        ).all()
        
        resumen_mes = resumen_registros(registros_mes)
        
        resumen.append({
            'mes': r.mes,
            **resumen_mes
        })
    
    return jsonify({
        'success': True,
        'resumen': resumen
    })


@main_bp.route('/api/kpis', methods=['GET'])
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
                'horas_objetivo': 0,
                'horas_facturadas': 0
            }
        })

    kpis = resumen_registros(registros)
    kpis['total_facturado'] = kpis['total_real']
    
    return jsonify({
        'success': True,
        'kpis': kpis
    })


@main_bp.route('/api/grafico', methods=['GET'])
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
            subcampania=filtros['subcampania']
        ).all()
        total_real = sum(reg.total_real for reg in registros_mes)
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
def api_filtros():
    """Opciones dinamicas disponibles para los filtros del dashboard."""
    filtros = filtros_request()
    registros = aplicar_filtros(Facturacion2026.query, **filtros).all()
    return jsonify({
        'success': True,
        'filtros': {
            'meses': sorted({r.mes for r in registros if r.mes}),
            'clientes': sorted({r.cliente for r in registros if r.cliente}),
            'gerentes': sorted({r.gerente for r in registros if r.gerente}),
            'jefes_site': sorted({r.jefe_site for r in registros if r.jefe_site}),
            'campanias': sorted({r.campania for r in registros if r.campania}),
            'subcampanias': sorted({r.subcampania for r in registros if r.subcampania}),
        }
    })


@main_bp.route('/api/por-cliente', methods=['GET'])
def api_por_cliente():
    """Agrupacion ejecutiva por cliente."""
    registros = registros_filtrados()
    grupos = {}
    for registro in registros:
        grupos.setdefault(registro.cliente, []).append(registro)

    datos = []
    for cliente, registros_cliente in grupos.items():
        resumen = resumen_registros(registros_cliente)
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


@main_bp.route('/api/alertas', methods=['GET'])
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
def api_exportar_excel():
    """Exporta los registros filtrados en un archivo compatible con Excel."""
    registros = aplicar_filtros(Facturacion2026.query, **filtros_request()).order_by(
        Facturacion2026.fecha.desc()
    ).all()

    headers = [
        'Fecha', 'Mes', 'Cliente', 'Gerente', 'Jefe de Site', 'Campaña', 'Sub campaña', 'Tipo de VH', 'Horas objetivo',
        'Horas facturadas', 'Valor hora objetivo', 'Valor hora alcanzado',
        '% cumplimiento horas',
        'Objetivo facturacion horas', 'Objetivo facturacion bono', 'Facturacion objetivo',
        'Facturado horas', 'Facturado bono', 'Penalizaciones por incumplimientos',
        'NetX Gen', 'Otros', 'Total facturado', 'Desvio', '% cumplimiento'
    ]
    rows = []
    for r in registros:
        rows.append([
            r.fecha.isoformat(), r.mes, r.cliente, r.gerente or '', r.jefe_site or '',
            r.campania or '', r.subcampania or '', r.tipo_jornada,
            r.horas_objetivo, r.horas_facturadas,
            r.valor_hora_objetivo if r.valor_hora_objetivo else r.valor_hora,
            r.valor_hora_alcanzado,
            round(r.porcentaje_cumplimiento_horas, 2),
            round(r.objetivo_facturacion_horas, 2), round(r.objetivo_facturacion_bono, 2),
            round(r.facturacion_objetivo, 2), round(r.facturado_horas, 2),
            round(r.facturado_bono, 2), round(r.penalizaciones_incumplimientos, 2),
            r.netx_gen or 0, r.otros or 0,
            round(r.total_real, 2),
            round(r.desvio, 2), round(r.porcentaje_cumplimiento, 2)
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
def api_template_carga():
    """Descarga una plantilla xlsx para carga masiva."""
    headers = [label for _, label in COLUMNAS_IMPORTACION]
    ayuda = [
        'YYYY-MM-DD o DD/MM/YYYY',
        'YYYY-MM',
        'Texto',
        'Texto',
        'Texto',
        'Texto',
        'Texto',
        'Diurna, Nocturna, Feriado, Capacitación, Diurnas Feriado, Nocturnas Feriado, horas líder o radio',
        'Número',
        'Número',
        'Número',
        'Número',
        'Opcional',
        'Opcional',
        'Opcional',
        'Opcional',
        'Opcional',
    ]
    contenido = crear_xlsx(headers, [ayuda])
    return Response(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="plantilla_carga_facturacion.xlsx"'}
    )


@main_bp.route('/api/importar_datos', methods=['POST'])
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
            item.setdefault('penalizaciones', 0)
            item.setdefault('netx_gen', 0)
            item.setdefault('otros', 0)
            item.setdefault('tarifacion', None)
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


@main_bp.route('/api/asignaciones', methods=['POST'])
def api_crear_asignacion():
    """Alta de una asociacion cliente/gerente/campaña/sub campaña."""
    data = request.get_json() or {}
    campos = {
        'cliente': data.get('cliente', '').strip(),
        'gerente': data.get('gerente', '').strip(),
        'jefe_site': data.get('jefe_site', '').strip(),
        'campania': data.get('campania', '').strip(),
        'subcampania': data.get('subcampania', '').strip(),
    }
    errores = [f'{campo} es obligatorio' for campo, valor in campos.items() if not valor]
    if errores:
        return jsonify({'success': False, 'errores': errores}), 400

    existente = AsignacionComercial.query.filter_by(**campos).first()
    if existente:
        existente.activa = True
        db.session.commit()
        return jsonify({'success': True, 'mensaje': 'La asociación ya existía y quedó activa', 'asignacion': existente.to_dict()})

    asignacion = AsignacionComercial(**campos)
    db.session.add(asignacion)
    db.session.commit()
    return jsonify({'success': True, 'mensaje': 'Asociación creada correctamente', 'asignacion': asignacion.to_dict()})


@main_bp.route('/api/asignaciones/<int:asignacion_id>', methods=['PATCH'])
def api_actualizar_asignacion(asignacion_id):
    data = request.get_json() or {}
    if not validar_clave(data):
        return jsonify({'success': False, 'errores': ['Clave inválida']}), 403

    asignacion = AsignacionComercial.query.get_or_404(asignacion_id)
    valores_anteriores = filtros_asignacion(asignacion)
    nuevos_valores = {}
    campos_asociacion = ['cliente', 'gerente', 'jefe_site', 'campania', 'subcampania']

    for campo in campos_asociacion:
        if campo in data:
            valor = data.get(campo, '').strip()
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
    db.session.commit()
    return jsonify({
        'success': True,
        'asignacion': asignacion.to_dict(),
        'registros_actualizados': len(registros_asociados)
    })


@main_bp.route('/api/asignaciones/<int:asignacion_id>', methods=['DELETE'])
def api_eliminar_asignacion(asignacion_id):
    data = request.get_json() or {}
    if not validar_clave(data):
        return jsonify({'success': False, 'errores': ['Clave inválida']}), 403

    asignacion = AsignacionComercial.query.get_or_404(asignacion_id)
    registros_asociados = query_por_asignacion(asignacion).all()
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
def api_clientes():
    """Endpoint para obtener lista de clientes únicos"""
    clientes = db.session.query(Facturacion2026.cliente).distinct().order_by(Facturacion2026.cliente).all()
    return jsonify({
        'success': True,
        'clientes': [c[0] for c in clientes]
    })


# Endpoint para obtener lista de gerentes únicos
@main_bp.route('/api/gerentes', methods=['GET'])
def api_gerentes():
    gerentes = db.session.query(Facturacion2026.gerente).distinct().order_by(Facturacion2026.gerente).all()
    return jsonify({
        'success': True,
        'gerentes': [g[0] for g in gerentes if g[0]]
    })


@main_bp.route('/api/meses', methods=['GET'])
def api_meses():
    """Endpoint para obtener lista de meses disponibles"""
    meses = db.session.query(Facturacion2026.mes).distinct().order_by(Facturacion2026.mes).all()
    return jsonify({
        'success': True,
        'meses': [m[0] for m in meses]
    })
