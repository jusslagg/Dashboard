import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import Facturacion2026, ExcepcionCalculo
from app.routes import preparar_payload_edicion_facturacion, validar_payload_facturacion


app = create_app()
with app.app_context():
    registro = Facturacion2026.query.get(1420)
    payload = {
        'fecha': '2026-09-02', 'mes': '2026-08', 'cliente': registro.cliente,
        'gerente': registro.gerente, 'jefe_site': registro.jefe_site,
        'campania': registro.campania, 'subcampania': registro.subcampania,
        'tipo_jornada': registro.tipo_jornada, 'tipo_negocio': registro.tipo_negocio,
        'es_next_gen': False, 'horas_objetivo': 624, 'horas_facturadas': 590,
        'horas_penalizadas': 0, 'valor_hora_objetivo': 19183.47,
        'valor_hora': 18640.68, 'tarifacion': 146358.48,
        'importe_fijo': None, 'variable_objetivo': 0,
        'variable_productivo': 0, 'bonos': 0, 'penalizaciones': 0,
        'netx_gen': 0, 'otros': 0, 'justificaciones': [],
    }
    preparar_payload_edicion_facturacion(registro, payload)
    errores = validar_payload_facturacion(payload, exigir_configuracion_valor_hora=False)
    print({
        'manual_conservado': payload.get('facturado_horas_manual'),
        'valor_hora_validado': payload.get('valor_hora'),
        'errores': errores,
    })
    print('excepciones_activas', [
        (item.cliente, item.campania, item.tipo_calculo)
        for item in ExcepcionCalculo.query.filter_by(activa=True).all()
    ])

    bbva = Facturacion2026.query.filter_by(cliente='BBVA Seguros').order_by(Facturacion2026.fecha.desc()).first()
    if bbva:
        payload_bbva = {
            'fecha': bbva.fecha.isoformat(), 'mes': bbva.mes, 'cliente': bbva.cliente,
            'gerente': bbva.gerente, 'jefe_site': bbva.jefe_site,
            'campania': bbva.campania, 'subcampania': bbva.subcampania,
            'tipo_jornada': bbva.tipo_jornada, 'tipo_negocio': bbva.tipo_negocio,
            'es_next_gen': False, 'horas_objetivo': bbva.horas_objetivo,
            'horas_facturadas': bbva.horas_facturadas,
            'horas_penalizadas': bbva.horas_penalizadas or 0,
            'valor_hora_objetivo': bbva.valor_hora_objetivo,
            'valor_hora': bbva.valor_hora, 'tarifacion': bbva.tarifacion,
            'importe_fijo': bbva.importe_fijo, 'variable_objetivo': bbva.variable_objetivo or 0,
            'variable_productivo': bbva.variable_productivo or 0, 'bonos': bbva.bonos or 0,
            'penalizaciones': bbva.penalizaciones or 0, 'netx_gen': bbva.netx_gen or 0,
            'otros': bbva.otros or 0, 'justificaciones': [],
        }
        objetivo_antes, alcanzado_antes = payload_bbva['valor_hora_objetivo'], payload_bbva['valor_hora']
        preparar_payload_edicion_facturacion(bbva, payload_bbva)
        errores_bbva = validar_payload_facturacion(payload_bbva, exigir_configuracion_valor_hora=False)
        assert payload_bbva['valor_hora_objetivo'] == objetivo_antes
        assert payload_bbva['valor_hora'] == alcanzado_antes
        print({'bbva_sin_doble_ajuste': True, 'errores': errores_bbva})
