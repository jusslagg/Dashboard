from app import db
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
import re
import unicodedata
from sqlalchemy import event
from sqlalchemy.orm import Session, validates
from werkzeug.security import check_password_hash, generate_password_hash


ROLES_USUARIO = ('Full', 'Admin', 'RMO_OPS', 'Finanzas', 'Tesorero', 'RMO', 'RMO_WFM')

PUESTOS_POR_ROL = {
    'Full': ('Controller', 'Dir Gen'),
    'Admin': ('Administrador',),
    'RMO_OPS': ('Jefe de site', 'Gte ops'),
    'Finanzas': ('Resp Planif y ctrl', 'Analista Planif y ctrl', 'Gte Admin', 'Analista administracion'),
    'Tesorero': ('Tesoreria',),
    'RMO': ('COO', 'Dir Tecnologia', 'Gte Personal', 'Gte RRHH'),
    'RMO_WFM': ('WFM',),
}

JEFES_SITE_CANONICOS = {
    'alejandro del soto': 'Del Soto, Alejandro', 'del soto alejandro': 'Del Soto, Alejandro',
    'roxana de la vega': 'De la Vega, Roxana', 'de la vega roxana': 'De la Vega, Roxana',
    'ismael rissi': 'Rissi, Ismael', 'rissi ismael': 'Rissi, Ismael',
    'mariela ditto': 'Ditto, Mariela', 'ditto mariela': 'Ditto, Mariela',
    'micaela antelo': 'Antelo, Micaela', 'antelo micaela': 'Antelo, Micaela',
    'pablo chanampa': 'Chanampa, Pablo', 'chanampa pablo': 'Chanampa, Pablo',
    'salvador almeira': 'Almeira, Salvador', 'almeira salvador': 'Almeira, Salvador',
    'carolina surace': 'Surace, Carolina', 'surace carolina': 'Surace, Carolina',
    'walter canalini': 'Canalini, Walter', 'canalini walter': 'Canalini, Walter',
    'nextgen': 'NextGen', 'next gen': 'NextGen',
}

GERENTES_CANONICOS = {
    'lucas caamano': 'Caamaño, Lucas', 'caamano lucas': 'Caamaño, Lucas',
    'mariano quesada': 'Quesada, Mariano', 'quesada mariano': 'Quesada, Mariano',
    'multicuentas': 'Multicuentas', 'multi cuentas': 'Multicuentas',
    'nextgen': 'NextGen', 'next gen': 'NextGen',
    'sin gerencia': 'Sin gerencia', 'sin gerente': 'Sin gerencia',
}


def _clave_nombre(valor):
    sin_acentos = ''.join(letra for letra in unicodedata.normalize('NFD', valor)
                          if unicodedata.category(letra) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '', sin_acentos.lower())


_CLIENTES_CANONICOS = {}
_CAMPANIAS_CANONICAS = {}


def _registrar_nombre_canonico(cliente, campania=None):
    cliente_limpio = re.sub(r'\s+', ' ', str(cliente or '').strip())
    if not cliente_limpio:
        return
    clave_cliente = _clave_nombre(cliente_limpio)
    _CLIENTES_CANONICOS.setdefault(clave_cliente, cliente_limpio)
    if campania is None:
        return
    campania_limpia = re.sub(r'\s+', ' ', str(campania or '').strip())
    if campania_limpia:
        _CAMPANIAS_CANONICAS.setdefault(
            (clave_cliente, _clave_nombre(campania_limpia)),
            campania_limpia,
        )


def _canonizar_cliente(valor):
    limpio = re.sub(r'\s+', ' ', str(valor or '').strip())
    return _CLIENTES_CANONICOS.get(_clave_nombre(limpio), limpio) if limpio else limpio


def _canonizar_campania(cliente, valor):
    limpio = re.sub(r'\s+', ' ', str(valor or '').strip())
    if not limpio:
        return limpio
    return _CAMPANIAS_CANONICAS.get(
        (_clave_nombre(_canonizar_cliente(cliente)), _clave_nombre(limpio)),
        limpio,
    )


def normalizar_gerente(valor):
    if valor is None:
        return None
    limpio = re.sub(r'\s+', ' ', str(valor).strip())
    if not limpio:
        return None
    return GERENTES_CANONICOS.get(_clave_nombre(limpio), limpio)


def normalizar_jefe_site(valor):
    """Unifica mayúsculas, coma y orden con el padrón vigente."""
    if valor is None:
        return None
    limpio = re.sub(r'\s+', ' ', str(valor).strip())
    if not limpio:
        return None
    return JEFES_SITE_CANONICOS.get(_clave_nombre(limpio), limpio)


def permisos_perfil(rol, puesto=''):
    """Matriz de acceso funcional entregada por el negocio."""
    rol = {'administrador': 'Admin', 'superusuario': 'Full', 'usuario': 'RMO_OPS'}.get(rol, rol)
    puesto_clave = str(puesto or '').strip().lower()
    modulos = set()
    if rol == 'Full':
        modulos = {'facturacion_total', 'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq',
                   'rmo_personal', 'directorio', 'proyecciones'}
    elif rol == 'Admin':
        modulos = {'facturacion_total', 'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq',
                   'directorio', 'proyecciones'}
    elif rol == 'RMO_OPS':
        modulos = {'facturacion_asignada'}
    elif rol == 'Finanzas' and puesto_clave in {
        'analista planif y ctrl', 'gte admin', 'analista administracion', 'analista administracion?'
    }:
        modulos = {'facturacion_total', 'directorio', 'proyecciones'}
    elif rol == 'Tesorero':
        modulos = {'proyecciones'}
    elif rol == 'RMO':
        modulos = {'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq', 'rmo_personal'}
    elif rol == 'RMO_WFM':
        modulos = {'rmo_multi_co', 'rmo_multi_sq', 'rmo_personal'}
    return {
        'visualizar': True,
        'cargar': rol in ('Full', 'Admin'),
        'editar': rol == 'Admin',
        'eliminar': rol == 'Admin',
        'administrar_perfiles': rol == 'Admin',
        'modulos': modulos,
    }

# Tipos numéricos del contrato de base. ``asdecimal=False`` mantiene la
# compatibilidad de las APIs y cálculos Python actuales, mientras que el motor
# almacena los valores con precisión y escala explícitas.
DINERO = db.Numeric(18, 2, asdecimal=False)
CANTIDAD = db.Numeric(18, 4, asdecimal=False)
HORAS = db.Numeric(20, 10, asdecimal=False)
PORCENTAJE = db.Numeric(15, 10, asdecimal=False)
COTIZACION = db.Numeric(24, 10, asdecimal=False)


def redondear_moneda(valor):
    return float(Decimal(str(valor or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(30), nullable=False, default='usuario')
    puesto = db.Column(db.String(100), nullable=True)
    gerente_asignado = db.Column(db.String(100), nullable=True)
    jefe_site_asignado = db.Column(db.String(100), nullable=True)
    permisos_personalizados = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    debe_cambiar_password = db.Column(db.Boolean, default=False, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_administrador(self):
        return self.rol in ('Admin', 'administrador')

    @property
    def es_superusuario(self):
        return self.rol in ('Full', 'superusuario')

    @property
    def permisos(self):
        base = permisos_perfil(self.rol, self.puesto)
        if not self.permisos_personalizados:
            return base
        try:
            guardados = json.loads(self.permisos_personalizados)
        except (TypeError, ValueError):
            return base
        modulos_validos = {
            'facturacion_total', 'facturacion_asignada', 'rmo_santander', 'rmo_multi_co',
            'rmo_multi_sq', 'rmo_personal', 'directorio', 'proyecciones',
        }
        return {
            'visualizar': bool(guardados.get('visualizar', True)),
            'cargar': bool(guardados.get('cargar', False)),
            'editar': bool(guardados.get('editar', False)),
            'eliminar': bool(guardados.get('eliminar', False)),
            'administrar_perfiles': bool(guardados.get('administrar_perfiles', False)),
            'modulos': set(guardados.get('modulos') or ()) & modulos_validos,
        }

    def puede_acceder(self, modulo):
        return self.permisos['visualizar'] and modulo in self.permisos['modulos']

    @property
    def puede_ver_facturacion(self):
        return self.permisos['visualizar'] and any(
            modulo.startswith(('facturacion_', 'rmo_')) for modulo in self.permisos['modulos']
        )

    @property
    def puede_ver_directorio(self):
        return self.puede_acceder('directorio')

    @property
    def puede_ver_proyecciones(self):
        return self.puede_acceder('proyecciones')

    @property
    def puede_editar(self):
        return self.permisos['editar']

    @property
    def puede_cargar(self):
        return self.permisos['cargar']

    @property
    def puede_eliminar(self):
        return self.permisos['eliminar']

    @property
    def puede_ver_carga(self):
        return self.permisos['cargar'] and self.puede_ver_facturacion

    @property
    def puede_ver_catalogos(self):
        return self.es_administrador

    @property
    def puede_administrar_usuarios(self):
        return self.permisos['administrar_perfiles']

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'email': self.email,
            'rol': self.rol,
            'puesto': self.puesto,
            'gerente_asignado': self.gerente_asignado,
            'jefe_site_asignado': self.jefe_site_asignado,
            'permisos': {**self.permisos, 'modulos': sorted(self.permisos['modulos'])},
            'activo': self.activo,
            'debe_cambiar_password': self.debe_cambiar_password,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class HistorialCambio(db.Model):
    __tablename__ = 'historial_cambios'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    usuario_nombre = db.Column(db.String(120), nullable=True)
    usuario_email = db.Column(db.String(160), nullable=True)
    accion = db.Column(db.String(30), nullable=False)
    entidad = db.Column(db.String(80), nullable=False)
    entidad_id = db.Column(db.String(50), nullable=True)
    resumen = db.Column(db.String(255), nullable=False)
    detalle = db.Column(db.Text, nullable=True)
    antes = db.Column(db.Text, nullable=True)
    despues = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    usuario = db.relationship('Usuario', lazy=True)

    def _json(self, value):
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    def to_dict(self):
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'usuario_nombre': self.usuario_nombre,
            'usuario_email': self.usuario_email,
            'accion': self.accion,
            'entidad': self.entidad,
            'entidad_id': self.entidad_id,
            'resumen': self.resumen,
            'detalle': self.detalle,
            'antes': self._json(self.antes),
            'despues': self._json(self.despues),
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }


class FacturacionAnio(db.Model):
    """Facturación real histórica y futura, sin limitar el período a 2026."""
    __tablename__ = 'facturacion_anio'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    cliente = db.Column(db.String(100), nullable=False)
    gerente = db.Column(db.String(100), nullable=True)
    jefe_site = db.Column(db.String(100), nullable=True)
    campania = db.Column(db.String(100), nullable=True)
    subcampania = db.Column(db.String(100), nullable=True)
    tipo_negocio = db.Column(db.String(100), nullable=True)
    es_next_gen = db.Column(db.Boolean, default=False, nullable=False)
    objetivo_separar_ajuste_vh = db.Column(db.Boolean, default=False, nullable=False)
    tipo_jornada = db.Column(db.String(50), nullable=False)
    horas_objetivo = db.Column(HORAS, nullable=False)
    horas_facturadas = db.Column(HORAS, nullable=False)
    horas_penalizadas = db.Column(HORAS, default=0)
    valor_hora_objetivo = db.Column(DINERO, nullable=True)
    valor_hora = db.Column(DINERO, nullable=False)
    facturado_horas_manual = db.Column(DINERO, nullable=True)
    total_facturado_manual = db.Column(DINERO, nullable=True)
    control_facturado_horas = db.Column(DINERO, nullable=True)
    control_variable_productivo = db.Column(DINERO, nullable=True)
    control_penalizaciones_bonos = db.Column(DINERO, nullable=True)
    control_total_facturado = db.Column(DINERO, nullable=True)
    control_objetivo_total = db.Column(DINERO, nullable=True)
    tarifacion = db.Column(DINERO, nullable=True)
    importe_fijo = db.Column(DINERO, nullable=True)
    variable_objetivo = db.Column(DINERO, default=0)
    variable_productivo = db.Column(DINERO, default=0)
    bonos = db.Column(DINERO, default=0)
    penalizaciones = db.Column(DINERO, default=0)
    netx_gen = db.Column(DINERO, default=0)
    otros = db.Column(DINERO, default=0)

    @validates('jefe_site')
    def validar_jefe_site(self, _, valor):
        return normalizar_jefe_site(valor)

    @validates('gerente')
    def validar_gerente(self, _, valor):
        return normalizar_gerente(valor)
    justificaciones = db.relationship(
        'JustificacionAjuste',
        backref='registro',
        cascade='all, delete-orphan',
        lazy=True,
    )

    @property
    def valor_hora_alcanzado(self):
        return self.valor_hora

    @property
    def valor_hora_objetivo_calculo(self):
        return self.valor_hora_objetivo if self.valor_hora_objetivo else self.valor_hora

    @property
    def usa_importe_fijo(self):
        return self.importe_fijo is not None and self.importe_fijo > 0

    @property
    def objetivo_facturacion_horas(self):
        if self.usa_importe_fijo:
            return self.importe_fijo
        if self.objetivo_separar_ajuste_vh:
            return self.horas_objetivo * self.valor_hora_alcanzado
        return self.horas_objetivo * self.valor_hora_objetivo_calculo

    @property
    def objetivo_facturacion_bono(self):
        return self.variable_objetivo or 0

    @property
    def facturacion_objetivo(self):
        return self.objetivo_facturacion_horas + self.objetivo_facturacion_bono

    @property
    def facturado_horas(self):
        if self.facturado_horas_manual is not None:
            return self.facturado_horas_manual
        if self.usa_importe_fijo:
            return self.importe_fijo
        horas_netas = max((self.horas_facturadas or 0) - (self.horas_penalizadas or 0), 0)
        return horas_netas * self.valor_hora_alcanzado

    @property
    def facturado_bono(self):
        return self.bonos or 0

    @property
    def variable_productivo_calculo(self):
        return self.variable_productivo or 0

    @property
    def penalizaciones_incumplimientos(self):
        valor = self.penalizaciones or 0
        return -abs(valor) if valor else 0

    @property
    def facturado_horas_control(self):
        return self.control_facturado_horas if self.control_facturado_horas is not None else self.facturado_horas

    @property
    def variable_productivo_control(self):
        return self.control_variable_productivo if self.control_variable_productivo is not None else self.variable_productivo_calculo

    @property
    def penalizaciones_bonos_control(self):
        if self.control_penalizaciones_bonos is not None:
            return self.control_penalizaciones_bonos
        return self.facturado_bono + self.penalizaciones_incumplimientos

    @property
    def total_facturado_control(self):
        if self.control_total_facturado is not None:
            return self.control_total_facturado
        return (
            self.facturado_horas_control
            + (self.tarifacion or 0)
            + self.variable_productivo_control
            + self.penalizaciones_bonos_control
            + (self.netx_gen or 0)
            + (self.otros or 0)
        )

    @property
    def porcentaje_cumplimiento_horas(self):
        if self.horas_objetivo == 0:
            return 0
        return (self.horas_facturadas / self.horas_objetivo) * 100

    @property
    def total_real(self):
        """Calcula el total facturado segun la apertura de control."""
        if self.usa_importe_fijo:
            return (
                self.importe_fijo
                + self.facturado_bono
                + self.penalizaciones_incumplimientos
            )
        return (
            self.facturado_horas
            + self.facturado_bono
            + self.penalizaciones_incumplimientos
        )

    @property
    def monto_final_con_tarifacion(self):
        return self.total_real + (self.tarifacion or 0)

    @property
    def total_dashboard(self):
        # Una carga identificada como NextGen se informa exclusivamente en su
        # concepto, aunque el archivo o formulario haya enviado un total manual
        # vacío o en cero. No debe transformarse en horas ni perder el importe.
        if self.es_next_gen:
            return self.netx_gen or 0
        if self.total_facturado_manual is not None:
            return self.total_facturado_manual
        if self.usa_importe_fijo:
            return (
                self.importe_fijo
                + (self.tarifacion or 0)
                + self.facturado_bono
                + self.variable_productivo_calculo
                + self.penalizaciones_incumplimientos
                + (self.netx_gen or 0)
                + (self.otros or 0)
            )
        return (
            self.facturado_horas
            + (self.tarifacion or 0)
            + self.facturado_bono
            + self.variable_productivo_calculo
            + self.penalizaciones_incumplimientos
            + (self.netx_gen or 0)
            + (self.otros or 0)
        )

    @property
    def total_teorico(self):
        """Total de Facturación Objetivo, respetando el control del Excel."""
        if self.control_objetivo_total is not None:
            return self.control_objetivo_total
        return self.facturacion_objetivo

    @property
    def desvio(self):
        """Calcula el desvio real contra objetivo."""
        if self.es_next_gen:
            return 0
        return self.total_real - self.total_teorico

    @property
    def porcentaje_cumplimiento(self):
        """Calcula el porcentaje de cumplimiento: total_real / total_teorico."""
        if self.es_next_gen:
            return 0
        if self.usa_importe_fijo:
            return 100
        if self.total_teorico == 0:
            return 0
        return (self.total_real / self.total_teorico) * 100

    def to_dict(self):
        return {
            'id': self.id,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'mes': self.mes,
            'cliente': self.cliente,
            'gerente': self.gerente,
            'jefe_site': self.jefe_site,
            'campania': self.campania,
            'subcampania': self.subcampania,
            'tipo_negocio': self.tipo_negocio,
            'es_next_gen': bool(self.es_next_gen),
            'objetivo_separar_ajuste_vh': bool(self.objetivo_separar_ajuste_vh),
            'tipo_jornada': self.tipo_jornada,
            'horas_objetivo': self.horas_objetivo,
            'horas_facturadas': self.horas_facturadas,
            'horas_penalizadas': self.horas_penalizadas or 0,
            'valor_hora_objetivo': self.valor_hora_objetivo_calculo,
            'valor_hora_alcanzado': self.valor_hora_alcanzado,
            'valor_hora': self.valor_hora,
            'facturado_horas_manual': self.facturado_horas_manual,
            'total_facturado_manual': self.total_facturado_manual,
            'control_facturado_horas': self.control_facturado_horas,
            'control_variable_productivo': self.control_variable_productivo,
            'control_penalizaciones_bonos': self.control_penalizaciones_bonos,
            'control_total_facturado': self.control_total_facturado,
            'control_objetivo_total': self.control_objetivo_total,
            'tarifacion': self.tarifacion,
            'importe_fijo': self.importe_fijo,
            'variable_objetivo': self.variable_objetivo,
            'variable_productivo': self.variable_productivo,
            'bonos': self.bonos,
            'penalizaciones': self.penalizaciones_incumplimientos,
            'netx_gen': self.netx_gen,
            'otros': self.otros,
            'justificaciones': [item.to_dict() for item in self.justificaciones],
            'objetivo_facturacion_horas': round(self.objetivo_facturacion_horas, 2),
            'objetivo_facturacion_bono': round(self.objetivo_facturacion_bono, 2),
            'facturacion_objetivo': round(self.facturacion_objetivo, 2),
            'facturado_horas': round(self.facturado_horas, 2),
            'facturado_bono': round(self.facturado_bono, 2),
            'variable_productivo_calculo': round(self.variable_productivo_calculo, 2),
            'penalizaciones_incumplimientos': round(self.penalizaciones_incumplimientos, 2),
            'porcentaje_cumplimiento_horas': round(self.porcentaje_cumplimiento_horas, 2),
            'total_facturado': round(self.total_dashboard, 2),
            'total_real': round(self.total_dashboard, 2),
            'monto_final_con_tarifacion': round(self.monto_final_con_tarifacion, 2),
            'total_dashboard': round(self.total_dashboard, 2),
            'total_teorico': round(self.total_teorico, 2),
            'desvio': round(0 if self.es_next_gen else self.total_dashboard - self.total_teorico, 2),
            'porcentaje_cumplimiento': round(
                (self.total_dashboard / self.total_teorico * 100)
                if self.total_teorico > 0 and not self.es_next_gen else 0,
                2
            )
        }


# Alias temporal para las rutas existentes. La entidad y la tabla física ya no
# están limitadas a 2026; el código consumidor puede migrar gradualmente al
# nombre FacturacionAnio sin afectar el contrato actual de las APIs.
Facturacion2026 = FacturacionAnio


class JustificacionAjuste(db.Model):
    __tablename__ = 'justificaciones_ajustes'

    id = db.Column(db.Integer, primary_key=True)
    facturacion_id = db.Column(db.Integer, db.ForeignKey('facturacion_anio.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    cantidad = db.Column(CANTIDAD, default=1)
    precio = db.Column(DINERO, default=0)
    importe = db.Column(DINERO, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def importe_calculo(self):
        valor = self.importe or 0
        return -abs(valor) if self.tipo == 'penalizaciones' else valor

    def to_dict(self):
        return {
            'id': self.id,
            'facturacion_id': self.facturacion_id,
            'tipo': self.tipo,
            'cantidad': self.cantidad or 0,
            'precio': self.precio or 0,
            'importe': self.importe_calculo,
            'descripcion': self.descripcion,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }


class ProyeccionMatriz(db.Model):
    __tablename__ = 'matriz_proyecciones'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    dotacion_requerida = db.Column(HORAS, default=0, nullable=False)
    carga_semanal = db.Column(db.String(20), default='L a V', nullable=False)
    carga_horaria = db.Column(HORAS, default=0, nullable=False)
    dias_objetivo = db.Column(db.Integer, default=0, nullable=False)
    horas_requeridas = db.Column(HORAS, default=0, nullable=False)
    porcentaje_cumplimiento = db.Column(PORCENTAJE, default=100, nullable=False)
    tiene_nocturnidad = db.Column(db.Boolean, default=False, nullable=False)
    porcentaje_nocturnidad = db.Column(PORCENTAJE, default=0, nullable=False)
    tipo_plp = db.Column(db.String(30), nullable=True)
    horas_carga_manual = db.Column(db.Boolean, default=False, nullable=False)
    dias_objetivo_manual = db.Column(db.Integer, nullable=True)
    horas_requeridas_manual = db.Column(HORAS, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    jornadas = db.relationship(
        'ProyeccionMatrizJornada',
        backref='proyeccion',
        cascade='all, delete-orphan',
        lazy=True,
        order_by='ProyeccionMatrizJornada.id',
    )

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'mes', name='uq_matriz_proyecciones_cliente_campania_mes'),
    )

    @property
    def horas_proyectadas(self):
        return (self.horas_requeridas or 0) * ((self.porcentaje_cumplimiento or 0) / 100)

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'campania': self.campania,
            'year': self.year,
            'mes': self.mes,
            'dotacion_requerida': self.dotacion_requerida or 0,
            'carga_semanal': self.carga_semanal or 'L a V',
            'carga_horaria': self.carga_horaria or 0,
            'dias_objetivo': self.dias_objetivo or 0,
            'horas_requeridas': self.horas_requeridas or 0,
            'porcentaje_cumplimiento': self.porcentaje_cumplimiento or 0,
            'tiene_nocturnidad': bool(self.tiene_nocturnidad),
            'porcentaje_nocturnidad': self.porcentaje_nocturnidad or 0,
            'tipo_plp': self.tipo_plp or '',
            'horas_carga_manual': bool(self.horas_carga_manual),
            'dias_objetivo_manual': self.dias_objetivo_manual,
            'horas_requeridas_manual': self.horas_requeridas_manual,
            'horas_proyectadas': round(self.horas_proyectadas, 2),
            'jornadas': [jornada.to_dict() for jornada in self.jornadas],
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class ProyeccionMatrizJornada(db.Model):
    __tablename__ = 'matriz_proyecciones_jornadas'

    id = db.Column(db.Integer, primary_key=True)
    proyeccion_id = db.Column(db.Integer, db.ForeignKey('matriz_proyecciones.id'), nullable=False, index=True)
    dotacion_requerida = db.Column(HORAS, default=0, nullable=False)
    carga_semanal = db.Column(db.String(30), default='L a V', nullable=False)
    carga_horaria = db.Column(HORAS, default=0, nullable=False)
    dias_objetivo = db.Column(db.Integer, default=0, nullable=False)
    horas_requeridas = db.Column(HORAS, default=0, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'dotacion_requerida': self.dotacion_requerida or 0,
            'carga_semanal': self.carga_semanal or 'L a V',
            'carga_horaria': self.carga_horaria or 0,
            'dias_objetivo': self.dias_objetivo or 0,
            'horas_requeridas': round(self.horas_requeridas or 0, 2),
        }


class PersonalDistribucionHoras(db.Model):
    __tablename__ = 'personal_distribucion_horas'

    id = db.Column(db.Integer, primary_key=True)
    servicio = db.Column(db.String(100), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    porcentaje_diurno = db.Column(PORCENTAJE, default=100, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @validates('gerente_asignado')
    def validar_gerente_asignado(self, _, valor):
        return normalizar_gerente(valor)

    @validates('jefe_site_asignado')
    def validar_jefe_site_asignado(self, _, valor):
        return normalizar_jefe_site(valor)

    __table_args__ = (
        db.UniqueConstraint('servicio', 'mes', name='uq_personal_distribucion_servicio_mes'),
    )

    @property
    def porcentaje_nocturno(self):
        return max(0, 100 - (self.porcentaje_diurno or 0))

    def to_dict(self):
        return {
            'id': self.id,
            'servicio': self.servicio,
            'year': self.year,
            'mes': self.mes,
            'porcentaje_diurno': self.porcentaje_diurno or 0,
            'porcentaje_nocturno': self.porcentaje_nocturno,
        }


class ProyeccionPrecio(db.Model):
    __tablename__ = 'matriz_precios'

    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    precio_base = db.Column(COTIZACION, default=0, nullable=False)
    alcance_porcentaje = db.Column(PORCENTAJE, default=100, nullable=False)
    precio_final = db.Column(COTIZACION, default=0, nullable=False)
    importe_fijo_mensual = db.Column(DINERO, default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'mes', name='uq_matriz_precios_cliente_campania_mes'),
    )

    def recalcular(self):
        total = Decimal(str(self.precio_base or 0)) * (Decimal(str(self.alcance_porcentaje or 0)) / Decimal('100'))
        self.precio_final = float(total.quantize(Decimal('0.0000000001'), rounding=ROUND_HALF_UP))

    def to_dict(self):
        return {
            'id': self.id,
            'site': self.site or '',
            'cliente': self.cliente,
            'campania': self.campania,
            'year': self.year,
            'mes': self.mes,
            'precio_base': self.precio_base or 0,
            'alcance_porcentaje': self.alcance_porcentaje or 0,
            'precio_final': round(self.precio_final or 0, 10),
            'importe_fijo_mensual': round(self.importe_fijo_mensual or 0, 2),
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class VariableCampania(db.Model):
    __tablename__ = 'variables_campanias'

    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    porcentaje = db.Column(PORCENTAJE, default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'mes', name='uq_variables_cliente_campania_mes'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'site': self.site or '',
            'cliente': self.cliente,
            'campania': self.campania,
            'year': self.year,
            'mes': self.mes,
            'porcentaje': self.porcentaje or 0,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class TarifacionCampania(db.Model):
    __tablename__ = 'tarifaciones_campanias'

    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    concepto = db.Column(db.String(100), default='Tarifación', nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    monto = db.Column(COTIZACION, default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'concepto', 'mes', name='uq_tarifacion_campania_concepto_mes'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'site': self.site or '', 'cliente': self.cliente,
            'campania': self.campania, 'concepto': self.concepto,
            'year': self.year, 'mes': self.mes, 'monto': self.monto or 0,
        }


class NextGenDolar(db.Model):
    __tablename__ = 'next_gen_dolar'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, unique=True, index=True)
    valor = db.Column(COTIZACION, default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'year': self.year, 'mes': self.mes, 'valor': self.valor or 0}


class NextGenProducto(db.Model):
    __tablename__ = 'next_gen_productos'

    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    producto = db.Column(db.String(160), nullable=False)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    cantidad_usd = db.Column(COTIZACION, default=0, nullable=False)
    cotizacion_aplicada = db.Column(COTIZACION, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'producto', 'mes', name='uq_next_gen_producto_mes'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'site': self.site or '', 'cliente': self.cliente,
            'campania': self.campania, 'producto': self.producto,
            'year': self.year, 'mes': self.mes, 'cantidad_usd': self.cantidad_usd or 0,
            'cotizacion_aplicada': self.cotizacion_aplicada,
        }


class SiteProyeccion(db.Model):
    __tablename__ = 'sites_proyecciones'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(160), nullable=False)
    site = db.Column(db.String(100), nullable=False)
    cliente_destino = db.Column(db.String(100), nullable=True)
    campania_destino = db.Column(db.String(160), nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', name='uq_site_proyeccion_cliente_campania'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'cliente': self.cliente, 'campania': self.campania, 'site': self.site,
            'cliente_destino': self.cliente_destino or '', 'campania_destino': self.campania_destino or '',
        }


class FeriadoOperativo(db.Model):
    __tablename__ = 'feriados_operativos'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    nombre = db.Column(db.String(160), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default='Manual')
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('fecha', name='uq_feriados_operativos_fecha'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'fecha': self.fecha.isoformat() if self.fecha else None,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'activo': self.activo,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
            'actualizado_en': self.actualizado_en.isoformat() if self.actualizado_en else None,
        }


class DotacionMensual(db.Model):
    """Serie mensual usada por los indicadores de dotaciones."""
    __tablename__ = 'dotaciones_mensuales'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True, index=True)
    dotacion_requerida = db.Column(HORAS, nullable=False)
    personal = db.Column(HORAS, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'fecha': self.fecha.isoformat(),
            'dotacion_requerida': self.dotacion_requerida or 0,
            'personal': self.personal or 0,
        }


class RatioEliMensual(db.Model):
    __tablename__ = 'ratio_eli_mensual'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True, index=True)
    requerido = db.Column(HORAS, nullable=False)
    staff = db.Column(HORAS, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    def to_dict(self):
        r, s = float(self.requerido or 0), float(self.staff or 0)
        return {'id': self.id, 'fecha': self.fecha.isoformat(), 'mes': self.fecha.strftime('%Y-%m'), 'requerido': r, 'staff': s, 'ratio': s/r if r else None}


class RatioEliIIMensual(db.Model):
    __tablename__ = 'ratio_eli_ii_mensual'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True, index=True)
    operaciones = db.Column(HORAS, nullable=False)
    staff = db.Column(HORAS, nullable=False)
    operaciones_importe = db.Column(DINERO, nullable=False, default=0)
    staff_importe = db.Column(DINERO, nullable=False, default=0)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        operaciones, staff = float(self.operaciones or 0), float(self.staff or 0)
        operaciones_importe, staff_importe = float(self.operaciones_importe or 0), float(self.staff_importe or 0)
        return {
            'id': self.id, 'fecha': self.fecha.isoformat(), 'mes': self.fecha.strftime('%Y-%m'),
            'operaciones': operaciones, 'staff': staff, 'total': operaciones + staff,
            'ratio': staff / operaciones if operaciones else None,
            'operaciones_importe': operaciones_importe, 'staff_importe': staff_importe,
            'total_importe': operaciones_importe + staff_importe,
            'ratio_importe': staff_importe / operaciones_importe if operaciones_importe else None,
        }


class DashboardOperativo(db.Model):
    """Fila mensual importada del Dashboard; bajas se conserva manualmente."""
    __tablename__ = 'dashboard_operativo'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    cliente = db.Column(db.String(120), nullable=False, index=True)
    campania = db.Column(db.String(180), nullable=False)
    datos = db.Column(db.Text, nullable=False, default='{}')
    bajas_manual = db.Column(HORAS, nullable=False, default=0)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('mes', 'cliente', 'campania', name='uq_dashboard_mes_cliente_campania'),
    )

    def datos_dict(self):
        try:
            return json.loads(self.datos or '{}')
        except (TypeError, ValueError):
            return {}

    def to_dict(self):
        return {
            'id': self.id, 'year': self.year, 'mes': self.mes,
            'cliente': self.cliente, 'campania': self.campania,
            'datos': self.datos_dict(), 'bajas_manual': self.bajas_manual or 0,
        }


class HistoricoClienteMensual(db.Model):
    """Base histórica por cliente; pagadas y logueo son los únicos datos manuales."""
    __tablename__ = 'historico_clientes_mensuales'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    mes = db.Column(db.String(7), nullable=False, index=True)
    cliente = db.Column(db.String(160), nullable=False, index=True)
    datos_base = db.Column(db.Text, nullable=False, default='{}')
    pagadas = db.Column(HORAS, nullable=True)
    logueo = db.Column(HORAS, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('mes', 'cliente', name='uq_historico_mes_cliente'),)

    def base_dict(self):
        try:
            return json.loads(self.datos_base or '{}')
        except (TypeError, ValueError):
            return {}

    def to_dict(self):
        return {'id': self.id, 'year': self.year, 'mes': self.mes, 'cliente': self.cliente,
                'datos_base': self.base_dict(), 'pagadas': self.pagadas, 'logueo': self.logueo}


class DotacionClienteMensual(db.Model):
    """Dotación requerida mensual abierta por cliente, como en la matriz Excel."""
    __tablename__ = 'dotaciones_clientes_mensuales'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(160), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    dotacion = db.Column(HORAS, nullable=False, default=0)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'fecha', name='uq_dotacion_cliente_fecha'),
    )

    def to_dict(self):
        return {'id': self.id, 'cliente': self.cliente, 'fecha': self.fecha.isoformat(), 'dotacion': self.dotacion or 0}


class GraficoDotacionMensual(db.Model):
    __tablename__ = 'graficos_dotaciones_mensuales'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True, index=True)
    dotacion_requerida = db.Column(HORAS, nullable=False)
    activa_sl = db.Column(HORAS, nullable=False)
    activa_ba = db.Column(HORAS, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        activa = float(self.activa_sl or 0) + float(self.activa_ba or 0)
        requerida = float(self.dotacion_requerida or 0)
        return {'id': self.id, 'fecha': self.fecha.isoformat(), 'dotacion_requerida': requerida,
                'activa_sl': self.activa_sl or 0, 'activa_ba': self.activa_ba or 0,
                'dotacion_activa': round(activa, 2), 'diferencia': round(activa - requerida, 2),
                'porcentaje_staff': round((activa - requerida) / requerida, 6) if requerida else 0}


class Campania(db.Model):
    """Catálogo canónico de campañas.

    El ID identifica de manera estable la combinación cliente + nombre. El
    nombre puede repetirse para clientes distintos, pero no dentro del mismo
    cliente.
    """
    __tablename__ = 'campanias'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    valor_hora_variable = db.Column(db.Boolean, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'nombre', name='uq_campanias_cliente_nombre'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'nombre': self.nombre,
            'activa': self.activa,
            'valor_hora_variable': self.valor_hora_variable,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }


class ExcepcionCalculo(db.Model):
    __tablename__ = 'excepciones_calculo'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    tipo_calculo = db.Column(db.String(60), nullable=False, default='facturado_horas_manual')
    ajuste_vh_objetivo_pct = db.Column(db.Numeric(9, 4, asdecimal=False), default=0, nullable=False)
    ajuste_vh_alcanzado_pct = db.Column(db.Numeric(9, 4, asdecimal=False), default=0, nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', name='uq_excepcion_calculo_cliente_campania'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'campania': self.campania,
            'tipo_calculo': self.tipo_calculo,
            'ajuste_vh_objetivo_pct': self.ajuste_vh_objetivo_pct or 0,
            'ajuste_vh_alcanzado_pct': self.ajuste_vh_alcanzado_pct or 0,
            'activa': self.activa,
        }


class AsignacionComercial(db.Model):
    __tablename__ = 'asignaciones_comerciales'

    id = db.Column(db.Integer, primary_key=True)
    campania_id = db.Column(
        db.Integer,
        db.ForeignKey('campanias.id', name='fk_asignaciones_campania'),
        nullable=False,
        index=True,
    )
    cliente = db.Column(db.String(100), nullable=False)
    gerente = db.Column(db.String(100), nullable=False)
    jefe_site = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    subcampania = db.Column(db.String(100), nullable=False)
    tipo_negocio = db.Column(db.String(100), nullable=True)
    es_next_gen = db.Column(db.Boolean, default=False, nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    vigencia_desde = db.Column(db.String(7), nullable=True, index=True)
    vigencia_hasta = db.Column(db.String(7), nullable=True, index=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    campania_catalogo = db.relationship('Campania', lazy=True)

    @validates('jefe_site')
    def validar_jefe_site(self, _, valor):
        return normalizar_jefe_site(valor)

    @validates('gerente')
    def validar_gerente(self, _, valor):
        return normalizar_gerente(valor)

    @property
    def label(self):
        partes = [self.cliente, self.gerente, self.jefe_site, self.campania, self.subcampania]
        if self.tipo_negocio:
            partes.append(self.tipo_negocio)
        return ' / '.join(partes)

    def to_dict(self):
        return {
            'id': self.id,
            'campania_id': self.campania_id,
            'cliente': self.cliente,
            'gerente': self.gerente,
            'jefe_site': self.jefe_site,
            'campania': self.campania,
            'subcampania': self.subcampania,
            'tipo_negocio': self.tipo_negocio,
            'es_next_gen': bool(self.es_next_gen),
            'activa': self.activa,
            'vigencia_desde': self.vigencia_desde,
            'vigencia_hasta': self.vigencia_hasta,
            'label': self.label
        }


MODELOS_CON_IDENTIDAD_COMERCIAL = (
    FacturacionAnio,
    ProyeccionMatriz,
    ProyeccionPrecio,
    VariableCampania,
    TarifacionCampania,
    NextGenProducto,
    SiteProyeccion,
    DashboardOperativo,
    HistoricoClienteMensual,
    DotacionClienteMensual,
    Campania,
    ExcepcionCalculo,
    AsignacionComercial,
)


def cargar_nombres_comerciales_canonicos():
    """Carga el padrón cliente/campaña que gobierna escritura y filtros."""
    _CLIENTES_CANONICOS.clear()
    _CAMPANIAS_CANONICAS.clear()
    for registro in Campania.query.order_by(Campania.id).all():
        _registrar_nombre_canonico(registro.cliente, registro.nombre)
    # Las fuentes históricas pueden contener clientes todavía no incorporados
    # al catálogo. La primera grafía operativa queda registrada y las variantes
    # posteriores se alinean con ella.
    for modelo in MODELOS_CON_IDENTIDAD_COMERCIAL:
        for registro in modelo.query.order_by(modelo.id).all():
            campania = getattr(registro, 'nombre', None) if isinstance(registro, Campania) else getattr(registro, 'campania', None)
            _registrar_nombre_canonico(getattr(registro, 'cliente', None), campania)


def normalizar_nombres_comerciales_existentes():
    """Alinea variantes de mayúsculas, espacios y acentos con el catálogo."""
    cargar_nombres_comerciales_canonicos()
    db.session.info['normalizando_nombres_comerciales'] = True
    modificados = 0
    # Había doce precios vacíos de ``Santander Préstamos`` que, al corregir
    # la grafía, coinciden con los doce precios válidos ya existentes. Se
    # conserva por clave mensual la fila con información económica y se quita
    # únicamente la variante vacía.
    grupos_precios = {}
    for registro in ProyeccionPrecio.query.order_by(ProyeccionPrecio.id).all():
        cliente = _canonizar_cliente(registro.cliente)
        campania = _canonizar_campania(cliente, registro.campania)
        clave = (cliente, campania, registro.mes)
        grupos_precios.setdefault(clave, []).append(registro)
    for registros in grupos_precios.values():
        if len(registros) < 2:
            continue
        registros.sort(
            key=lambda fila: (
                bool(fila.precio_base or fila.precio_final or fila.importe_fijo_mensual),
                fila.id,
            ),
            reverse=True,
        )
        for duplicado in registros[1:]:
            db.session.delete(duplicado)
            modificados += 1

    # El histórico puede contener una fila de base y otra auxiliar del Dashboard
    # para el mismo cliente/mes con distinta grafía. Primero se combinan sus
    # aportes; renombrarlas directamente violaría la clave única y, peor aún,
    # podría perder horas.
    grupos_historicos = {}
    for registro in HistoricoClienteMensual.query.order_by(HistoricoClienteMensual.id).all():
        clave = (registro.mes, _clave_nombre(_canonizar_cliente(registro.cliente)))
        grupos_historicos.setdefault(clave, []).append(registro)
    campos_suma = (
        'horas_dotacion_activa', 'horas_ausentismo', 'dotacion_promedio',
        'bajas', 'horas_requeridas', 'horas_realizadas', 'dotacion_requerida',
    )
    for registros in grupos_historicos.values():
        if len(registros) < 2:
            continue
        principal = registros[0]
        datos = principal.base_dict()
        for adicional in registros[1:]:
            otros = adicional.base_dict()
            for campo in campos_suma:
                datos[campo] = float(datos.get(campo) or 0) + float(otros.get(campo) or 0)
            for campo in ('empresa', 'site', 'industria'):
                datos[campo] = datos.get(campo) or otros.get(campo)
            for campo in ('pagadas', 'logueo'):
                valores = [
                    valor for valor in (getattr(principal, campo), getattr(adicional, campo))
                    if valor is not None
                ]
                setattr(principal, campo, sum(float(valor) for valor in valores) if valores else None)
            db.session.delete(adicional)
            modificados += 1
        principal.datos_base = json.dumps(datos, ensure_ascii=False)

    # SQLite ejecuta UPDATE antes que DELETE dentro de un mismo flush. Se
    # eliminan primero las variantes ya consolidadas para liberar la clave
    # única (mes, cliente) antes de adoptar el nombre canónico.
    db.session.flush()

    with db.session.no_autoflush:
        for modelo in MODELOS_CON_IDENTIDAD_COMERCIAL:
            for registro in modelo.query.all():
                if registro in db.session.deleted:
                    continue
                if hasattr(registro, 'cliente'):
                    cliente = _canonizar_cliente(registro.cliente)
                    if cliente != registro.cliente:
                        registro.cliente = cliente
                        modificados += 1
                campo_campania = 'nombre' if isinstance(registro, Campania) else 'campania'
                if hasattr(registro, campo_campania):
                    actual = getattr(registro, campo_campania)
                    canonico = _canonizar_campania(getattr(registro, 'cliente', ''), actual)
                    if canonico != actual:
                        setattr(registro, campo_campania, canonico)
                        modificados += 1
    if modificados:
        db.session.commit()
    db.session.info.pop('normalizando_nombres_comerciales', None)
    return modificados


@event.listens_for(Session, 'before_flush')
def canonizar_identidad_comercial_antes_de_guardar(session, _flush_context, _instances):
    """Impide que una carga vuelva a crear AlMundo/Almundo como entidades distintas."""
    if session.info.get('normalizando_nombres_comerciales'):
        return
    candidatos = list(session.new) + list(session.dirty)
    for registro in candidatos:
        if isinstance(registro, Campania):
            cliente = _canonizar_cliente(registro.cliente)
            nombre = _canonizar_campania(cliente, registro.nombre)
            registro.cliente = cliente
            registro.nombre = nombre
            _registrar_nombre_canonico(cliente, nombre)
    for registro in candidatos:
        if not isinstance(registro, MODELOS_CON_IDENTIDAD_COMERCIAL):
            continue
        if hasattr(registro, 'cliente'):
            registro.cliente = _canonizar_cliente(registro.cliente)
        campo_campania = 'nombre' if isinstance(registro, Campania) else 'campania'
        if hasattr(registro, campo_campania):
            setattr(
                registro,
                campo_campania,
                _canonizar_campania(getattr(registro, 'cliente', ''), getattr(registro, campo_campania)),
            )
