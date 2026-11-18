"""Extrae datos parciales de Assurant de la caché de tabla dinámica del libro."""
import argparse
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archivo', type=Path)
    args = parser.parse_args()
    namespace = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(args.archivo) as libro:
        definicion = ElementTree.fromstring(libro.read('xl/pivotCache/pivotCacheDefinition8.xml'))
        campos = definicion.find('x:cacheFields', namespace)
        nombres = [campo.get('name') for campo in campos]
        esperados = ('Cuenta/Nom Diras', 'Mes', 'Objetivo Horas', 'Horas Facturadas', 'Total Facturado')
        if any(campo not in nombres for campo in esperados):
            raise ValueError('La estructura de la tabla dinámica no coincide con el libro esperado')
        compartidos = []
        for campo in campos:
            items = campo.find('x:sharedItems', namespace)
            compartidos.append([item.get('v') for item in items] if items is not None else [])
        registros = ElementTree.fromstring(libro.read('xl/pivotCache/pivotCacheRecords8.xml'))
        encontrados = []
        for registro in registros:
            valores = []
            for indice, celda in enumerate(registro):
                tipo, valor = celda.tag.rsplit('}', 1)[-1], celda.get('v')
                valores.append(compartidos[indice][int(valor)] if tipo == 'x' else
                               float(valor) if tipo == 'n' else valor if tipo in ('s', 'd') else None)
            fila = dict(zip(nombres, valores))
            if (str(fila['Cuenta/Nom Diras'] or '').casefold() == 'assurant' and
                    str(fila['Mes'] or '').startswith('2026-08')):
                encontrados.append(fila)
    if not encontrados:
        raise ValueError('No se encontraron datos de Assurant de agosto en la caché')
    datos = {'archivo': args.archivo.name, 'fuente': 'Caché de tabla dinámica 8 (2026!E:V)',
             'cliente': 'Assurant', 'campania': 'Assurant', 'mes': '2026-08',
             'horas_objetivo': sum(float(fila['Objetivo Horas'] or 0) for fila in encontrados),
             'horas_facturadas': sum(float(fila['Horas Facturadas'] or 0) for fila in encontrados),
             'total_facturado': sum(float(fila['Total Facturado'] or 0) for fila in encontrados),
             'registros': len(encontrados)}
    if not datos['horas_objetivo']:
        raise ValueError('No hay horas objetivo para calcular el porcentaje')
    destino = Path(__file__).resolve().parents[1] / 'app/data/assurant_agosto_cache.json'
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Recuperados {datos['registros']} registros de la tabla dinámica: {destino}")


if __name__ == '__main__':
    main()
