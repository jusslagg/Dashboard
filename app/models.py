from app import db
from datetime import datetime
import json
from werkzeug.security import check_password_hash, generate_password_hash


ROLES_USUARIO = ('administrador', 'usuario', 'superusuario')


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
        return self.rol in ('administrador', 'superusuario')

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


class Facturacion2026(db.Model):
    __tablename__ = 'facturacion_2026'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    cliente = db.Column(db.String(100), nullable=False)
    gerente = db.Column(db.String(100), nullable=True)
    jefe_site = db.Column(db.String(100), nullable=True)
    campania = db.Column(db.String(100), nullable=True)
    subcampania = db.Column(db.String(100), nullable=True)
    tipo_negocio = db.Column(db.String(100), nullable=True)
    tipo_jornada = db.Column(db.String(50), nullable=False)
    horas_objetivo = db.Column(db.Float, nullable=False)
    horas_facturadas = db.Column(db.Float, nullable=False)
    horas_penalizadas = db.Column(db.Float, default=0)
    valor_hora_objetivo = db.Column(db.Float, nullable=True)
    valor_hora = db.Column(db.Float, nullable=False)
    tarifacion = db.Column(db.Float, nullable=True)
    importe_fijo = db.Column(db.Float, nullable=True)
    variable_objetivo = db.Column(db.Float, default=0)
    variable_productivo = db.Column(db.Float, default=0)
    bonos = db.Column(db.Float, default=0)
    penalizaciones = db.Column(db.Float, default=0)
    netx_gen = db.Column(db.Float, default=0)
    otros = db.Column(db.Float, default=0)
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
    def objetivo_facturacion_horas(self):
        if self.importe_fijo is not None:
            return self.importe_fijo
        return self.horas_objetivo * self.valor_hora_objetivo_calculo

    @property
    def objetivo_facturacion_bono(self):
        return self.variable_objetivo or 0

    @property
    def facturacion_objetivo(self):
        return self.objetivo_facturacion_horas + self.objetivo_facturacion_bono

    @property
    def facturado_horas(self):
        if self.importe_fijo is not None:
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
        return self.penalizaciones or 0

    @property
    def porcentaje_cumplimiento_horas(self):
        if self.horas_objetivo == 0:
            return 0
        return (self.horas_facturadas / self.horas_objetivo) * 100

    @property
    def total_real(self):
        """Calcula el total facturado segun la apertura de control."""
        if self.importe_fijo is not None:
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
        if self.importe_fijo is not None:
            return self.total_real + (self.tarifacion or 0)
        return self.total_real + (self.tarifacion or 0)

    @property
    def total_dashboard(self):
        if self.importe_fijo is not None:
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
        if self.importe_fijo is not None:
            return self.importe_fijo
        return self.facturacion_objetivo

    @property
    def desvio(self):
        """Calcula el desvio real contra objetivo."""
        return self.total_real - self.total_teorico

    @property
    def porcentaje_cumplimiento(self):
        """Calcula el porcentaje de cumplimiento: total_real / total_teorico."""
        if self.importe_fijo is not None:
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
            'tipo_jornada': self.tipo_jornada,
            'horas_objetivo': self.horas_objetivo,
            'horas_facturadas': self.horas_facturadas,
            'horas_penalizadas': self.horas_penalizadas or 0,
            'valor_hora_objetivo': self.valor_hora_objetivo_calculo,
            'valor_hora_alcanzado': self.valor_hora_alcanzado,
            'valor_hora': self.valor_hora,
            'tarifacion': self.tarifacion,
            'importe_fijo': self.importe_fijo,
            'variable_objetivo': self.variable_objetivo,
            'variable_productivo': self.variable_productivo,
            'bonos': self.bonos,
            'penalizaciones': self.penalizaciones,
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
            'desvio': round(self.total_dashboard - self.total_teorico, 2),
            'porcentaje_cumplimiento': round(
                (self.total_dashboard / self.total_teorico * 100)
                if self.total_teorico > 0 else 0,
                2
            )
        }


class JustificacionAjuste(db.Model):
    __tablename__ = 'justificaciones_ajustes'

    id = db.Column(db.Integer, primary_key=True)
    facturacion_id = db.Column(db.Integer, db.ForeignKey('facturacion_2026.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    cantidad = db.Column(db.Float, default=1)
    precio = db.Column(db.Float, default=0)
    importe = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'facturacion_id': self.facturacion_id,
            'tipo': self.tipo,
            'cantidad': self.cantidad or 0,
            'precio': self.precio or 0,
            'importe': self.importe,
            'descripcion': self.descripcion,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }


class AsignacionComercial(db.Model):
    __tablename__ = 'asignaciones_comerciales'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    gerente = db.Column(db.String(100), nullable=False)
    jefe_site = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    subcampania = db.Column(db.String(100), nullable=False)
    tipo_negocio = db.Column(db.String(100), nullable=True)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def label(self):
        partes = [self.cliente, self.gerente, self.jefe_site, self.campania, self.subcampania]
        if self.tipo_negocio:
            partes.append(self.tipo_negocio)
        return ' / '.join(partes)

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'gerente': self.gerente,
            'jefe_site': self.jefe_site,
            'campania': self.campania,
            'subcampania': self.subcampania,
            'tipo_negocio': self.tipo_negocio,
            'activa': self.activa,
            'label': self.label
        }


class BajaOperativa(db.Model):
    __tablename__ = 'bajas_operativas'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.String(4), nullable=False, index=True)
    mes_baja = db.Column(db.String(20), nullable=False, index=True)
    campania = db.Column(db.String(100), nullable=False, index=True)
    motivo_baja = db.Column(db.String(120), nullable=False, index=True)
    cantidad = db.Column(db.Integer, default=1, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'year': self.year,
            'mes_baja': self.mes_baja,
            'campania': self.campania,
            'motivo_baja': self.motivo_baja,
            'cantidad': self.cantidad or 0,
            'creado_en': self.creado_en.isoformat() if self.creado_en else None,
        }
