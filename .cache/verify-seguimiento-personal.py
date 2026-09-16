import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import HistorialCambio, SeguimientoPersonalImportacion
from app.routes import deshacer_item_historial

archivo = Path(r'C:\Users\jegil\Downloads\2026 Seguimiento Personal Facturacion Variable Agosto.xlsx')
archivo_proforma = Path(r'C:\Users\jegil\Downloads\Proforma Proyectada Cable 08-2026.xlsx')
app = create_app()

with app.test_client() as client, app.app_context():
    with client.session_transaction() as sesion:
        sesion['usuario_id'] = 1
        sesion['csrf_token'] = 'verificacion-seguimiento'
    original_commit = db.session.commit
    db.session.commit = db.session.flush
    try:
        respuesta = client.post(
            '/api/seguimiento-personal/importar',
            data={'archivo': (io.BytesIO(archivo.read_bytes()), archivo.name)},
            headers={'X-CSRF-Token': 'verificacion-seguimiento'},
            content_type='multipart/form-data',
        )
        assert respuesta.status_code == 200, respuesta.get_data(as_text=True)
        importacion = respuesta.get_json()['importacion']
        print('importacion', importacion)
        assert importacion['cantidad_hojas'] == 5
        assert importacion['cantidad_filas'] == 3019
        assert importacion['cantidad_formulas'] > 20000
        assert importacion['advertencias'] == 23

        for clave, columnas in [('base_objetivo_masivo', 25), ('auxiliar_horas_plp_masivo', 23), ('precios', 14), ('2026', 33), ('aux', 13)]:
            hoja = client.get(f"/api/seguimiento-personal/hoja?importacion_id={importacion['id']}&hoja={clave}")
            assert hoja.status_code == 200
            datos = hoja.get_json()['hoja']
            assert datos['cantidad_columnas'] == columnas, (clave, datos['cantidad_columnas'])

        hoja_2026 = client.get(f"/api/seguimiento-personal/hoja?importacion_id={importacion['id']}&hoja=2026").get_json()['hoja']
        assert hoja_2026['referencias_rotas'][:2] == ['AB1', 'AC1']
        assert len(hoja_2026['referencias_rotas']) == 23
        assert hoja_2026['filas'][1][8]['f'] == '=+G2*H2'
        assert round(hoja_2026['filas'][1][8]['v'], 2) == 163370578.70

        respuesta_proforma = client.post(
            '/api/proforma-personal/importar',
            data={'tipo_proforma': 'Masivo', 'archivo': (io.BytesIO(archivo_proforma.read_bytes()), archivo_proforma.name)},
            headers={'X-CSRF-Token': 'verificacion-seguimiento'},
            content_type='multipart/form-data',
        )
        assert respuesta_proforma.status_code == 200, respuesta_proforma.get_data(as_text=True)
        assert respuesta_proforma.get_json()['seguimiento_actualizado'] is True
        proformas_importadas = respuesta_proforma.get_json()['proformas']
        cantidad_proformas = len(proformas_importadas)
        assert cantidad_proformas > 6
        generadas = {}
        for clave in ('base_objetivo_masivo', 'auxiliar_horas_plp_masivo', 'precios', '2026', 'aux'):
            generadas[clave] = client.get(f"/api/seguimiento-personal/hoja?importacion_id={importacion['id']}&hoja={clave}").get_json()['hoja']
        print('generadas', {clave: hoja['cantidad_filas'] for clave, hoja in generadas.items()})
        assert generadas['2026']['cantidad_filas'] == 1139 + cantidad_proformas
        assert generadas['base_objetivo_masivo']['cantidad_filas'] == 779 + cantidad_proformas
        equivalencias_tipo = {'FERIADO': 'Feriados', 'NOCTURNA': 'Nocturnas', 'NORMAL': 'Diurnas'}
        filas_agosto = [fila for fila in generadas['2026']['filas'][1:] if str(fila[2]['v']).startswith('2026-08-01') and fila[3]['v'] == 'Proyectada']
        assert len(filas_agosto) == cantidad_proformas
        for origen in proformas_importadas:
            destino = next(fila for fila in filas_agosto if fila[5]['v'] == origen['segmento'] and fila[17]['v'] == equivalencias_tipo[origen['tipo_hora']])
            assert round(destino[6]['v'], 4) == round(origen['total_horas'], 4)
            assert round(destino[7]['v'], 2) == round(origen['precio'], 2)
            assert round(destino[8]['v'], 2) == round(origen['monto_fijo'], 2)
            assert round(destino[9]['v'] * 100, 4) == round(origen['bono_porcentaje_total'], 4)
            assert round(destino[10]['v'], 2) == round(origen['monto_variable'], 2)
            assert round(destino[13]['v'], 2) == round(origen['total_proyeccion'], 2)
            assert destino[0]['f'].startswith('=VLOOKUP($Q') and destino[18]['f'].startswith('=IFERROR(VLOOKUP(Q')
        segunda_proforma = client.post(
            '/api/proforma-personal/importar',
            data={'tipo_proforma': 'Masivo', 'archivo': (io.BytesIO(archivo_proforma.read_bytes()), archivo_proforma.name)},
            headers={'X-CSRF-Token': 'verificacion-seguimiento'},
            content_type='multipart/form-data',
        )
        assert segunda_proforma.status_code == 200 and segunda_proforma.get_json()['actualizadas'] == cantidad_proformas
        filas_2026_segunda = client.get(f"/api/seguimiento-personal/hoja?importacion_id={importacion['id']}&hoja=2026").get_json()['hoja']['filas']
        agosto_proyectado = [fila for fila in filas_2026_segunda[1:] if str(fila[2]['v']).startswith('2026-08-01') and fila[3]['v'] == 'Proyectada']
        assert len(agosto_proyectado) == cantidad_proformas

        descarga = client.get(f"/api/seguimiento-personal/{importacion['id']}/descargar")
        assert descarga.status_code == 200 and len(descarga.data) == archivo.stat().st_size

        historial = HistorialCambio.query.filter_by(entidad='seguimiento_personal', entidad_id=str(importacion['id'])).order_by(HistorialCambio.id.desc()).first()
        resultado, estado = deshacer_item_historial(historial)
        assert estado == 200, resultado
        assert db.session.get(SeguimientoPersonalImportacion, importacion['id']) is None
        print({
            'status': respuesta.status_code,
            'hojas': importacion['cantidad_hojas'],
            'filas': importacion['cantidad_filas'],
            'formulas': importacion['cantidad_formulas'],
            'advertencias': importacion['advertencias'],
            'proformas_automaticas': cantidad_proformas,
            'deshacer': estado,
        })
    finally:
        db.session.rollback()
        db.session.commit = original_commit
