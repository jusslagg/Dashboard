import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import Facturacion2026
from app.routes import (
    clave_reemplazo_personal_mes,
    query_reemplazo_importacion,
    query_reemplazo_personal_mes,
)


app = create_app()
with app.app_context():
    personal = {
        'mes': '2026-07',
        'fecha': '2026-07-01',
        'cliente': 'Personal',
        'gerente': 'Personal',
        'jefe_site': 'Personal',
        'campania': 'Capacitaciones',
        'subcampania': 'Capacitaciones',
        'tipo_jornada': 'Capacitación',
        'tipo_negocio': None,
        '_importacion_directa_personal': True,
    }
    filas_personal = query_reemplazo_personal_mes(personal).all()
    assert len(filas_personal) == 114
    assert all(registro.mes == '2026-07' for registro in filas_personal)
    assert all(registro.cliente.lower().startswith('personal') for registro in filas_personal)
    assert clave_reemplazo_personal_mes(personal) == 'personal|2026-07'

    otro = Facturacion2026.query.filter(
        Facturacion2026.mes == '2026-07',
        ~Facturacion2026.cliente.ilike('personal%'),
    ).first()
    assert otro is not None
    payload_otro = {
        'fecha': otro.fecha.isoformat(), 'mes': otro.mes, 'cliente': otro.cliente,
        'gerente': otro.gerente or '', 'jefe_site': otro.jefe_site or '',
        'campania': otro.campania or '', 'subcampania': otro.subcampania or '',
        'tipo_jornada': otro.tipo_jornada, 'tipo_negocio': otro.tipo_negocio,
        '_importacion_directa_personal': False,
    }
    coincidencias_otro = query_reemplazo_importacion(payload_otro).all()
    assert coincidencias_otro
    assert all(not registro.cliente.lower().startswith('personal') for registro in coincidencias_otro)
    print({
        'personal_julio_a_reemplazar': len(filas_personal),
        'otros_clientes_incluidos': 0,
        'coincidencia_no_personal_se_rechaza': otro.cliente,
    })
