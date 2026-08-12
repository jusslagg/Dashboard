from app import db
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
from werkzeug.security import check_password_hash, generate_password_hash


ROLES_USUARIO = ('administrador', 'usuario', 'superusuario')

# Tipos numéricos del contrato de base. ``asdecimal=False`` mantiene la
# compatibilidad de las APIs y cálculos Python actuales, mientras que el motor
# almacena los valores con precisión y escala explícitas.
DINERO = db.Numeric(18, 2, asdecimal=False)
CANTIDAD = db.Numeric(18, 4, asdecimal=False)
HORAS = db.Numeric(12, 2, asdecimal=False)
PORCENTAJE = db.Numeric(9, 4, asdecimal=False)
COTIZACION = db.Numeric(18, 6, asdecimal=False)


def redondear_moneda(valor):
    return float(Decimal(str(valor or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(30), nullable=False, default='usuario')
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_administrador(self):
        return self.rol == 'administrador'

    @property
    def es_superusuario(self):
        return self.rol == 'superusuario'

    @property
    def puede_editar(self):
        return self.rol in ('administrador', 'superusuario')

    @property
    def puede_eliminar(self):
        return self.rol == 'administrador'

    @property
    def puede_ver_carga(self):
        return self.rol in ('administrador', 'superusuario')

    @property
    def puede_ver_catalogos(self):
        return self.rol in ('administrador', 'superusuario')

    @property
    def puede_administrar_usuarios(self):
        return self.rol == 'administrador'

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'email': self.email,
            'rol': self.rol,
            'activo': self.activo,
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
    tarifacion = db.Column(DINERO, nullable=True)
    importe_fijo = db.Column(DINERO, nullable=True)
    variable_objetivo = db.Column(DINERO, default=0)
    variable_productivo = db.Column(DINERO, default=0)
    bonos = db.Column(DINERO, default=0)
    penalizaciones = db.Column(DINERO, default=0)
    netx_gen = db.Column(DINERO, default=0)
    otros = db.Column(DINERO, default=0)
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
        """Calcula el total objetivo: horas_objetivo por valor_hora_objetivo."""
        if self.usa_importe_fijo:
            return self.importe_fijo
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
    precio_base = db.Column(DINERO, default=0, nullable=False)
    alcance_porcentaje = db.Column(PORCENTAJE, default=100, nullable=False)
    precio_final = db.Column(DINERO, default=0, nullable=False)
    importe_fijo_mensual = db.Column(DINERO, default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cliente', 'campania', 'mes', name='uq_matriz_precios_cliente_campania_mes'),
    )

    def recalcular(self):
        total = Decimal(str(self.precio_base or 0)) * (Decimal(str(self.alcance_porcentaje or 0)) / Decimal('100'))
        self.precio_final = redondear_moneda(total)

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
            'precio_final': round(self.precio_final or 0, 2),
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
    monto = db.Column(DINERO, default=0, nullable=False)
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
    cantidad_usd = db.Column(DINERO, default=0, nullable=False)
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
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    campania_catalogo = db.relationship('Campania', lazy=True)

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
            'label': self.label
        }
