from app import db
from datetime import datetime


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
    tipo_jornada = db.Column(db.String(50), nullable=False)
    horas_objetivo = db.Column(db.Float, nullable=False)
    horas_facturadas = db.Column(db.Float, nullable=False)
    valor_hora_objetivo = db.Column(db.Float, nullable=True)
    valor_hora = db.Column(db.Float, nullable=False)
    tarifacion = db.Column(db.Float, nullable=True)
    importe_fijo = db.Column(db.Float, nullable=True)
    variable_productivo = db.Column(db.Float, default=0)
    bonos = db.Column(db.Float, default=0)
    penalizaciones = db.Column(db.Float, default=0)
    netx_gen = db.Column(db.Float, default=0)
    otros = db.Column(db.Float, default=0)

    @property
    def valor_hora_alcanzado(self):
        return self.tarifacion if self.tarifacion else self.valor_hora

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
        return 0

    @property
    def facturacion_objetivo(self):
        return self.objetivo_facturacion_horas + self.objetivo_facturacion_bono

    @property
    def facturado_horas(self):
        if self.importe_fijo is not None:
            return self.importe_fijo
        return self.horas_facturadas * self.valor_hora_alcanzado

    @property
    def facturado_bono(self):
        return (self.bonos or 0) + (self.variable_productivo or 0)

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
        """Calcula el total real: horas_facturadas por tarifa real, mas ajustes."""
        if self.importe_fijo is not None:
            return self.importe_fijo
        return (
            self.facturado_horas
            + self.facturado_bono
            - self.penalizaciones_incumplimientos
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
            'tipo_jornada': self.tipo_jornada,
            'horas_objetivo': self.horas_objetivo,
            'horas_facturadas': self.horas_facturadas,
            'valor_hora_objetivo': self.valor_hora_objetivo_calculo,
            'valor_hora_alcanzado': self.valor_hora_alcanzado,
            'valor_hora': self.valor_hora,
            'tarifacion': self.tarifacion,
            'importe_fijo': self.importe_fijo,
            'variable_productivo': self.variable_productivo,
            'bonos': self.bonos,
            'penalizaciones': self.penalizaciones,
            'netx_gen': self.netx_gen,
            'otros': self.otros,
            'objetivo_facturacion_horas': round(self.objetivo_facturacion_horas, 2),
            'objetivo_facturacion_bono': round(self.objetivo_facturacion_bono, 2),
            'facturacion_objetivo': round(self.facturacion_objetivo, 2),
            'facturado_horas': round(self.facturado_horas, 2),
            'facturado_bono': round(self.facturado_bono, 2),
            'penalizaciones_incumplimientos': round(self.penalizaciones_incumplimientos, 2),
            'porcentaje_cumplimiento_horas': round(self.porcentaje_cumplimiento_horas, 2),
            'total_facturado': round(self.total_real, 2),
            'total_real': round(self.total_real, 2),
            'total_teorico': round(self.total_teorico, 2),
            'desvio': round(self.desvio, 2),
            'porcentaje_cumplimiento': round(self.porcentaje_cumplimiento, 2)
        }


class AsignacionComercial(db.Model):
    __tablename__ = 'asignaciones_comerciales'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    gerente = db.Column(db.String(100), nullable=False)
    jefe_site = db.Column(db.String(100), nullable=False)
    campania = db.Column(db.String(100), nullable=False)
    subcampania = db.Column(db.String(100), nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'gerente': self.gerente,
            'jefe_site': self.jefe_site,
            'campania': self.campania,
            'subcampania': self.subcampania,
            'activa': self.activa,
            'label': f'{self.cliente} / {self.gerente} / {self.jefe_site} / {self.campania} / {self.subcampania}'
        }
