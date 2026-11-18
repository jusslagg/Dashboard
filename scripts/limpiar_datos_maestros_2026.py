"""Alinea altas con los dos libros operativos. Por defecto solo simula."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

from openpyxl import load_workbook
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio, _clave_nombre

FACTURACION = Path(r'C:\Users\jegil\Downloads\2026 Facturacion V2 (2).xlsx')
PROYECCION = Path(r'C:\Users\jegil\Downloads\Proyeccion Horas V4 (5).xlsx')


def clave(*valores):
    return tuple(_clave_nombre(str(valor or '')) for valor in valores)


def textos_fuente():
    encontrados = set()
    for ruta, hojas in ((FACTURACION, ['2026']), (PROYECCION, [
        'Matriz', 'LISTADO', 'Unificado', 'Desglose HORAS PERSONAL', 'Precios',
        'Next Gen', 'Facturacion Horas', 'Variable', 'Tarifacion', 'Horas',
    ])):
        libro = load_workbook(ruta, data_only=True, read_only=True)
        for hoja in hojas:
            for fila in libro[hoja].iter_rows(values_only=True):
                encontrados.update(_clave_nombre(valor) for valor in fila if isinstance(valor, str))
        libro.close()
    return encontrados


def ejecutar(apply=False):
    fuentes = textos_fuente()
    altas = AsignacionComercial.query.filter_by(activa=True).order_by(AsignacionComercial.id).all()
    facturas = Facturacion2026.query.filter(Facturacion2026.mes.like('2026-%')).all()
    por_factura = defaultdict(list)
    for f in facturas:
        por_factura[clave(f.cliente, f.campania, f.subcampania)].append(f)
    cambios = {}
    pendientes = []

    def cambiar(alta, motivo, **nuevos):
        diferentes = {campo: valor for campo, valor in nuevos.items() if getattr(alta, campo) != valor}
        if not diferentes:
            return
        entrada = cambios.setdefault(alta.id, {'id': alta.id, 'antes': alta.to_dict(), 'motivos': []})
        entrada['motivos'].append(motivo)
        for campo, valor in diferentes.items():
            setattr(alta, campo, valor)

    # Los nombres no aparecen en ninguno de los dos libros ni en la facturación
    # vigente. Se verifica también el nombre antes de tocar cada ID.
    obsoletas = {
        20: 'Supervielle Prestamos Previsional', 141: 'Supervielle Prestamos Previsional',
        26: 'Energía San Juan TL', 48: 'Mirgor Buyback Tl',
        92: 'Mixto Estables', 93: 'Mixto Ingresos',
        96: 'Retención Seguros', 106: 'Retención Seguros', 98: 'Isla Prevención de fraude',
    }
    for alta in altas:
        nombre = obsoletas.get(alta.id)
        if not nombre or clave(alta.subcampania) != clave(nombre):
            continue
        usado = any(clave(f.cliente, f.subcampania) == clave(alta.cliente, alta.subcampania) for f in facturas)
        if clave(nombre)[0] in fuentes or usado:
            pendientes.append(f'{alta.cliente} / {nombre}: apareció una fuente y se conservó')
            continue
        cambiar(alta, 'No aparece en los libros ni en las cargas vigentes', activa=False)

    # Chat Redes tiene ahora campaña Santander Chat y conserva la misma
    # subcampaña, tal como figura en el archivo de Facturación.
    equivalentes = [a for a in altas if a.id == 224 and a.activa]
    if len(equivalentes) == 1:
        vigente = equivalentes[0]
        if por_factura.get(clave(vigente.cliente, vigente.campania, vigente.subcampania)):
            for alta in altas:
                if alta.id in (6, 110) and clave(alta.cliente, alta.campania, alta.subcampania) == clave(
                    'Santander', 'Santander Chat Redes', 'Santander Chat Redes'
                ):
                    cambiar(alta, 'Reemplazada por la campaña y subcampaña vigentes del archivo', activa=False)

    por_alta = defaultdict(list)
    for alta in altas:
        if alta.activa:
            por_alta[clave(alta.cliente, alta.campania, alta.subcampania, alta.tipo_negocio, alta.es_next_gen)].append(alta)
    for identidad, grupo in por_alta.items():
        if len(grupo) < 2:
            continue
        hechos = por_factura.get(clave(grupo[0].cliente, grupo[0].campania, grupo[0].subcampania), [])
        hechos = [f for f in hechos if bool(f.es_next_gen) == bool(grupo[0].es_next_gen)]
        responsables = {(clave(f.gerente)[0], clave(f.jefe_site)[0]) for f in hechos if f.gerente and f.jefe_site}
        jefes = {jefe for _, jefe in responsables}
        if len(jefes) == 1:
            compatibles = [alta for alta in grupo if clave(alta.jefe_site)[0] in jefes]
        elif not hechos and len({clave(a.gerente, a.jefe_site) for a in grupo}) == 1:
            compatibles = grupo
        else:
            compatibles = []
        if not compatibles:
            pendientes.append(f'{grupo[0].cliente} / {grupo[0].subcampania}: responsables no únicos')
            continue
        elegido = min(compatibles, key=lambda a: a.id)
        for alta in grupo:
            if alta.id != elegido.id:
                cambiar(alta, f'Duplicada; se conserva la asociación #{elegido.id} respaldada por el archivo', activa=False)
        if hechos and len(responsables) == 1:
            cambiar(elegido, 'La misma jefatura figura durante todos los meses del archivo',
                    vigencia_desde=None, vigencia_hasta=None)

    # Actualiza responsables únicamente cuando la identidad completa y el
    # último mes tienen una correspondencia única y valores informados.
    activas = [alta for alta in altas if alta.activa]
    for identidad, hechos in por_factura.items():
        ultimo = max(f.mes for f in hechos)
        recientes = [f for f in hechos if f.mes == ultimo]
        grupos = defaultdict(list)
        for f in recientes:
            tipo = clave(f.tipo_negocio)[0] if clave(f.cliente)[0] == 'personal' else ''
            grupos[(tipo, bool(f.es_next_gen))].append(f)
        for (tipo, es_next_gen), items in grupos.items():
            candidatos = [a for a in activas if clave(a.cliente, a.campania, a.subcampania) == identidad
                          and bool(a.es_next_gen) == es_next_gen
                          and (not tipo or clave(a.tipo_negocio)[0] == tipo)]
            if len(candidatos) != 1:
                continue
            responsables = {(f.gerente, f.jefe_site) for f in items}
            if len(responsables) != 1:
                pendientes.append(f'{items[0].cliente} / {items[0].subcampania}: responsables distintos en {ultimo}')
                continue
            gerente, jefe = next(iter(responsables))
            campos = {}
            if gerente and clave(gerente)[0] not in ('sinasignar', 'singerencia'):
                campos['gerente'] = gerente
            if jefe and clave(jefe)[0] not in ('sinasignar', 'singerencia'):
                campos['jefe_site'] = jefe
            cambiar(candidatos[0], f'Responsables según Facturación {ultimo}', **campos)

    db.session.flush()
    for entrada in cambios.values():
        entrada['despues'] = db.session.get(AsignacionComercial, entrada['id']).to_dict()
    resultado = {'cambios': list(cambios.values()), 'pendientes': pendientes,
                 'desactivadas': sum(not x['despues']['activa'] for x in cambios.values()),
                 'actualizadas': sum(x['despues']['activa'] for x in cambios.values())}
    if apply:
        db.session.add(HistorialCambio(
            usuario_nombre='Sistema', accion='edicion', entidad='limpieza_datos_maestros', entidad_id='2026',
            resumen=f'Datos Maestros: {resultado["desactivadas"]} antiguas desactivadas y {resultado["actualizadas"]} actualizadas',
            detalle='Conciliación contra los archivos de Facturación y Proyectados de 2026.',
            antes=json.dumps({'asignaciones': [x['antes'] for x in resultado['cambios']]}, ensure_ascii=False),
            despues=json.dumps(resultado, ensure_ascii=False),
        ))
        db.session.commit()
    else:
        db.session.rollback()
    return resultado


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        resultado = ejecutar(args.apply)
        if args.report:
            args.report.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Altas desactivadas: {resultado['desactivadas']}; actualizadas: {resultado['actualizadas']}; pendientes: {len(resultado['pendientes'])}")
