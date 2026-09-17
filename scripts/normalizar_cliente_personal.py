"""Consolida Personal como cliente y conserva su apertura en tipo_negocio."""
from pathlib import Path
import sys
import unicodedata
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import (
    AsignacionComercial, Campania, Facturacion2026,
    normalizar_tipo_negocio_personal,
)


def clave(value):
    text = ''.join(
        char for char in unicodedata.normalize('NFD', str(value or '').lower())
        if unicodedata.category(char) != 'Mn'
    )
    return re.sub(r'[^a-z0-9]+', '', text)


app = create_app()
with app.app_context():
    asignaciones = AsignacionComercial.query.filter(
        AsignacionComercial.cliente.ilike('Personal%')
    ).all()
    registros = Facturacion2026.query.filter(
        Facturacion2026.cliente.ilike('Personal%')
    ).all()

    # Primero se combinan campañas repetidas, antes de renombrarlas, para no
    # violar la clave única (cliente, nombre) de Datos Maestros.
    campanias = Campania.query.filter(Campania.cliente.ilike('Personal%')).order_by(
        Campania.id
    ).all()
    por_nombre = {}
    eliminadas = 0
    for campania in campanias:
        nombre = clave(campania.nombre)
        principal = por_nombre.get(nombre)
        if principal is None or (principal.cliente != 'Personal' and campania.cliente == 'Personal'):
            if principal is not None:
                for asignacion in AsignacionComercial.query.filter_by(campania_id=principal.id).all():
                    asignacion.campania_id = campania.id
                db.session.delete(principal)
                eliminadas += 1
            por_nombre[nombre] = campania
            continue
        for asignacion in AsignacionComercial.query.filter_by(campania_id=campania.id).all():
            asignacion.campania_id = principal.id
        db.session.delete(campania)
        eliminadas += 1
    db.session.flush()

    for campania in por_nombre.values():
        campania.cliente = 'Personal'
    for registro in registros:
        cliente_original = registro.cliente
        registro.tipo_negocio = normalizar_tipo_negocio_personal(
            cliente_original, registro.tipo_negocio, registro.campania,
        )
        registro.cliente = 'Personal'
    for asignacion in asignaciones:
        cliente_original = asignacion.cliente
        asignacion.tipo_negocio = normalizar_tipo_negocio_personal(
            cliente_original, asignacion.tipo_negocio, asignacion.campania,
        )
        asignacion.cliente = 'Personal'
        asignacion.grupo_facturacion = 'Personal'

    db.session.commit()
    print({
        'facturacion_normalizada': len(registros),
        'asignaciones_normalizadas': len(asignaciones),
        'campanias_personal': len(por_nombre),
        'campanias_duplicadas_eliminadas': eliminadas,
    })
