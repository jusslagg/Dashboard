"""Operational administration separated from the billing/calculation routes."""
from flask import Blueprint, g, jsonify, render_template, request
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from . import db
from .models import AsignacionComercial, Campania, ConfiguracionOperativa, ProyeccionMatriz, ProyeccionPrecio
from .operacion import anio_calendario, anio_operativo
from .routes import admin_requerido, registrar_historial, validar_confirmacion_accion

administracion_bp = Blueprint('administracion', __name__)


@administracion_bp.route('/administracion')
@admin_requerido
def index():
    return render_template('administracion.html')


@administracion_bp.route('/api/administracion/configuracion', methods=['GET', 'PATCH'])
@admin_requerido
def configuracion():
    setting = db.session.get(ConfiguracionOperativa, 'anio_predeterminado')
    if request.method == 'GET':
        return jsonify(success=True, anio=anio_operativo(), version=setting.version if setting else 0,
                       modo='calendario' if setting and setting.valor == 'calendario' else 'fijo',
                       anio_calendario=anio_calendario())
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(success=False, errores=['Enviá una configuración válida.']), 400
    year, version = data.get('anio'), data.get('version')
    mode = data.get('modo','fijo')
    if mode not in ('fijo','calendario'):
        return jsonify(success=False, errores=['Elegí un año fijo o el año calendario.']), 400
    if mode == 'calendario':
        year = anio_calendario()
    if type(year) is not int or not 2020 <= year <= 2100 or type(version) is not int or not 0 <= version < 2147483647:
        return jsonify(success=False, errores=['Elegí un año entre 2020 y 2100 y actualizá la configuración.']), 400
    if not validar_confirmacion_accion(data):
        return jsonify(success=False, errores=['La contraseña de confirmación no es válida.']), 403
    before = {'anio': anio_operativo(), 'version':setting.version if setting else 0,
              'modo':'calendario' if setting and setting.valor == 'calendario' else 'fijo'}
    value = 'calendario' if mode == 'calendario' else str(year)
    try:
        if setting:
            updated = ConfiguracionOperativa.query.filter_by(clave=setting.clave, version=version).update(
                {'valor':value, 'version':version + 1}, synchronize_session=False)
            if not updated:
                db.session.rollback()
                return jsonify(success=False, errores=['Otra persona cambió la configuración. Actualizá antes de guardar.']), 409
        else:
            if version != 0:
                return jsonify(success=False, errores=['La configuración cambió. Actualizá antes de guardar.']), 409
            db.session.add(ConfiguracionOperativa(clave='anio_predeterminado', valor=value, version=1))
        registrar_historial('edicion', 'configuracion_operativa', 'anio_predeterminado',
                            'Año de apertura de las vistas', antes=before,
                            despues={'anio':year, 'version':version + 1,'modo':mode})
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(success=False, errores=['Otra persona guardó la configuración. Actualizá antes de guardar.']), 409
    g.anio_operativo = year
    return jsonify(success=True, anio=year, version=version + 1, modo=mode,
                   mensaje='Año de apertura guardado. ' + ('Avanzará con el año calendario; no copia ni modifica datos históricos.' if mode == 'calendario' else 'Se aplica al abrir las vistas sin un año seleccionado.'))


@administracion_bp.route('/api/administracion/pendientes')
@admin_requerido
def pendientes():
    try:
        year = int(request.args.get('year') or anio_operativo())
        if not 2020 <= year <= 2100:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify(success=False, errores=['Año inválido.']), 400
    next_gen = exists(select(AsignacionComercial.id).where(
        AsignacionComercial.campania_id == Campania.id, AsignacionComercial.es_next_gen.is_(True)))
    standard = exists(select(AsignacionComercial.id).where(
        AsignacionComercial.campania_id == Campania.id, AsignacionComercial.es_next_gen.is_(False)))
    campaigns = Campania.query.filter(Campania.activa.is_(True), Campania.valor_hora_variable.is_(None),
                                     ~(next_gen & ~standard)).order_by(Campania.cliente, Campania.nombre)
    price_exists = exists(select(ProyeccionPrecio.id).where(
        ProyeccionPrecio.cliente == ProyeccionMatriz.cliente,
        ProyeccionPrecio.campania == ProyeccionMatriz.campania,
        ProyeccionPrecio.mes == ProyeccionMatriz.mes))
    projections = ProyeccionMatriz.query.filter(ProyeccionMatriz.year == year, ~price_exists).order_by(
        ProyeccionMatriz.cliente, ProyeccionMatriz.campania, ProyeccionMatriz.mes)
    return jsonify(success=True, year=year, revisiones=[
        {'id':'valor_hora', 'titulo':'Campañas sin modalidad de valor hora',
         'descripcion':'Completá la modalidad en Datos Maestros antes de cargar facturación para estas campañas.',
         'total':campaigns.count(), 'url':'/catalogos#configuracionValorHora',
         'detalle':[{'cliente':item.cliente,'campania':item.nombre} for item in campaigns.limit(50)]},
        {'id':'precios', 'titulo':'Meses proyectados sin fila de precio',
         'descripcion':'Revisá si falta cargar el precio o si el mes todavía está en preparación. No se completa automáticamente.',
         'total':projections.count(), 'url':'/matriz-precios',
         'detalle':[{'cliente':item.cliente,'campania':item.campania,'mes':item.mes} for item in projections.limit(50)]},
    ])
