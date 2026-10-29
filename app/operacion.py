"""User-managed operational preferences, resolved per request across workers."""
from flask import current_app, g, has_request_context
from .models import ConfiguracionOperativa
from . import db
from datetime import datetime


def anio_calendario():
    return datetime.now().year


def anio_operativo():
    if has_request_context() and hasattr(g, 'anio_operativo'):
        return g.anio_operativo
    setting = db.session.get(ConfiguracionOperativa, 'anio_predeterminado')
    year = (anio_calendario() if setting.valor == 'calendario' else int(setting.valor)) if setting else current_app.config['DEFAULT_YEAR']
    if has_request_context():
        g.anio_operativo = year
    return year
