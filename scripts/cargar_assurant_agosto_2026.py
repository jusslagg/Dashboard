"""Carga y concilia la fila de agosto de Assurant proporcionada por el usuario."""
import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Facturacion2026
from app.routes import construir_apertura_desvios_clientes, registrar_historial
from scripts.reemplazar_facturacion_libro import fila_facturacion


def fila_usuario():
    # Las columnas AB y AE se muestran redondeadas en la captura; sus valores
    # precisos están en N/V y se confirman con los desvíos suministrados.
    valores = [None] * 31
    for indice, valor in {
        0: 'Agosto', 1: 'CAROLINA SURACE', 2: 'CAT',
        3: 'ASSURANT ARGENTINA COMPAÑIA DE SEGUROS S.A.', 4: 'Assurant',
        5: 'Pablo Sconocchini', 6: 'Assurant', 7: 'BBVA - Desempleo HOT RDI',
        8: 'Horas', 9: datetime(2026, 8, 1), 10: 1800, 11: 1899,
        12: 18993.67, 13: 36068979.33, 21: 36068979.33,
        22: 19057.41, 23: 18993.67, 24: 34188606, 25: 114732,
        26: 34303338, 27: 36068979.33, 28: 0, 29: 0, 30: 36068979.33,
    }.items():
        valores[indice] = valor
    return valores


def cargar(aplicar=False):
    existentes = [r for r in Facturacion2026.query.filter_by(mes='2026-08').all()
                  if r.cliente.casefold() == 'assurant']
    if existentes:
        raise RuntimeError(f'Ya existen {len(existentes)} registros de Assurant en agosto; no se modificó ninguno.')
    antes = construir_apertura_desvios_clientes(2026)
    total_antes = next(f for f in antes['filas'] if f['cliente'] == 'TOTAL GENERAL' and f['mes'] == '2026-08')
    registro = fila_facturacion(fila_usuario(), 2026)
    db.session.add(registro)
    db.session.flush()
    despues = construir_apertura_desvios_clientes(2026)
    fila = next(f for f in despues['filas'] if f['cliente'].casefold() == 'assurant' and f['mes'] == '2026-08')
    total_despues = next(f for f in despues['filas'] if f['cliente'] == 'TOTAL GENERAL' and f['mes'] == '2026-08')
    esperados = {'cumplimiento_horas': 1899 / 1800, 'horas': 1880373.33,
                 'variable': -114732, 'bonos_penalizaciones': 0, 'total': 1765641.33,
                 'cumplimiento_facturacion': 36068979.33 / 34303338,
                 'porcentaje_desvio': 1765641.33 / 34303338}
    for campo, esperado in esperados.items():
        if fila[campo] is None or abs(fila[campo] - esperado) > (0.001 if campo in ('horas', 'variable', 'bonos_penalizaciones', 'total') else 1e-10):
            raise AssertionError(f'{campo}: esperado {esperado}, calculado {fila[campo]}')
    if fila.get('fuente_parcial') or despues.get('recuperaciones'):
        raise AssertionError('El dato parcial no fue sustituido por el registro confirmado')
    for campo in ('horas', 'variable', 'bonos_penalizaciones', 'total'):
        diferencia = total_despues[campo] - total_antes[campo]
        if abs(diferencia - esperados[campo]) > .001:
            raise AssertionError(f'Total general {campo}: diferencia inesperada {diferencia}')
    registrar_historial('creacion', 'facturacion', registro.id,
        'Facturación cargada: Assurant / agosto 2026', despues=registro.to_dict(),
        detalle='Fila de facturación proporcionada por el usuario; reemplaza la referencia parcial de la tabla dinámica.')
    resultado = {'id': registro.id, 'mes': registro.mes, 'cliente': registro.cliente,
                 'horas_objetivo': registro.horas_objetivo, 'horas_facturadas': registro.horas_facturadas,
                 'valor_hora_objetivo': registro.valor_hora_objetivo, 'valor_hora': registro.valor_hora,
                 'facturado': registro.total_facturado_manual, 'apertura': fila}
    if aplicar:
        db.session.commit()
    else:
        db.session.rollback()
    return resultado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aplicar', action='store_true')
    args = parser.parse_args()
    app = create_app()
    with app.app_context(), app.test_request_context():
        if args.aplicar and db.engine.dialect.name == 'sqlite':
            origen = Path(db.engine.url.database).resolve()
            carpeta = Path(__file__).resolve().parents[1] / '.cache' / 'respaldos'
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / f"facturacion_antes_assurant_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
            with sqlite3.connect(f'file:{origen.as_posix()}?mode=ro', uri=True) as source:
                with sqlite3.connect(destino) as target:
                    source.backup(target)
            print(f'Respaldo previo: {destino}')
        resultado = cargar(args.aplicar)
        print(('Cargado' if args.aplicar else 'Validación sin guardar') + ':', resultado)


if __name__ == '__main__':
    main()
